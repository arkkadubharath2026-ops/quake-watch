"""Ingestion background jobs (ESD §13 reliability), run by the ArangoDB job queue (apps.jobs).

* ``sync_feed`` — soft/hard timeout 240/300 s. No task-level retry: the HTTP adapter already
  retries transient failures with backoff and the next scheduled tick is the retry. An ArangoDB
  lease per feed prevents overlapping runs (fail closed: skipped when the lease store is
  unreachable); the pipeline is idempotent.
* ``run_backfill`` — 840/900 s, processes at most ``BACKFILL_WINDOWS_PER_TASK`` windows then
  re-enqueues itself. Up to 10 retries on transient upstream failure with exponential backoff
  (honours Retry-After, capped at 30 min), then dead-lettered. Lease per job; checkpoint per window.
  At most one queued run per backfill job (dedupe).
* ``enrich_event`` — 60/90 s, up to 3 transient retries, rate limited; skipped when fresh;
  at most one queued enrichment per event.
* ``recover`` — every 10 min: marks abandoned runs, re-queues stalled or idle pending backfills.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from apps.core.arango.client import get_db
from apps.core.clock import to_iso, utc_now
from apps.core.errors import CircuitOpen, NotFound
from apps.core.locks import LockUnavailable, job_lock
from apps.core.resilience import backoff_delay
from apps.ingestion.adapters.http import UpstreamRequestFailed
from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.observers import configured_observers
from apps.ingestion.repository import RunRepository
from apps.ingestion.services import (
    BackfillInterrupted,
    BackfillService,
    EnrichmentService,
    FeedSyncService,
    enrichment_is_stale,
)
from apps.jobs import Retry, current_job, task
from config.env import get_settings
from config.logging import get_logger

log = get_logger(__name__)

BACKFILL_WINDOWS_PER_TASK = 12
# Lease TTLs must exceed each task's hard time limit, so a live task can never outlive its lease
# (tests/unit/test_job_lock.py enforces this).
SYNC_LEASE_TTL_SECONDS = 600
BACKFILL_LEASE_TTL_SECONDS = 1200


def sync_lease_name(feed: str) -> str:
    """Lease shared by the scheduled task and `manage.py sync_feed` (decision P2)."""
    return f"sync:{feed}"


def backfill_lease_name(job_id: str) -> str:
    """Lease shared by the backfill task and `manage.py backfill` (decision P2)."""
    return f"backfill:{job_id}"


ENRICHMENT_MAX_AGE = timedelta(minutes=30)


@task(
    name="ingestion.sync_feed",
    soft_time_limit=240,
    time_limit=300,
    dedupe=lambda feed=None: feed or "default",
)
def sync_feed(feed: str | None = None) -> dict[str, Any]:
    feed_name = feed or get_settings().sync_feed
    try:
        with job_lock(sync_lease_name(feed_name), ttl_seconds=SYNC_LEASE_TTL_SECONDS) as acquired:
            if not acquired:
                log.info("sync_skipped_already_running", feed=feed_name)
                return {"status": "skipped_locked"}
            client = build_usgs_client()
            try:
                result = FeedSyncService(get_db(), client, observers=configured_observers()).run(
                    feed_name
                )
            finally:
                client.close()
    except LockUnavailable as exc:  # fail closed (P1): never sync without the lease
        log.error("sync_skipped_lock_unavailable", feed=feed_name, error=str(exc))
        return {"status": "skipped_lock_unavailable"}
    for key in result.important_keys:
        enrich_event.delay(key)
    return {"run_id": result.run_id, "status": result.status, "counts": result.counts}


@task(
    name="ingestion.run_backfill",
    soft_time_limit=840,
    time_limit=900,
    max_retries=10,
    dedupe=lambda job_id: job_id,
)
def run_backfill(job_id: str) -> dict[str, Any]:
    try:
        with job_lock(
            backfill_lease_name(job_id), ttl_seconds=BACKFILL_LEASE_TTL_SECONDS
        ) as acquired:
            if not acquired:
                return {"status": "skipped_locked"}
            client = build_usgs_client()
            try:
                job = BackfillService(get_db(), client).run_job(
                    job_id, max_windows=BACKFILL_WINDOWS_PER_TASK
                )
            except BackfillInterrupted as exc:
                countdown = backoff_delay(
                    current_job().retries + 1, base=30, cap=1800, retry_after=exc.retry_after
                )
                log.warning(
                    "backfill_retry_scheduled", backfill_job_id=job_id, countdown_s=countdown
                )
                raise Retry(countdown, exc) from exc
            finally:
                client.close()
    except LockUnavailable as exc:  # fail closed (P1); `recover` resumes the job later
        log.error("backfill_skipped_lock_unavailable", backfill_job_id=job_id, error=str(exc))
        return {"job_id": job_id, "status": "skipped_lock_unavailable"}
    if job.get("status") == "pending":
        run_backfill.delay(job_id)  # continue with the next batch of windows
    return {"job_id": job_id, "status": job.get("status")}


@task(
    name="ingestion.enrich_event",
    soft_time_limit=60,
    time_limit=90,
    max_retries=3,
    rate_limit="30/m",
    dedupe=lambda event_key, force=False: f"{event_key}:{'force' if force else 'stale'}",
)
def enrich_event(event_key: str, force: bool = False) -> dict[str, Any]:
    db = get_db()
    event = db.collection("events").get(event_key)
    if not isinstance(event, dict):
        return {"status": "not_found"}
    if not force and not enrichment_is_stale(event, max_age=ENRICHMENT_MAX_AGE):
        return {"status": "fresh"}
    client = build_usgs_client()
    try:
        EnrichmentService(db, client).enrich(event_key)
    except (UpstreamRequestFailed, CircuitOpen) as exc:
        if exc.transient:
            countdown = backoff_delay(
                current_job().retries + 1, base=20, cap=600, retry_after=exc.retry_after_seconds
            )
            raise Retry(countdown, exc) from exc
        return {"status": "failed", "error": str(exc)}
    except NotFound:
        return {"status": "not_found"}
    finally:
        client.close()
    return {"status": "enriched"}


@task(name="ingestion.recover", soft_time_limit=60, time_limit=90, dedupe=lambda: "recover")
def recover() -> dict[str, Any]:
    db = get_db()
    abandoned = RunRepository(db).abandon_stale_runs(older_than=timedelta(hours=1))
    client = build_usgs_client()
    try:
        requeued = BackfillService(db, client).recover_stalled()
    finally:
        client.close()
    for job_id in requeued:
        run_backfill.delay(job_id)
    idle_threshold = to_iso(utc_now() - timedelta(minutes=30))  # > max retry countdown
    pending = [
        j["_key"]
        for j in RunRepository(db).active_backfill_jobs()
        if j["status"] == "pending" and j["updated_at"] < idle_threshold
    ]
    for job_id in pending:
        if job_id not in requeued:
            run_backfill.delay(job_id)
    if abandoned or requeued:
        log.warning("ingestion_recovery", abandoned_runs=abandoned, requeued_jobs=requeued)
    return {"abandoned_runs": abandoned, "requeued_jobs": requeued, "resumed": pending}
