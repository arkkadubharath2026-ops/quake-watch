from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.arango.client import get_db
from apps.core.locks import LockUnavailable, describe_holder, job_lease
from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.observers import configured_observers
from apps.ingestion.services import FeedSyncService
from apps.ingestion.tasks import SYNC_LEASE_TTL_SECONDS, sync_lease_name
from config.env import get_settings


class Command(BaseCommand):
    help = "Synchronise a USGS summary feed now (same code path as the scheduled job)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--feed", default=None, help="e.g. all_day, 2.5_week (default: config)")

    def handle(self, *args: Any, **options: Any) -> None:
        feed = options["feed"] or get_settings().sync_feed
        name = sync_lease_name(feed)
        try:
            # Same lease as the scheduled task (P2): never sync a feed twice concurrently.
            with job_lease(name, ttl_seconds=SYNC_LEASE_TTL_SECONDS) as lease:
                if lease is None:
                    raise CommandError(
                        f"sync of {feed} is already running ({describe_holder(name)}); "
                        "not starting a second run"
                    )
                client = build_usgs_client()
                try:
                    result = FeedSyncService(
                        get_db(), client, observers=configured_observers()
                    ).run(feed)
                finally:
                    client.close()
        except LockUnavailable as exc:  # fail closed (P1): never sync without the lease
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps({"run_id": result.run_id, "counts": result.counts}, indent=2))
        if result.status in ("failed", "skipped"):
            raise CommandError(f"sync {result.status}: {result.error}")
        self.stdout.write(self.style.SUCCESS(f"sync {result.status} ({feed})"))
