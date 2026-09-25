from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.core.arango.client import ensure_database
from apps.core.arango.migrate import apply_schema


class Command(BaseCommand):
    help = "Create/reconcile ArangoDB database, collections, indexes, view and graph (idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--keep-undeclared-indexes",
            action="store_true",
            help="Do not drop qw_* indexes that are no longer declared (used by benchmarks).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        db = ensure_database()
        report = apply_schema(db, drop_undeclared_indexes=not options["keep_undeclared_indexes"])
        if not report.changed:
            self.stdout.write(self.style.SUCCESS(f"ArangoDB schema up to date ({db.name})."))
            return
        for label, items in (
            ("collections created", report.created_collections),
            ("indexes created", report.created_indexes),
            ("indexes replaced", report.replaced_indexes),
            ("indexes dropped", report.dropped_indexes),
            ("data migrations", report.data_migrations),
        ):
            if items:
                self.stdout.write(f"{label}: {', '.join(items)}")
        self.stdout.write(f"view: {report.view}; graph: {report.graph}")
        self.stdout.write(self.style.SUCCESS(f"ArangoDB schema applied to {db.name}."))
