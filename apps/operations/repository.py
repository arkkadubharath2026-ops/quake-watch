"""Operations read models: runs, freshness inputs, dead letters, collection counts."""

from __future__ import annotations

from typing import Any

from arango.database import Database

from apps.core.arango import catalog
from apps.core.arango import schema as s
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.client import sync, sync_optional
from apps.core.arango.query import run_query

LATEST_RUN = catalog.register(
    NamedQuery(
        name="ops_latest_run",
        category="operations",
        question="Latest ingestion run of a kind, optionally only successful ones (freshness).",
        aql="""
        FOR r IN ingestion_runs OPTIONS {indexHint: "qw_runs_kind_started"}
          FILTER r.kind == @kind AND (@status == null OR r.status IN @statuses)
          SORT r.kind DESC, r.started_at DESC
          LIMIT 1
          RETURN UNSET(r, "_id", "_rev")
        """,
        sample_binds=lambda: {"kind": "feed_sync", "status": "ok", "statuses": ["succeeded"]},
        expected_indexes=("qw_runs_kind_started",),
        features=("composite index", "sort"),
    )
)

RECENT_RUNS = catalog.register(
    NamedQuery(
        name="ops_recent_runs",
        category="operations",
        question="Recent ingestion runs (sync history, job durations, failures).",
        aql="""
        FOR r IN ingestion_runs
          FILTER @kind == null OR r.kind == @kind
          FILTER @status == null OR r.status == @status
          SORT r.started_at DESC
          LIMIT @offset, @limit
          RETURN KEEP(r, "_key", "kind", "status", "started_at", "finished_at", "duration_ms",
                      "counts", "error", "params", "correlation_id", "source_generated_at")
        """,
        sample_binds=lambda: {"kind": None, "status": None, "offset": 0, "limit": 25},
        expected_indexes=("qw_runs_started_at",),
        features=("sort", "pagination"),
    )
)

RUN_STATS = catalog.register(
    NamedQuery(
        name="ops_run_stats",
        category="operations",
        question="Run outcomes and durations per kind since a timestamp (success rate, p95).",
        aql="""
        FOR r IN ingestion_runs
          FILTER r.started_at >= @since
          COLLECT kind = r.kind INTO runs = r
          LET durations = runs[* FILTER CURRENT.duration_ms != null RETURN CURRENT.duration_ms]
          RETURN {
            kind: kind,
            total: LENGTH(runs),
            by_status: MERGE(FOR st IN UNIQUE(runs[*].status)
                               RETURN {[st]: LENGTH(runs[* FILTER CURRENT.status == st])}),
            p50_ms: LENGTH(durations) == 0 ? null : PERCENTILE(durations, 50),
            p95_ms: LENGTH(durations) == 0 ? null : PERCENTILE(durations, 95)
          }
        """,
        sample_binds=lambda: {"since": "2026-09-01T00:00:00.000Z"},
        expected_indexes=("qw_runs_started_at", "qw_runs_kind_started"),
        features=("aggregation", "percentiles", "array operators"),
    )
)

DEAD_LETTERS = catalog.register(
    NamedQuery(
        name="ops_dead_letters",
        category="operations",
        question="Rejected / failing source records, most recent failure first.",
        aql="""
        FOR d IN dead_letters
          FILTER @unresolved == false OR d.resolved_at == null
          SORT d.last_failure_at DESC
          LIMIT @offset, @limit
          RETURN UNSET(d, "_id", "_rev", "payload")
        """,
        sample_binds=lambda: {"unresolved": True, "offset": 0, "limit": 25},
        expected_indexes=("qw_dead_last_failure",),
        features=("sort", "pagination"),
    )
)


class OperationsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def latest_run(self, kind: str, *, statuses: list[str] | None = None) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            LATEST_RUN.name,
            LATEST_RUN.aql,
            {"kind": kind, "status": "any" if statuses else None, "statuses": statuses or []},
        ).rows
        return rows[0] if rows else None

    def recent_runs(
        self, *, kind: str | None, status: str | None, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        result = run_query(
            self.db,
            RECENT_RUNS.name,
            RECENT_RUNS.aql,
            {"kind": kind, "status": status, "offset": offset, "limit": limit},
            full_count=True,
        )
        return result.rows, int(result.full_count or 0)

    def run_stats(self, since: str) -> list[dict[str, Any]]:
        return run_query(self.db, RUN_STATS.name, RUN_STATS.aql, {"since": since}).rows

    def dead_letters(
        self, *, unresolved_only: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        result = run_query(
            self.db,
            DEAD_LETTERS.name,
            DEAD_LETTERS.aql,
            {"unresolved": unresolved_only, "offset": offset, "limit": limit},
            full_count=True,
        )
        return result.rows, int(result.full_count or 0)

    def collection_counts(self) -> dict[str, int]:
        return {
            spec.name: int(sync(self.db.collection(spec.name).count()))
            for spec in s.COLLECTIONS
            if spec.name != s.SCHEMA_META
        }


AUDIT_RECENT = catalog.register(
    NamedQuery(
        name="ops_audit_recent",
        category="operations",
        question="Audit trail of privileged actions, newest first (FR-15).",
        aql="""
        FOR a IN audit_log
          FILTER @action == null OR a.action == @action
          SORT a.at DESC
          LIMIT @offset, @limit
          RETURN UNSET(a, "_id", "_rev")
        """,
        sample_binds=lambda: {"action": None, "offset": 0, "limit": 25},
        expected_indexes=("qw_audit_at",),
        features=("sort", "pagination"),
    )
)

BACKFILL_JOBS = catalog.register(
    NamedQuery(
        name="ops_backfill_jobs",
        category="operations",
        question="Backfill jobs with checkpoint progress.",
        aql="""
        FOR j IN backfill_jobs
          SORT j.created_at DESC
          LIMIT @limit
          RETURN UNSET(j, "_id", "_rev")
        """,
        sample_binds=lambda: {"limit": 25},
        features=("sort",),
    )
)


class AuditRepository:
    """Append-only audit trail. There is intentionally no update or delete method."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, entry: dict[str, Any]) -> None:
        sync(self.db.collection(s.AUDIT_LOG).insert(entry, silent=True))

    def recent(
        self, *, action: str | None, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        result = run_query(
            self.db,
            AUDIT_RECENT.name,
            AUDIT_RECENT.aql,
            {"action": action, "offset": offset, "limit": limit},
            full_count=True,
        )
        return result.rows, int(result.full_count or 0)

    def backfill_jobs(self, *, limit: int = 25) -> list[dict[str, Any]]:
        return run_query(self.db, BACKFILL_JOBS.name, BACKFILL_JOBS.aql, {"limit": limit}).rows

    def dead_letter(self, key: str) -> dict[str, Any] | None:
        doc = sync_optional(self.db.collection(s.DEAD_LETTERS).get(key))
        return doc if isinstance(doc, dict) else None
