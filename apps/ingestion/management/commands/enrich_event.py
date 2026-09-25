from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.arango.client import get_db
from apps.core.errors import QuakeWatchError
from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.services import EnrichmentService


class Command(BaseCommand):
    help = "Fetch USGS detail-feed product summaries for one event (lazy enrichment)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("event_key", help="canonical event key, e.g. usgs_us7000abcd")

    def handle(self, *args: Any, **options: Any) -> None:
        client = build_usgs_client()
        try:
            enrichment = EnrichmentService(get_db(), client).enrich(options["event_key"])
        except QuakeWatchError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            client.close()
        self.stdout.write(json.dumps(enrichment["products"], indent=2))
