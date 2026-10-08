from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.arango.client import get_db
from apps.core.errors import QuakeWatchError
from apps.core.locks import describe_holder, job_lease
from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.services import BackfillInterrupted, BackfillRequest, BackfillService
from apps.ingestion.tasks import BACKFILL_LEASE_TTL_SECONDS, backfill_lease_name


def _date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"invalid date {value!r}; use YYYY-MM-DD or ISO-8601") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class Command(BaseCommand):
    help = "Bounded, checkpointed historical backfill from the USGS FDSN catalog."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start", type=_date, help="inclusive start (UTC)")
        parser.add_argument("--end", type=_date, help="exclusive end (UTC)")
        parser.add_argument("--min-magnitude", type=float, default=None)
        parser.add_argument("--window-days", type=int, default=7)
        parser.add_argument("--resume", metavar="JOB_ID", help="resume an existing job")
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="queue the job for a worker instead of running here",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        db = get_db()
        client = build_usgs_client()
        service = BackfillService(db, client)
        try:
            job_id = options["resume"] or self._create(service, options)
            if options["enqueue"]:
                from apps.ingestion.tasks import run_backfill

                run_backfill.delay(job_id)
                self.stdout.write(self.style.SUCCESS(f"backfill job {job_id} enqueued"))
                return
            job: dict[str, Any] = {}
            name = backfill_lease_name(job_id)
            while True:
                # Same lease as the queued job (P2), taken per window — the task's unit of work —
                # so a long CLI run needs no renewal and never overlaps a task on this job.
                # LockUnavailable is a QuakeWatchError: reported below, nothing runs (P1).
                with job_lease(name, ttl_seconds=BACKFILL_LEASE_TTL_SECONDS) as lease:
                    if lease is None:
                        raise CommandError(
                            f"backfill job {job_id} is already running ({describe_holder(name)}); "
                            f"resume later with --resume {job_id}"
                        )
                    job = service.run_job(job_id, max_windows=1)
                self.stdout.write(
                    f"  window {job.get('windows_completed')} done -> next "
                    f"{job.get('next_window_start')} counts={job.get('counts')}"
                )
                if job.get("status") != "pending":
                    break
        except BackfillInterrupted as exc:
            raise CommandError(
                f"interrupted by transient upstream failure; resume with --resume {exc.job_id}"
            ) from exc
        except QuakeWatchError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            client.close()
        self.stdout.write(json.dumps(job.get("counts", {}), indent=2))
        self.stdout.write(self.style.SUCCESS(f"backfill job {job_id}: {job.get('status')}"))

    def _create(self, service: BackfillService, options: dict[str, Any]) -> str:
        if not options["start"] or not options["end"]:
            raise CommandError("--start and --end are required unless --resume is given")
        return service.create_job(
            BackfillRequest(
                start=options["start"],
                end=options["end"],
                min_magnitude=options["min_magnitude"],
                window_days=options["window_days"],
                requested_by="cli",
            )
        )
