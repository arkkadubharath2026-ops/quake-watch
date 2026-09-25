"""Ingestion application services: feed sync, checkpointed backfill, detail enrichment.

Each service records an ``ingestion_runs`` document for every unit of upstream work, including
request provenance, outcome counts and structured errors (FR-01, FR-02, FR-14, ESD §15).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import structlog

from apps.core import metrics
from apps.core.arango import StandardDatabase
from apps.core.arango import schema as s
from apps.core.arango.client import sync, sync_optional
from apps.core.arango.transactions import run_in_transaction
from apps.core.clock import from_epoch_ms, from_iso, now_iso, to_iso, utc_now
from apps.core.errors import CircuitOpen, NotFound, SourceSchemaError, ValidationFailed
from apps.ingestion.adapters.http import SourceRequest, UpstreamRequestFailed
from apps.ingestion.adapters.usgs import CATALOG_MAX_LIMIT, SOURCE, UsgsClient
from apps.ingestion.enrichment import summarize_products
from apps.ingestion.normalizer import parse_feed
from apps.ingestion.pipeline import EventObserver, IngestionPipeline, IngestionStats
from apps.ingestion.repository import RunRepository
from config.logging import get_logger

log = get_logger(__name__)

RunStatus = Literal["succeeded", "partial", "failed", "skipped"]

MAX_BACKFILL_SPAN = timedelta(days=3 * 366)
MIN_SPLIT_WINDOW = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str
    status: RunStatus
    counts: dict[str, int]
    important_keys: tuple[str, ...] = ()
    error: str | None = None


def _correlation_id() -> str | None:
    value = structlog.contextvars.get_contextvars().get("correlation_id")
    return str(value) if value else None


def _error_dict(exc: Exception) -> dict[str, Any]:
    details = getattr(exc, "details", {}) or {}
    return {
        "type": type(exc).__name__,
        "code": getattr(exc, "code", None),
        "message": str(exc),
        "transient": getattr(exc, "transient", None),
        "details": {k: v for k, v in details.items() if k != "request"},
    }


class FeedSyncService:
    """Scheduled synchronisation of a USGS summary feed (FR-01)."""

    def __init__(
        self,
        db: StandardDatabase,
        client: UsgsClient,
        *,
        observers: Sequence[EventObserver] = (),
    ) -> None:
        self.db = db
        self.client = client
        self.runs = RunRepository(db)
        self.observers = observers

    def run(self, feed: str) -> RunResult:
        run_id = self.runs.start_run(
            kind="feed_sync", source=SOURCE, params={"feed": feed}, correlation_id=_correlation_id()
        )
        structlog.contextvars.bind_contextvars(ingestion_run_id=run_id, source=SOURCE)
        started = time.perf_counter()
        requests: list[dict[str, Any]] = []
        try:
            fetch = self.client.summary_feed(feed)
            requests.append(fetch.request.as_dict())
            parsed = parse_feed(fetch.body)
            stats = IngestionPipeline(self.db, observers=self.observers, run_id=run_id).ingest(
                parsed.records, parsed.rejected
            )
        except CircuitOpen as exc:
            return self._finish_failed(run_id, started, requests, exc, status="skipped")
        except UpstreamRequestFailed as exc:
            requests.append(exc.request.as_dict())
            return self._finish_failed(run_id, started, requests, exc)
        except SourceSchemaError as exc:
            return self._finish_failed(run_id, started, requests, exc)
        finally:
            structlog.contextvars.unbind_contextvars("ingestion_run_id", "source")

        degraded = stats.counts["rejected"] or stats.counts["failed"]
        status: RunStatus = "partial" if degraded else "succeeded"
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        self.runs.finish_run(
            run_id,
            status=status,
            counts=stats.as_dict(),
            requests=requests,
            duration_ms=duration_ms,
            source_generated_at=to_iso(from_epoch_ms(parsed.metadata.generated)),
        )
        metrics.incr("sync_runs_total")
        metrics.incr(f"sync_runs_{status}")
        metrics.observe("sync_duration_ms", duration_ms)
        return RunResult(run_id, status, stats.as_dict(), tuple(stats.important_keys))

    def _finish_failed(
        self,
        run_id: str,
        started: float,
        requests: list[dict[str, Any]],
        exc: Exception,
        *,
        status: RunStatus = "failed",
    ) -> RunResult:
        self.runs.finish_run(
            run_id,
            status=status,
            counts={},
            requests=requests,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            error=_error_dict(exc),
        )
        metrics.incr("sync_runs_total")
        metrics.incr(f"sync_runs_{status}")
        log.warning("feed_sync_failed", ingestion_run_id=run_id, status=status, error=str(exc))
        return RunResult(run_id, status, {}, (), str(exc))


# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BackfillRequest:
    start: datetime
    end: datetime
    min_magnitude: float | None
    window_days: int
    requested_by: str

    def validate(self, now: datetime) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValidationFailed("backfill bounds must be timezone-aware")
        if self.end <= self.start:
            raise ValidationFailed("backfill end must be after start")
        if self.end > now + timedelta(minutes=5):
            raise ValidationFailed("backfill end cannot be in the future")
        if self.end - self.start > MAX_BACKFILL_SPAN:
            raise ValidationFailed("backfill span is limited to 3 years per job (bounded backfill)")
        if not 1 <= self.window_days <= 31:
            raise ValidationFailed("window_days must be between 1 and 31")
        if self.min_magnitude is not None and not -1 <= self.min_magnitude <= 10:
            raise ValidationFailed("min_magnitude out of range")


class BackfillInterrupted(Exception):
    """A window failed transiently; the job is checkpointed and should be retried later."""

    def __init__(self, job_id: str, cause: Exception, retry_after: float | None) -> None:
        super().__init__(f"backfill {job_id} interrupted: {cause}")
        self.job_id = job_id
        self.cause = cause
        self.retry_after = retry_after


class BackfillService:
    """Bounded, checkpointed historical import through the FDSN catalog API (FR-02, ESD §4.2).

    The job advances window by window. The checkpoint (``next_window_start``) is persisted only
    after a window's events are committed, so a crash re-processes at most one window — which is
    harmless because ingestion is idempotent. Windows whose count exceeds the API's
    ``maxAllowed`` are split in half recursively.
    """

    def __init__(
        self, db: StandardDatabase, client: UsgsClient, *, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.db = db
        self.client = client
        self.runs = RunRepository(db)
        self.clock = clock

    def create_job(self, request: BackfillRequest) -> str:
        request.validate(self.clock())
        job_id = uuid.uuid4().hex
        self.runs.create_backfill_job(
            {
                "_key": job_id,
                "source": SOURCE,
                "status": "pending",
                "start": to_iso(request.start),
                "end": to_iso(request.end),
                "min_magnitude": request.min_magnitude,
                "window_days": request.window_days,
                "next_window_start": to_iso(request.start),
                "windows_completed": 0,
                "counts": {},
                "requested_by": request.requested_by,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "heartbeat_at": None,
                "attempts": 0,
                "last_error": None,
            }
        )
        log.info(
            "backfill_job_created",
            backfill_job_id=job_id,
            start=to_iso(request.start),
            end=to_iso(request.end),
        )
        return job_id

    def run_job(self, job_id: str, *, max_windows: int | None = None) -> dict[str, Any]:
        job = self.runs.get_backfill_job(job_id)
        if job is None:
            raise NotFound(f"backfill job {job_id} not found")
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        end = from_iso(job["end"])
        window = timedelta(days=int(job["window_days"]))
        cursor = from_iso(job["next_window_start"])
        totals: dict[str, int] = dict(job.get("counts") or {})
        self.runs.update_backfill_job(
            job_id,
            {"status": "running", "attempts": int(job["attempts"]) + 1, "heartbeat_at": now_iso()},
        )
        processed = 0
        while cursor < end and (max_windows is None or processed < max_windows):
            window_end = min(cursor + window, end)
            try:
                counts = self._process_window(job, cursor, window_end)
            except (UpstreamRequestFailed, CircuitOpen) as exc:
                self.runs.update_backfill_job(
                    job_id,
                    {
                        "status": "pending" if exc.transient else "failed",
                        "last_error": _error_dict(exc),
                        "updated_at": now_iso(),
                    },
                )
                if exc.transient:
                    raise BackfillInterrupted(job_id, exc, exc.retry_after_seconds) from exc
                raise
            except SourceSchemaError as exc:
                self.runs.update_backfill_job(
                    job_id, {"status": "failed", "last_error": _error_dict(exc)}
                )
                raise
            for name, value in counts.items():
                totals[name] = totals.get(name, 0) + value
            cursor = window_end
            processed += 1
            self.runs.update_backfill_job(
                job_id,
                {
                    "next_window_start": to_iso(cursor),
                    "windows_completed": int(job["windows_completed"]) + processed,
                    "counts": totals,
                    "heartbeat_at": now_iso(),
                    "updated_at": now_iso(),
                    "last_error": None,
                },
            )
        done = cursor >= end
        self.runs.update_backfill_job(
            job_id,
            {
                "status": "completed" if done else "pending",
                "completed_at": now_iso() if done else None,
                "updated_at": now_iso(),
            },
        )
        return self.runs.get_backfill_job(job_id) or {}

    def _process_window(
        self, job: dict[str, Any], start: datetime, end: datetime
    ) -> dict[str, int]:
        min_mag = job["min_magnitude"]
        count = self.client.catalog_count(start=start, end=end, min_magnitude=min_mag)
        if count.count >= min(count.max_allowed, CATALOG_MAX_LIMIT):
            return self._split(job, start, end, f"count {count.count} >= limit")

        run_id = self.runs.start_run(
            kind="backfill_window",
            source=SOURCE,
            params={"start": to_iso(start), "end": to_iso(end), "min_magnitude": min_mag},
            correlation_id=_correlation_id(),
            backfill_job_id=job["_key"],
        )
        started = time.perf_counter()
        requests: list[SourceRequest] = [count.request]
        try:
            if count.count == 0:
                stats = IngestionStats()
            else:
                fetch = self.client.catalog_query(start=start, end=end, min_magnitude=min_mag)
                requests.append(fetch.request)
                parsed = parse_feed(fetch.body)
                returned = len(parsed.records) + len(parsed.rejected)
                if returned >= CATALOG_MAX_LIMIT:
                    # Grew past the limit between count and query: never ingest a truncated
                    # window; record the run and split instead.
                    self.runs.finish_run(
                        run_id,
                        status="split",
                        counts={"returned": returned},
                        requests=[r.as_dict() for r in requests],
                        duration_ms=round((time.perf_counter() - started) * 1000, 1),
                    )
                    return self._split(job, start, end, f"query returned {returned} rows")
                stats = IngestionPipeline(self.db, run_id=run_id, mode="backfill").ingest(
                    parsed.records, parsed.rejected
                )
        except (UpstreamRequestFailed, SourceSchemaError, CircuitOpen) as exc:
            if isinstance(exc, UpstreamRequestFailed):
                requests.append(exc.request)
            self.runs.finish_run(
                run_id,
                status="failed",
                counts={},
                requests=[r.as_dict() for r in requests],
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                error=_error_dict(exc),
            )
            raise
        status = "partial" if stats.counts["rejected"] or stats.counts["failed"] else "succeeded"
        self.runs.finish_run(
            run_id,
            status=status,
            counts=stats.as_dict(),
            requests=[r.as_dict() for r in requests],
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return stats.as_dict()

    def _split(
        self, job: dict[str, Any], start: datetime, end: datetime, reason: str
    ) -> dict[str, int]:
        if end - start <= MIN_SPLIT_WINDOW:
            raise SourceSchemaError(
                f"catalog window {to_iso(start)}..{to_iso(end)} cannot be split further ({reason})"
            )
        middle = start + (end - start) / 2
        log.info("backfill_window_split", start=to_iso(start), end=to_iso(end), reason=reason)
        first = self._process_window(job, start, middle)
        second = self._process_window(job, middle, end)
        return {k: first.get(k, 0) + second.get(k, 0) for k in set(first) | set(second)}

    def recover_stalled(self, *, stale_after: timedelta = timedelta(minutes=20)) -> list[str]:
        """Jobs left ``running`` by a dead worker (no heartbeat) go back to ``pending``."""
        threshold = to_iso(self.clock() - stale_after)
        recovered = []
        for job in self.runs.active_backfill_jobs():
            heartbeat = job.get("heartbeat_at") or job["created_at"]
            if job["status"] == "running" and heartbeat < threshold:
                self.runs.update_backfill_job(
                    job["_key"], {"status": "pending", "updated_at": now_iso()}
                )
                recovered.append(job["_key"])
        return recovered


# ---------------------------------------------------------------------------------------------
class EnrichmentService:
    """Lazy detail-feed enrichment (ESD §4.3). Failure never affects the base event record."""

    def __init__(self, db: StandardDatabase, client: UsgsClient) -> None:
        self.db = db
        self.client = client
        self.runs = RunRepository(db)

    def enrich(self, event_key: str) -> dict[str, Any]:
        events = self.db.collection(s.EVENTS)
        event = sync_optional(events.get(event_key))
        if not isinstance(event, dict):
            raise NotFound(f"event {event_key} not found")
        run_id = self.runs.start_run(
            kind="detail_enrichment",
            source=SOURCE,
            params={"event_key": event_key, "source_event_id": event["source_event_id"]},
            correlation_id=_correlation_id(),
        )
        started = time.perf_counter()
        try:
            detail = self.client.detail(event["source_event_id"])
        except (UpstreamRequestFailed, SourceSchemaError, CircuitOpen) as exc:
            requests = [exc.request.as_dict()] if isinstance(exc, UpstreamRequestFailed) else []
            self.runs.finish_run(
                run_id,
                status="failed",
                counts={},
                requests=requests,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                error=_error_dict(exc),
            )
            previous = event.get("enrichment") or {}
            sync(
                events.update(
                    {
                        "_key": event_key,
                        "enrichment": {
                            **previous,
                            "last_error": str(exc),
                            "last_attempt_at": now_iso(),
                        },
                    },
                    silent=True,
                )
            )
            raise
        products = summarize_products(detail.feature)
        enrichment: dict[str, Any] = {
            "fetched_at": now_iso(),
            "last_attempt_at": now_iso(),
            "last_error": None,
            "products": products,
            "source_request": detail.request.as_dict(),
        }
        run_in_transaction(
            self.db,
            lambda txn: txn.collection(s.EVENTS).update(
                {"_key": event_key, "enrichment": enrichment}, silent=True
            ),
            write=[s.EVENTS],
        )
        self.runs.finish_run(
            run_id,
            status="succeeded",
            counts={"products": len(products)},
            requests=[detail.request.as_dict()],
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return enrichment


def enrichment_is_stale(event: dict[str, Any], *, max_age: timedelta) -> bool:
    enrichment = event.get("enrichment") or {}
    fetched = enrichment.get("fetched_at")
    if not fetched:
        return True
    return bool(utc_now() - from_iso(fetched) > max_age)
