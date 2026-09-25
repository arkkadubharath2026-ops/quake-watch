"""Write-path persistence for ingestion: events, revisions, raw payloads, graph, runs, dead letters.

Every method accepts either the standard database or a stream-transaction handle (both are
:class:`Database`), so the pipeline decides the transactional scope. All AQL uses bind variables.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from arango.database import Database

from apps.core.arango import catalog
from apps.core.arango import schema as s
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.client import sync, sync_optional
from apps.core.arango.query import run_query
from apps.core.clock import now_iso, to_iso, utc_now
from apps.geo.regions import DerivedRegion
from apps.ingestion.networks import network_name

REPOINT_CLAIMS = catalog.register(
    NamedQuery(
        name="ingest_repoint_claims",
        category="maintenance",
        question="On merge, move every identity claim of the absorbed record to the survivor.",
        aql="""
        FOR c IN event_identities FILTER c.event_key == @loser
          UPDATE c WITH {event_key: @primary, claimed_at: @at} IN event_identities
        """,
        sample_binds=lambda: {"loser": "usgs_x", "primary": "usgs_y", "at": "2026-01-01"},
        expected_indexes=("qw_identities_event_key",),
        features=("update", "persistent index"),
        read_only=False,
    )
)

RESOLVE_DEAD_LETTERS = catalog.register(
    NamedQuery(
        name="ingest_resolve_dead_letters",
        category="maintenance",
        question="Mark dead letters resolved once their record ingests successfully.",
        aql="""
        FOR d IN dead_letters
          FILTER d.source == @source AND d.source_event_id IN @ids
          FILTER d.resolved_at == null
          UPDATE d WITH {resolved_at: @at} IN dead_letters
          RETURN 1
        """,
        sample_binds=lambda: {"source": "USGS", "ids": ["x"], "at": "2026-01-01"},
        expected_indexes=("qw_dead_source_event",),
        features=("update", "composite index"),
        read_only=False,
    )
)

ABANDON_STALE_RUNS = catalog.register(
    NamedQuery(
        name="runs_abandon_stale",
        category="maintenance",
        question="Recovery: runs left 'running' by a dead worker become 'abandoned'.",
        aql="""
        FOR r IN ingestion_runs
          FILTER r.status == "running" AND r.started_at < @threshold
          UPDATE r WITH {status: "abandoned", finished_at: @now,
                         error: {type: "Abandoned", message: "no completion recorded"}}
          IN ingestion_runs
          RETURN 1
        """,
        sample_binds=lambda: {"threshold": "2026-01-01", "now": "2026-01-01"},
        expected_indexes=("qw_runs_status", "qw_runs_started_at"),
        features=("update", "recovery"),
        read_only=False,
    )
)


ACTIVE_BACKFILL_JOBS = catalog.register(
    NamedQuery(
        name="backfill_active_jobs",
        category="maintenance",
        question="Backfill jobs still pending or running (recovery task resumes them).",
        aql="""
        FOR j IN backfill_jobs
          FILTER j.status IN ["pending", "running"]
          SORT j.created_at
          RETURN j
        """,
        sample_binds=lambda: {},
        expected_indexes=("qw_backfill_status",),
        features=("persistent index", "recovery"),
    )
)


@dataclass(frozen=True, slots=True)
class EventWrite:
    """Everything one ingested record writes (see :meth:`IngestionRepository.apply_write`)."""

    event: dict[str, Any]
    is_new: bool
    source: str
    claim_ids: Sequence[str]
    raw: dict[str, Any]
    revision: dict[str, Any] | None = None
    region: DerivedRegion | None = None
    relink_region: bool = False
    network: str | None = None
    relink_network: bool = False


@dataclass(frozen=True, slots=True)
class KnownEvent:
    key: str
    source_event_id: str
    payload_hash: str
    source_updated_at: str


def revision_key(event_key: str, revision_number: int) -> str:
    return f"{event_key}_{revision_number:06d}"


def dead_letter_key(source: str, record_ref: str) -> str:
    return hashlib.sha256(f"{source}|{record_ref}".encode()).hexdigest()[:32]


class IngestionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---- identity ---------------------------------------------------------------------------
    def known_events(self, source: str, source_event_ids: Sequence[str]) -> dict[str, KnownEvent]:
        """Fast-path lookup (unique index) of current payload hashes by preferred id."""
        rows = run_query(
            self.db,
            "ingest_known_events",
            """
            FOR e IN events
              FILTER e.source == @source AND e.source_event_id IN @ids
              FILTER e.merged_into == null
              RETURN {key: e._key, id: e.source_event_id, hash: e.payload_hash,
                      updated: e.source_updated_at}
            """,
            {"source": source, "ids": list(source_event_ids)},
        ).rows
        return {r["id"]: KnownEvent(r["key"], r["id"], r["hash"], r["updated"]) for r in rows}

    def find_by_identity(self, source: str, ids: Sequence[str]) -> list[dict[str, Any]]:
        """Live canonical events claimed by any of ``ids`` (primary-key lookups only).

        Claims always point at live events (they are re-pointed on merge); following one
        ``merged_into`` hop is a defensive fallback.
        """
        return run_query(
            self.db,
            "ingest_find_by_identity",
            """
            LET keys = UNIQUE(
              FOR id IN @ids
                LET claim = DOCUMENT("event_identities", CONCAT(@prefix, id))
                FILTER claim != null
                RETURN claim.event_key
            )
            FOR k IN keys
              LET e = DOCUMENT("events", k)
              FILTER e != null
              LET live = e.merged_into == null ? e : DOCUMENT("events", e.merged_into)
              FILTER live != null AND live.merged_into == null
              COLLECT key = live._key INTO grouped = live
              RETURN FIRST(grouped)
            """,
            {"ids": list(ids), "prefix": f"{source.lower()}_"},
            record_metrics=False,
        ).rows

    def claim_identity(self, source: str, ids: Sequence[str], event_key: str) -> None:
        """Claim (or re-point) ids for an existing live event."""
        run_query(
            self.db,
            "ingest_claim_identity",
            """
            FOR id IN @ids
              UPSERT {_key: CONCAT(@prefix, id)}
              INSERT {_key: CONCAT(@prefix, id), source: @source, source_event_id: id,
                      event_key: @key, claimed_at: @at}
              UPDATE {event_key: @key, claimed_at: @at}
              IN event_identities
            """,
            {
                "ids": list(ids),
                "prefix": f"{source.lower()}_",
                "source": source,
                "key": event_key,
                "at": now_iso(),
            },
        )

    def absorb_merged(self, loser_key: str, primary_key: str, at: str) -> None:
        """Mark ``loser`` merged into ``primary`` and move everything identity-related over."""
        sync(
            self.db.collection(s.EVENTS).update(
                {"_key": loser_key, "merged_into": primary_key, "merged_at": at}, silent=True
            )
        )
        binds = {"loser": loser_key, "primary": primary_key, "at": at}
        # Separate statements: in AQL a second top-level FOR would nest inside the first.
        run_query(self.db, REPOINT_CLAIMS.name, REPOINT_CLAIMS.aql, binds)
        run_query(
            self.db,
            "ingest_repoint_merge_chain",
            """
            FOR e IN events FILTER e.merged_into == @loser
              UPDATE e WITH {merged_into: @primary} IN events
            """,
            {"loser": loser_key, "primary": primary_key},
        )
        for edge_collection in (s.EVENT_IN_REGION, s.EVENT_REPORTED_BY_NETWORK):
            run_query(
                self.db,
                "ingest_unlink_merged",
                "REMOVE {_key: @loser} IN @@edges OPTIONS {ignoreErrors: true}",
                {"loser": loser_key, "@edges": edge_collection},
            )

    # ---- consolidated write (one AQL statement per record) ------------------------------------
    def apply_write(self, w: EventWrite) -> None:
        """Execute every write for one record in a single multi-collection AQL statement.

        Each collection is modified at most once (AQL rule). New events claim ids with plain
        INSERTs so a concurrent writer of the same physical event fails with a conflict/unique
        violation and is retried by the caller's transaction loop (ADR-003).
        """
        claim_op = (
            "INSERT c INTO event_identities"
            if w.is_new
            else "UPSERT {_key: c._key} INSERT c "
            "UPDATE {event_key: c.event_key, claimed_at: c.claimed_at} IN event_identities"
        )
        event_op = "INSERT @event INTO events" if w.is_new else "REPLACE @event IN events"
        region_docs, region_edges, network_docs, network_edges = [], [], [], []
        key = w.event["_key"]
        if w.relink_region and w.region is not None:
            region_docs.append(
                {"_key": w.region.key, "name": w.region.name, "kind": w.region.kind,
                 "method_version": w.region.method_version}
            )  # fmt: skip
            region_edges.append(
                {"_key": key, "_from": f"events/{key}", "_to": f"regions/{w.region.key}"}
            )
        if w.relink_network and w.network:
            code = w.network.lower()
            network_docs.append({"_key": code, "code": code, "name": network_name(code)})
            network_edges.append({"_key": key, "_from": f"events/{key}", "_to": f"networks/{code}"})
        at = w.event["last_ingested_at"]
        run_query(
            self.db,
            "ingest_apply_write",
            f"""
            LET ev = ({event_op})
            LET claims = (FOR c IN @claims {claim_op})
            LET revision = (FOR r IN @revisions INSERT r INTO event_revisions)
            LET raw = (UPSERT {{_key: @raw._key}} INSERT @raw
                       UPDATE {{last_fetched_at: @raw.last_fetched_at, expires_at: @raw.expires_at}}
                       IN raw_payloads)
            LET region = (FOR r IN @regions UPSERT {{_key: r._key}} INSERT r
                          UPDATE UNSET(r, "_key") IN regions)
            LET region_edge = (FOR e IN @region_edges
                               INSERT e INTO event_in_region OPTIONS {{overwriteMode: "replace"}})
            LET network = (FOR n IN @networks UPSERT {{_key: n._key}} INSERT n
                           UPDATE UNSET(n, "_key") IN networks)
            LET network_edge = (FOR e IN @network_edges
                                INSERT e INTO event_reported_by_network
                                OPTIONS {{overwriteMode: "replace"}})
            RETURN 1
            """,
            {
                "event": w.event,
                "claims": [
                    {
                        "_key": f"{w.source.lower()}_{id_}",
                        "source": w.source,
                        "source_event_id": id_,
                        "event_key": key,
                        "claimed_at": at,
                    }
                    for id_ in w.claim_ids
                ],
                "revisions": [w.revision] if w.revision else [],
                "raw": w.raw,
                "regions": region_docs,
                "region_edges": region_edges,
                "networks": network_docs,
                "network_edges": network_edges,
            },
            record_metrics=False,
        )
        if w.relink_region and w.region is None:
            run_query(
                self.db,
                "ingest_unlink_region",
                "REMOVE {_key: @k} IN event_in_region OPTIONS {ignoreErrors: true}",
                {"k": key},
                record_metrics=False,
            )

    def touch_seen(self, keys: Iterable[str], seen_at: str, run_id: str | None) -> int:
        key_list = list(keys)
        if not key_list:
            return 0
        run_query(
            self.db,
            "ingest_touch_seen",
            """
            FOR k IN @keys
              UPDATE {_key: k} WITH {last_seen_at: @at, last_ingestion_run_id: @run}
              IN events OPTIONS {ignoreErrors: true}
            """,
            {"keys": key_list, "at": seen_at, "run": run_id},
        )
        return len(key_list)

    # ---- dead letters --------------------------------------------------------------------------
    def record_dead_letter(
        self,
        *,
        source: str,
        source_event_id: str | None,
        payload_hash: str,
        reason: str,
        detail: str,
        payload: dict[str, Any],
        run_id: str | None,
    ) -> None:
        at = now_iso()
        run_query(
            self.db,
            "ingest_dead_letter",
            """
            UPSERT {_key: @key}
            INSERT {_key: @key, source: @source, source_event_id: @id, payload_hash: @hash,
                    reason: @reason, detail: @detail, payload: @payload,
                    first_failure_at: @at, last_failure_at: @at, retry_count: 1,
                    resolved_at: null, last_ingestion_run_id: @run}
            UPDATE {payload_hash: @hash, reason: @reason, detail: @detail, payload: @payload,
                    last_failure_at: @at, retry_count: OLD.retry_count + 1, resolved_at: null,
                    last_ingestion_run_id: @run}
            IN dead_letters
            """,
            {
                "key": dead_letter_key(source, source_event_id or payload_hash),
                "source": source,
                "id": source_event_id,
                "hash": payload_hash,
                "reason": reason,
                "detail": detail,
                "payload": payload,
                "at": at,
                "run": run_id,
            },
        )

    def resolve_dead_letters(self, source: str, source_event_ids: Sequence[str]) -> int:
        if not source_event_ids:
            return 0
        rows = run_query(
            self.db,
            RESOLVE_DEAD_LETTERS.name,
            RESOLVE_DEAD_LETTERS.aql,
            {"source": source, "ids": list(source_event_ids), "at": now_iso()},
        ).rows
        return len(rows)


class RunRepository:
    """ingestion_runs + backfill_jobs bookkeeping (outside the per-record transactions)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def start_run(
        self,
        *,
        kind: str,
        source: str,
        params: dict[str, Any],
        correlation_id: str | None,
        backfill_job_id: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        sync(
            self.db.collection(s.INGESTION_RUNS).insert(
                {
                    "_key": run_id,
                    "kind": kind,
                    "source": source,
                    "params": params,
                    "status": "running",
                    "started_at": now_iso(),
                    "finished_at": None,
                    "duration_ms": None,
                    "counts": {},
                    "requests": [],
                    "error": None,
                    "correlation_id": correlation_id,
                    "backfill_job_id": backfill_job_id,
                },
                silent=True,
            )
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        counts: dict[str, int],
        requests: list[dict[str, Any]],
        duration_ms: float,
        error: dict[str, Any] | None = None,
        source_generated_at: str | None = None,
    ) -> None:
        sync(
            self.db.collection(s.INGESTION_RUNS).update(
                {
                    "_key": run_id,
                    "status": status,
                    "finished_at": now_iso(),
                    "duration_ms": duration_ms,
                    "counts": counts,
                    "requests": requests,
                    "error": error,
                    "source_generated_at": source_generated_at,
                },
                silent=True,
                merge=False,
            )
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        doc = sync_optional(self.db.collection(s.INGESTION_RUNS).get(run_id))
        return doc if isinstance(doc, dict) else None

    def abandon_stale_runs(self, *, older_than: timedelta) -> int:
        """Runs stuck in ``running`` (worker died mid-run) become ``abandoned``."""
        rows = run_query(
            self.db,
            ABANDON_STALE_RUNS.name,
            ABANDON_STALE_RUNS.aql,
            {"threshold": to_iso(utc_now() - older_than), "now": now_iso()},
        ).rows
        return len(rows)

    # backfill jobs
    def create_backfill_job(self, doc: dict[str, Any]) -> None:
        sync(self.db.collection(s.BACKFILL_JOBS).insert(doc, silent=True))

    def get_backfill_job(self, job_id: str) -> dict[str, Any] | None:
        doc = sync_optional(self.db.collection(s.BACKFILL_JOBS).get(job_id))
        return doc if isinstance(doc, dict) else None

    def update_backfill_job(self, job_id: str, fields: dict[str, Any]) -> None:
        sync(self.db.collection(s.BACKFILL_JOBS).update({"_key": job_id, **fields}, silent=True))

    def active_backfill_jobs(self) -> list[dict[str, Any]]:
        return run_query(self.db, ACTIVE_BACKFILL_JOBS.name, ACTIVE_BACKFILL_JOBS.aql, {}).rows
