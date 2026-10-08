"""Run the periodic scheduler (replaces ``celery beat``); several may run safely at once."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.jobs.scheduler import Scheduler


class Command(BaseCommand):
    help = "Enqueue periodic jobs (settings.JOBS_SCHEDULE) until SIGTERM/SIGINT."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--poll-seconds", type=float, default=1.0)
        parser.add_argument("--once", action="store_true", help="check every entry once, exit")

    def handle(self, *args: Any, **options: Any) -> None:
        scheduler = Scheduler(poll_seconds=options["poll_seconds"])
        if options["once"]:
            ids = scheduler.tick()
            self.stdout.write(f"enqueued {len(ids)} job(s): {', '.join(ids) or '-'}")
            return
        scheduler.install_signal_handlers()
        scheduler.run()
