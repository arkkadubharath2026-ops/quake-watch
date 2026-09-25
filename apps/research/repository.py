"""Research snapshot persistence: freeze (pin revisions), reconstruct rows, provenance, CRUD."""

from __future__ import annotations

from typing import Any

from arango.database import Database

from apps.core.arango import catalog
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.query import run_query
from apps.core.arango.transactions import exclusive_query
from apps.earthquakes.filters import EventFilter
from apps.earthquakes.repository import compile_filter
from apps.ingestion.repository import revision_key

RECONSTRUCT_CHUNK = 2000
SUMMARY_FIELDS = (
    "title", "notes", "created_at", "row_count", "content_sha256", "query_definition",
    "application_version",
)  # fmt: skip

REVISION_ROWS = catalog.register(
    NamedQuery(
        name="research_rows_from_revisions",
        category="research",
        question="Reconstruct a frozen dataset from immutable revision snapshots "
        "(primary-key lookups of pinned revisions).",
        aql="""
        FOR k IN @keys
          LET r = DOCUMENT("event_revisions", k)
          RETURN r == null ? {missing: k}
               : {event_key: r.event_key, revision_number: r.revision_number, state: r.state,
                  payload_hash: r.payload_hash, ingestion_run_id: r.ingestion_run_id}
        """,
        sample_binds=lambda: {"keys": ["usgs_x_000001"]},
        features=("primary-key lookup", "revision reconstruction"),
    )
)

USER_SNAPSHOTS = catalog.register(
    NamedQuery(
        name="research_user_snapshots",
        category="research",
        question="A user's research snapshots (without member lists).",
        aql="""
        FOR s IN research_snapshots
          FILTER s.user_id == @user_id
          SORT s.user_id DESC, s.created_at DESC
          RETURN MERGE(KEEP(s, @fields), {id: s._key})
        """,
        sample_binds=lambda: {"user_id": 1, "fields": list(SUMMARY_FIELDS)},
        expected_indexes=("qw_snapshots_user",),
        features=("composite index", "projection"),
    )
)


class ResearchRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def freeze_members(self, f: EventFilter, *, limit: int) -> list[list[Any]]:
        """``[[event_key, revision_number], ...]`` for matching live events, capped at limit+1."""
        compiled = compile_filter(f)
        aql = (
            f"{compiled.body()}\n"
            "  SORT e.occurred_at ASC, e._key ASC\n"
            "  LIMIT @limit\n"
            "  RETURN [e._key, e.revision_count]"
        )
        binds = {**compiled.binds, "limit": limit + 1}
        return run_query(self.db, "research_freeze_members", aql, binds, max_runtime=120).rows

    def pinned_revisions(self, members: list[list[Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        keys = [revision_key(key, int(number)) for key, number in members]
        for start in range(0, len(keys), RECONSTRUCT_CHUNK):
            chunk = keys[start : start + RECONSTRUCT_CHUNK]
            rows.extend(
                run_query(self.db, REVISION_ROWS.name, REVISION_ROWS.aql, {"keys": chunk}).rows
            )
        return rows

    def source_requests(self, run_ids: list[str]) -> list[dict[str, Any]]:
        """Request provenance of the ingestion runs that produced the pinned revisions."""
        if not run_ids:
            return []
        return run_query(
            self.db,
            "research_source_requests",
            """
            FOR id IN @ids
              LET r = DOCUMENT("ingestion_runs", id)
              FILTER r != null
              SORT r.started_at
              RETURN {run_id: r._key, kind: r.kind, started_at: r.started_at,
                      requests: r.requests[* RETURN KEEP(CURRENT, "url", "params",
                        "requested_at", "status_code", "response_sha256", "response_bytes")]}
            """,
            {"ids": run_ids},
        ).rows

    def insert_capped(self, doc: dict[str, Any], *, max_per_user: int) -> bool:
        """Insert unless the owner already has ``max_per_user`` snapshots (serialised)."""
        rows = exclusive_query(
            self.db,
            "research_insert_capped",
            """
            LET existing = LENGTH(FOR s IN research_snapshots FILTER s.user_id == @uid RETURN 1)
            FILTER existing < @max
            INSERT @doc INTO research_snapshots
            RETURN 1
            """,
            {"uid": doc["user_id"], "max": max_per_user, "doc": doc},
            exclusive=["research_snapshots"],
        )
        return bool(rows)

    def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        return run_query(
            self.db,
            USER_SNAPSHOTS.name,
            USER_SNAPSHOTS.aql,
            {"user_id": user_id, "fields": list(SUMMARY_FIELDS)},
        ).rows

    def get(self, user_id: int, snapshot_id: str) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            "research_get_snapshot",
            """
            LET s = DOCUMENT("research_snapshots", @id)
            FILTER s != null AND s.user_id == @uid
            RETURN s
            """,
            {"id": snapshot_id, "uid": user_id},
        ).rows
        return rows[0] if rows else None

    def delete(self, user_id: int, snapshot_id: str) -> bool:
        rows = run_query(
            self.db,
            "research_delete_snapshot",
            """
            LET s = DOCUMENT("research_snapshots", @id)
            FILTER s != null AND s.user_id == @uid
            REMOVE s IN research_snapshots
            RETURN 1
            """,
            {"id": snapshot_id, "uid": user_id},
        ).rows
        return bool(rows)
