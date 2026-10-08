"""Run a job worker (replaces ``celery worker``; ``--with-scheduler`` also replaces beat)."""

from __future__ import annotations

import multiprocessing
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.jobs.scheduler import Scheduler
from apps.jobs.worker import Worker, WorkerConfig


def _run_scheduler() -> None:
    scheduler = Scheduler()
    scheduler.install_signal_handlers()
    scheduler.run()


class Command(BaseCommand):
    help = "Process background jobs from the ArangoDB queue until SIGTERM/SIGINT."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--concurrency", type=int, default=2, help="jobs run in parallel")
        parser.add_argument("--lease-seconds", type=float, default=60.0)
        parser.add_argument("--heartbeat-seconds", type=float, default=15.0)
        parser.add_argument("--poll-seconds", type=float, default=1.0)
        parser.add_argument("--shutdown-grace", type=float, default=25.0)
        parser.add_argument("--task", action="append", dest="tasks", help="only these tasks")
        parser.add_argument(
            "--with-scheduler",
            action="store_true",
            help="also run the periodic scheduler (in a separate child process)",
        )
        parser.add_argument("--max-jobs", type=int, default=None, help="exit after N jobs")
        parser.add_argument("--idle-exit", type=float, default=None, help="exit when idle N s")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["concurrency"] < 1:
            raise ValueError("--concurrency must be at least 1")
        config = WorkerConfig(
            concurrency=options["concurrency"],
            lease_seconds=options["lease_seconds"],
            heartbeat_seconds=options["heartbeat_seconds"],
            poll_seconds=options["poll_seconds"],
            shutdown_grace=options["shutdown_grace"],
            tasks=frozenset(options["tasks"]) if options["tasks"] else None,
        )
        scheduler = None
        if options["with_scheduler"]:
            # A process, not a thread: the worker forks per job and must stay single-threaded.
            scheduler = multiprocessing.get_context("fork").Process(
                target=_run_scheduler, name="scheduler", daemon=True
            )
            scheduler.start()
        worker = Worker(config)
        worker.install_signal_handlers()
        try:
            processed = worker.run(max_jobs=options["max_jobs"], idle_exit=options["idle_exit"])
        finally:
            if scheduler is not None and scheduler.is_alive():
                scheduler.terminate()
                scheduler.join(timeout=10)
        self.stdout.write(f"worker stopped after {processed} job(s)")
