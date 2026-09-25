"""Ingestion pipeline (ESD §7): identify → diff → transactional upsert → observers.

For each normalised record:

1. **Fast path** — if the current canonical event already carries this exact payload hash, the
   record is *unchanged*: its ``last_seen_at`` is bulk-updated, nothing else is written.
2. Otherwise, inside one stream transaction:
   a. resolve identity through ``associated_ids`` (handles USGS preferred-id changes and merges);
   b. ignore out-of-order data (older ``source_updated_at`` → *stale*);
   c. diff against the versioned revision policy;
   d. write canonical event + immutable revision + raw payload + region/network edges;
   e. let observers (e.g. alert evaluation) write within the same transaction.

Replaying a feed is idempotent: identical payloads hit the fast path; revision keys are
deterministic (``<event_key>_<n>``) and uniquely indexed, and a concurrent duplicate surfaces as a
write conflict that retries the whole unit, which then sees the committed state.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, Protocol

from apps.core import metrics
from apps.core.arango import Database, StandardDatabase
from apps.core.arango import schema as s
from apps.core.arango.transactions import run_in_transaction
from apps.core.clock import from_iso, now_iso, utc_now
from apps.core.errors import DatabaseUnavailable
from apps.earthquakes.domain import SCHEMA_VERSION, CanonicalEventInput, is_important
from apps.geo.regions import region_from_place
from apps.ingestion import revision_policy as policy
from apps.ingestion.normalizer import NormalizedRecord, RecordRejected
from apps.ingestion.repository import EventWrite, IngestionRepository, revision_key
from config.env import get_settings
from config.logging import get_logger

log = get_logger(__name__)

Mode = Literal["feed", "backfill"]
Outcome = Literal["inserted", "revised", "refreshed", "unchanged", "stale"]

BASE_WRITE_COLLECTIONS: tuple[str, ...] = (
    s.EVENTS,
    s.EVENT_IDENTITIES,
    s.EVENT_REVISIONS,
    s.RAW_PAYLOADS,
    s.REGIONS,
    s.NETWORKS,
    s.EVENT_IN_REGION,
    s.EVENT_REPORTED_BY_NETWORK,
)


@dataclass(frozen=True, slots=True)
class EventChange:
    kind: Literal["inserted", "revised"]
    event: dict[str, Any]
    changes: tuple[policy.FieldChange, ...]
    mode: Mode
    observed_at: str


class EventObserver(Protocol):
    """Participates in the ingestion transaction for inserted/revised events."""

    write_collections: tuple[str, ...]
    read_collections: tuple[str, ...]

    def on_event(self, txn: Database, change: EventChange) -> int:
        """Return the number of side effects produced (e.g. alert matches)."""
        ...


@dataclass
class IngestionStats:
    counts: Counter[str] = field(default_factory=Counter)
    revised_keys: list[str] = field(default_factory=list)
    inserted_keys: list[str] = field(default_factory=list)
    important_keys: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        keys = (
            "fetched", "inserted", "revised", "refreshed", "unchanged", "stale",
            "rejected", "failed", "merged", "observer_effects", "dead_letters_resolved",
        )  # fmt: skip
        return {k: int(self.counts.get(k, 0)) for k in keys}


def _event_doc(
    event: CanonicalEventInput,
    *,
    key: str,
    payload_hash: str,
    observed_at: str,
    first_seen_at: str,
    revision_count: int,
    run_id: str | None,
    mode: Mode,
    previous_derived: dict[str, Any] | None,
) -> dict[str, Any]:
    region = region_from_place(event.place)
    derived: dict[str, Any] = dict(previous_derived or {})
    if previous_derived is None:
        derived["first_seen_via"] = mode
        derived["first_seen_latency_s"] = round(
            (from_iso(first_seen_at) - event.occurred_at).total_seconds(), 3
        )
    derived.update(
        {
            "region_key": region.key if region else None,
            "region_name": region.name if region else None,
            "region_kind": region.kind if region else None,
            "region_method_version": region.method_version if region else None,
        }
    )
    return {
        "_key": key,
        **event.to_state(),
        "coordinates": [event.longitude, event.latitude],
        "derived": derived,
        "first_seen_at": first_seen_at,
        "last_seen_at": observed_at,
        "last_ingested_at": observed_at,
        "revision_count": revision_count,
        "payload_hash": payload_hash,
        "schema_version": SCHEMA_VERSION,
        "revision_policy_version": policy.POLICY_VERSION,
        "merged_into": None,
        "last_ingestion_run_id": run_id,
    }


def _source_state(doc: dict[str, Any]) -> dict[str, Any]:
    return {name: doc.get(name) for name in CanonicalEventInput.model_fields}


def _revision(
    event_key: str,
    number: int,
    kind: Literal["created", "updated"],
    changes: Sequence[policy.FieldChange],
    state: dict[str, Any],
    record: NormalizedRecord,
    observed_at: str,
    run_id: str | None,
) -> dict[str, Any]:
    return {
        "_key": revision_key(event_key, number),
        "event_key": event_key,
        "revision_number": number,
        "kind": kind,
        "observed_at": observed_at,
        "source_updated_at": state["source_updated_at"],
        "changed_fields": [c.field for c in changes],
        "before": {c.field: c.before for c in changes},
        "after": {c.field: c.after for c in changes},
        "state": state,
        "payload_hash": record.payload_hash,
        "policy_version": policy.POLICY_VERSION,
        "ingestion_run_id": run_id,
    }


def _pick_primary(candidates: list[dict[str, Any]], preferred_id: str) -> dict[str, Any]:
    for doc in candidates:
        if doc["source_event_id"] == preferred_id:
            return doc
    return min(candidates, key=lambda d: (d["first_seen_at"], d["_key"]))


class IngestionPipeline:
    def __init__(
        self,
        db: StandardDatabase,
        *,
        observers: Sequence[EventObserver] = (),
        run_id: str | None = None,
        mode: Mode = "feed",
    ) -> None:
        self.db = db
        self.repo = IngestionRepository(db)
        self.observers = tuple(observers)
        self.run_id = run_id
        self.mode = mode
        retention = get_settings().raw_payload_retention_days
        self._raw_ttl = timedelta(days=retention)
        write = set(BASE_WRITE_COLLECTIONS)
        read: set[str] = set()
        for obs in self.observers:
            write.update(obs.write_collections)
            read.update(obs.read_collections)
        self._write = tuple(sorted(write))
        self._read = tuple(sorted(read - write))

    # ------------------------------------------------------------------------------------------
    def ingest(
        self, records: Sequence[NormalizedRecord], rejected: Sequence[RecordRejected] = ()
    ) -> IngestionStats:
        stats = IngestionStats()
        stats.counts["fetched"] = len(records) + len(rejected)
        started = time.perf_counter()

        for bad in rejected:
            self.repo.record_dead_letter(
                source="USGS",
                source_event_id=bad.source_event_id,
                payload_hash=bad.payload_hash,
                reason=bad.reason,
                detail=bad.detail,
                payload=bad.payload,
                run_id=self.run_id,
            )
            stats.counts["rejected"] += 1
            log.warning(
                "record_rejected",
                source="USGS",
                source_event_id=bad.source_event_id,
                reason=bad.reason,
                detail=bad.detail,
            )

        known = self.repo.known_events("USGS", [r.event.source_event_id for r in records])
        unchanged_keys: list[str] = []
        observed_at = now_iso()
        for record in records:
            current = known.get(record.event.source_event_id)
            if current is not None and current.payload_hash == record.payload_hash:
                unchanged_keys.append(current.key)
                stats.counts["unchanged"] += 1
                continue
            try:
                outcome, merged = self._apply(record, observed_at, stats)
            except DatabaseUnavailable:
                raise  # infrastructure outage: abort the batch, the run is marked failed
            except Exception as exc:  # noqa: BLE001 - isolate one bad record; dead-lettered below
                self._record_failure(record, exc)
                stats.counts["failed"] += 1
                continue
            stats.counts[outcome] += 1
            stats.counts["merged"] += merged

        run_in_transaction(  # retried on write conflicts with concurrent ingestion units
            self.db,
            lambda txn: IngestionRepository(txn).touch_seen(
                unchanged_keys, observed_at, self.run_id
            ),
            write=[s.EVENTS],
            max_attempts=6,
        )
        stats.counts["dead_letters_resolved"] = self.repo.resolve_dead_letters(
            "USGS", [r.event.source_event_id for r in records]
        )
        for name in ("inserted", "revised", "unchanged", "stale", "rejected", "failed"):
            if stats.counts[name]:
                metrics.incr(f"ingest_{name}", stats.counts[name])
        log.info(
            "ingest_batch_done",
            ingestion_run_id=self.run_id,
            mode=self.mode,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            **stats.as_dict(),
        )
        return stats

    def _record_failure(self, record: NormalizedRecord, exc: Exception) -> None:
        log.error(
            "record_apply_failed",
            source=record.event.source,
            source_event_id=record.event.source_event_id,
            error=str(exc),
            exc_info=exc,
        )
        self.repo.record_dead_letter(
            source=record.event.source,
            source_event_id=record.event.source_event_id,
            payload_hash=record.payload_hash,
            reason="apply_failed",
            detail=f"{type(exc).__name__}: {exc}",
            payload=record.payload,
            run_id=self.run_id,
        )

    # ------------------------------------------------------------------------------------------
    def _apply(
        self, record: NormalizedRecord, observed_at: str, stats: IngestionStats
    ) -> tuple[Outcome, int]:
        def unit(txn: Database) -> tuple[Outcome, int, int, str]:
            return self._apply_in_txn(txn, record, observed_at)

        outcome, merged, effects, key = run_in_transaction(
            self.db,
            unit,
            write=self._write,
            read=self._read,
            max_attempts=6,
            retry_unique_violations=True,
        )
        stats.counts["observer_effects"] += effects
        if outcome == "inserted":
            stats.inserted_keys.append(key)
        elif outcome == "revised":
            stats.revised_keys.append(key)
        if outcome in ("inserted", "revised") and is_important(record.event):
            stats.important_keys.append(key)
        return outcome, merged

    def _apply_in_txn(
        self, txn: Database, record: NormalizedRecord, observed_at: str
    ) -> tuple[Outcome, int, int, str]:
        repo = IngestionRepository(txn)
        event = record.event
        new_state = event.to_state()
        candidates = repo.find_by_identity(event.source, event.associated_ids)
        raw = {
            "_key": record.payload_hash,
            "source": event.source,
            "source_event_id": event.source_event_id,
            "payload": record.payload,
            "first_fetched_at": observed_at,
            "last_fetched_at": observed_at,
            "expires_at": int((utc_now() + self._raw_ttl).timestamp()),
            "ingestion_run_id": self.run_id,
        }
        region = region_from_place(event.place)

        if not candidates:
            doc = _event_doc(
                event,
                key=event.key,
                payload_hash=record.payload_hash,
                observed_at=observed_at,
                first_seen_at=observed_at,
                revision_count=1,
                run_id=self.run_id,
                mode=self.mode,
                previous_derived=None,
            )
            repo.apply_write(
                EventWrite(
                    event=doc,
                    is_new=True,
                    source=event.source,
                    claim_ids=event.associated_ids,
                    raw=raw,
                    revision=_revision(
                        doc["_key"], 1, "created", [], new_state, record, observed_at, self.run_id
                    ),
                    region=region,
                    relink_region=True,
                    network=event.network,
                    relink_network=True,
                )
            )
            effects = self._notify(txn, EventChange("inserted", doc, (), self.mode, observed_at))
            return "inserted", 0, effects, doc["_key"]

        primary = _pick_primary(candidates, event.source_event_id)
        merged = 0
        for other in candidates:
            if other["_key"] != primary["_key"]:
                repo.absorb_merged(other["_key"], primary["_key"], observed_at)
                merged += 1
                log.info("event_merged", merged=other["_key"], into=primary["_key"])

        if from_iso(new_state["source_updated_at"]) < from_iso(primary["source_updated_at"]):
            # Identity knowledge is valid even when the payload itself is stale.
            repo.claim_identity(event.source, event.associated_ids, primary["_key"])
            repo.touch_seen([primary["_key"]], observed_at, self.run_id)
            return "stale", merged, 0, primary["_key"]

        before_state = _source_state(primary)
        changes = policy.diff(before_state, new_state)
        untracked = policy.untracked_changed(before_state, new_state)
        revision_count = int(primary["revision_count"]) + (1 if changes else 0)
        doc = _event_doc(
            event,
            key=primary["_key"],
            payload_hash=record.payload_hash,
            observed_at=observed_at,
            first_seen_at=primary["first_seen_at"],
            revision_count=revision_count,
            run_id=self.run_id,
            mode=self.mode,
            previous_derived=primary.get("derived") or {},
        )
        if "enrichment" in primary:
            doc["enrichment"] = primary["enrichment"]
        changed = {c.field for c in changes}
        repo.apply_write(
            EventWrite(
                event=doc,
                is_new=False,
                source=event.source,
                claim_ids=event.associated_ids,
                raw=raw,
                revision=(
                    _revision(
                        primary["_key"],
                        revision_count,
                        "updated",
                        changes,
                        new_state,
                        record,
                        observed_at,
                        self.run_id,
                    )
                    if changes
                    else None
                ),
                region=region,
                relink_region="place" in changed or bool(merged),
                network=event.network,
                relink_network=before_state.get("network") != event.network or bool(merged),
            )
        )
        if not changes:
            # untracked-only change → refreshed; identical content under a new hash → unchanged
            return ("refreshed" if untracked else "unchanged"), merged, 0, primary["_key"]
        effects = self._notify(
            txn, EventChange("revised", doc, tuple(changes), self.mode, observed_at)
        )
        return "revised", merged, effects, primary["_key"]

    def _notify(self, txn: Database, change: EventChange) -> int:
        return sum(observer.on_event(txn, change) for observer in self.observers)
