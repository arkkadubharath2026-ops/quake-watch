"""Celery tasks for ingestion (ESD §13 reliability).

* ``sync_feed`` — soft/hard timeout 240/300 s. No task-level retry: the HTTP adapter already
  retries transient failures with backoff and the next beat tick is the retry. A Redis lock per
  feed prevents overlapping runs; the pipeline is idempotent.
* ``run_backfill`` — 840/900 s, processes at most ``BACKFILL_WINDOWS_PER_TASK`` windows then
  re-enqueues itself. Up to 10 retries on transient upstream failure with exponential backoff
  (honours Retry-After, capped at 30 min). Lock per job; checkpoint per window.
* ``enrich_event`` — 60/90 s, up to 3 transient retries, rate limited; skipped when fresh.
* ``recover`` — every 10 min: marks abandoned runs, re-queues stalled or idle pending backfills.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from celery import Task, shared_task

from apps.core.arango.client import get_db
from apps.core.clock import to_iso, utc_now
from apps.core.errors import CircuitOpen, NotFound
from apps.core.locks import job_lock
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
from config.env import get_settings
from config.logging import get_logger

log = get_logger(__name__)

BACKFILL_WINDOWS_PER_TASK = 12
ENRICHMENT_MAX_AGE = timedelta(minutes=30)


@shared_task(name="ingestion.sync_feed", soft_time_limit=240, time_limit=300)
def sync_feed(feed: str | None = None) -> dict[str, Any]:
    feed_name = feed or get_settings().sync_feed
    with job_lock(f"sync:{feed_name}", ttl_seconds=600) as acquired:
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
    for key in result.important_keys:
        enrich_event.delay(key)
    return {"run_id": result.run_id, "status": result.status, "counts": result.counts}


@shared_task(
    bind=True,
    name="ingestion.run_backfill",
    soft_time_limit=840,
    time_limit=900,
    max_retries=10,
)
def run_backfill(self: Task, job_id: str) -> dict[str, Any]:
    with job_lock(f"backfill:{job_id}", ttl_seconds=1200) as acquired:
        if not acquired:
            return {"status": "skipped_locked"}
        client = build_usgs_client()
        try:
            job = BackfillService(get_db(), client).run_job(
                job_id, max_windows=BACKFILL_WINDOWS_PER_TASK
            )
        except BackfillInterrupted as exc:
            countdown = backoff_delay(
                self.request.retries + 1, base=30, cap=1800, retry_after=exc.retry_after
            )
            log.warning("backfill_retry_scheduled", backfill_job_id=job_id, countdown_s=countdown)
            raise self.retry(exc=exc, countdown=countdown) from exc
        finally:
            client.close()
    if job.get("status") == "pending":
        run_backfill.delay(job_id)  # continue with the next batch of windows
    return {"job_id": job_id, "status": job.get("status")}


@shared_task(
    bind=True,
    name="ingestion.enrich_event",
    soft_time_limit=60,
    time_limit=90,
    max_retries=3,
    rate_limit="30/m",
)
def enrich_event(self: Task, event_key: str, force: bool = False) -> dict[str, Any]:
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
                self.request.retries + 1, base=20, cap=600, retry_after=exc.retry_after_seconds
            )
            raise self.retry(exc=exc, countdown=countdown) from exc
        return {"status": "failed", "error": str(exc)}
    except NotFound:
        return {"status": "not_found"}
    finally:
        client.close()
    return {"status": "enriched"}


@shared_task(name="ingestion.recover", soft_time_limit=60, time_limit=90)
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
