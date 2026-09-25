from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.arango.client import get_db
from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.observers import configured_observers
from apps.ingestion.services import FeedSyncService
from config.env import get_settings


class Command(BaseCommand):
    help = "Synchronise a USGS summary feed now (same code path as the scheduled Celery task)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--feed", default=None, help="e.g. all_day, 2.5_week (default: config)")

    def handle(self, *args: Any, **options: Any) -> None:
        feed = options["feed"] or get_settings().sync_feed
        client = build_usgs_client()
        try:
            result = FeedSyncService(get_db(), client, observers=configured_observers()).run(feed)
        finally:
            client.close()
        self.stdout.write(json.dumps({"run_id": result.run_id, "counts": result.counts}, indent=2))
        if result.status in ("failed", "skipped"):
            raise CommandError(f"sync {result.status}: {result.error}")
        self.stdout.write(self.style.SUCCESS(f"sync {result.status} ({feed})"))
