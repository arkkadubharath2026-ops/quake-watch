"""Inspect and operate the job queue: ``stats``, ``list [--status S]``, ``requeue JOB_ID``."""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.arango.client import get_db
from apps.jobs import domain as d
from apps.jobs.repository import JobRepository


class Command(BaseCommand):
    help = "Job queue statistics, recent jobs, and re-queueing of dead/failed jobs."

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest="action", required=True)
        sub.add_parser("stats", help="job counts per task and status")
        listing = sub.add_parser("list", help="most recent jobs")
        listing.add_argument("--status", choices=d.STATUSES)
        listing.add_argument("--limit", type=int, default=20)
        requeue = sub.add_parser("requeue", help="give a dead or failed job fresh attempts")
        requeue.add_argument("job_id")

    def handle(self, *args: Any, **options: Any) -> None:
        repo = JobRepository(get_db())
        action = options["action"]
        if action == "stats":
            for row in sorted(repo.stats(), key=lambda r: (r["task"], r["status"])):
                self.stdout.write(f"{row['task']:<28} {row['status']:<10} {row['n']}")
        elif action == "list":
            for job in repo.recent(status=options["status"], limit=options["limit"]):
                summary = {k: job.get(k) for k in ("_key", "task", "status", "attempts")}
                summary["last_error"] = (job.get("last_error") or {}).get("message")
                self.stdout.write(json.dumps(summary, default=str))
        else:
            requeued = repo.requeue(options["job_id"])
            if requeued is None:
                raise CommandError(f"job {options['job_id']} is not dead/failed (or not found)")
            self.stdout.write(f"re-queued {requeued['_key']} ({requeued['task']})")
