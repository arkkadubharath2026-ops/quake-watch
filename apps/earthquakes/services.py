"""Event query services (pure: no HTTP framework or driver imports).

Presentation separates **source** values (as published by USGS), **derived** values (computed by
QuakeWatch, with method) and **operational** metadata, so every value shown carries its provenance
(PRD P6, ADR-010).
"""

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import urlsplit

from apps.core.clock import now_iso
from apps.core.errors import Conflict, NotFound, ValidationFailed
from apps.earthquakes.domain import KEY_PRODUCTS, SOURCE_STATE_FIELDS
from apps.earthquakes.filters import EventFilter
from apps.ingestion.revision_policy import POLICY_VERSION, TRACKED_FIELDS

OPERATIONAL_FIELDS = (
    "first_seen_at",
    "last_seen_at",
    "last_ingested_at",
    "revision_count",
    "payload_hash",
    "schema_version",
    "revision_policy_version",
    "last_ingestion_run_id",
)
NEARBY_RADIUS_KM = 100.0
NEARBY_DAYS = 7


class EventReader(Protocol):
    def search(
        self, f: EventFilter, *, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]: ...
    def resolve(self, identifier: str) -> dict[str, Any] | None: ...
    def revisions(self, key: str) -> list[dict[str, Any]]: ...
    def relationships(self, key: str, *, limit: int = 10) -> dict[str, Any]: ...
    def nearby(
        self, event: dict[str, Any], *, radius_km: float, days: int, limit: int = 10
    ) -> list[dict[str, Any]]: ...
    def raw_payload(self, payload_hash: str) -> dict[str, Any] | None: ...
    def runs(self, run_ids: list[str]) -> list[dict[str, Any]]: ...
    def map_points(self, f: EventFilter) -> tuple[list[list[Any]], bool]: ...
    def map_clusters(self, f: EventFilter) -> tuple[list[dict[str, Any]], float]: ...


def safe_usgs_url(value: Any) -> str | None:
    """Only https links on usgs.gov hosts are rendered as links. The stored source value is kept
    unchanged; this guards pages against a tampered upstream URL (e.g. a ``javascript:`` scheme)."""
    if not isinstance(value, str):
        return None
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "usgs.gov" or host.endswith(".usgs.gov")):
        return None
    return value


def present_event(doc: dict[str, Any]) -> dict[str, Any]:
    source = {name: doc.get(name) for name in SOURCE_STATE_FIELDS}
    products = set(doc.get("products") or [])
    return {
        "key": doc["_key"],
        "title": _title(doc),
        "source": source,
        "derived": {
            **(doc.get("derived") or {}),
            "method_notes": {
                "region_name": "text after the last comma of the USGS place string, US state "
                "abbreviations expanded (method v1)",
                "first_seen_latency_s": "QuakeWatch first observation minus origin time",
            },
        },
        "operational": {name: doc.get(name) for name in OPERATIONAL_FIELDS},
        "products": [
            {"type": code, "label": label, "available": code in products}
            for code, label in KEY_PRODUCTS.items()
        ],
        "enrichment": doc.get("enrichment"),
        "links": {"usgs_event_page": safe_usgs_url(doc.get("event_page_url"))},
    }


def _title(doc: dict[str, Any]) -> str:
    magnitude = doc.get("magnitude")
    mag = f"M {magnitude:.1f}" if isinstance(magnitude, int | float) else "M ?"
    return f"{mag} — {doc.get('place') or 'Unknown location'}"


class EventQueryService:
    def __init__(self, reader: EventReader) -> None:
        self.reader = reader

    def search(self, f: EventFilter, *, offset: int, limit: int) -> dict[str, Any]:
        rows, total = self.reader.search(f, offset=offset, limit=limit)
        return {
            "rows": rows,
            "total": total,
            "query": {"filters": f.canonical(), "summary": f.summary()},
        }

    def get(self, identifier: str) -> dict[str, Any]:
        doc = self.reader.resolve(identifier)
        if doc is None:
            raise NotFound(f"No event found for id {identifier!r}.")
        return doc

    def detail(self, identifier: str) -> dict[str, Any]:
        doc = self.get(identifier)
        presented = present_event(doc)
        if identifier not in (
            doc["_key"],
            doc["source_event_id"],
            f"usgs_{doc['source_event_id']}",
        ):
            presented["resolved_from"] = identifier
        return presented

    def revisions(self, identifier: str) -> dict[str, Any]:
        doc = self.get(identifier)
        revisions = self.reader.revisions(doc["_key"])
        timeline = [
            {
                "revision_number": r["revision_number"],
                "kind": r["kind"],
                "observed_at": r["observed_at"],
                "source_updated_at": r["source_updated_at"],
                "changes": [
                    {"field": f, "before": r["before"].get(f), "after": r["after"].get(f)}
                    for f in r["changed_fields"]
                ],
                "payload_hash": r["payload_hash"],
                "policy_version": r["policy_version"],
                "ingestion_run_id": r.get("ingestion_run_id"),
            }
            for r in revisions
        ]
        initial = revisions[0]["state"] if revisions else None
        current = revisions[-1]["state"] if revisions else None
        comparison = []
        if initial and current:
            for field in TRACKED_FIELDS:
                if initial.get(field) != current.get(field):
                    comparison.append(
                        {
                            "field": field,
                            "initial": initial.get(field),
                            "current": current.get(field),
                        }
                    )
        return {
            "key": doc["_key"],
            "revision_count": len(revisions),
            "policy_version": POLICY_VERSION,
            "tracked_fields": {
                name: {"kind": rule.kind, "tolerance": rule.tolerance, "rationale": rule.rationale}
                for name, rule in TRACKED_FIELDS.items()
            },
            "timeline": timeline,
            "initial_vs_current": comparison,
        }

    def provenance(self, identifier: str) -> dict[str, Any]:
        doc = self.get(identifier)
        revisions = self.reader.revisions(doc["_key"])
        run_ids = sorted({r["ingestion_run_id"] for r in revisions if r.get("ingestion_run_id")})
        raw = self.reader.raw_payload(doc["payload_hash"])
        return {
            "key": doc["_key"],
            "source": doc["source"],
            "source_event_id": doc["source_event_id"],
            "associated_ids": doc.get("associated_ids", []),
            "payload_hashes": [
                {"revision_number": r["revision_number"], "payload_hash": r["payload_hash"]}
                for r in revisions
            ],
            "current_payload": {
                "payload_hash": doc["payload_hash"],
                "retained": raw is not None,
                "first_fetched_at": raw.get("first_fetched_at") if raw else None,
                "last_fetched_at": raw.get("last_fetched_at") if raw else None,
                "payload": raw.get("payload") if raw else None,
            },
            "ingestion_runs": self.reader.runs(run_ids),
            "attribution": "Earthquake data courtesy of the U.S. Geological Survey (USGS).",
        }

    def relationships(self, identifier: str) -> dict[str, Any]:
        doc = self.get(identifier)
        graph = self.reader.relationships(doc["_key"])
        return {
            "key": doc["_key"],
            **graph,
            "nearby": {
                "radius_km": NEARBY_RADIUS_KM,
                "window_days": NEARBY_DAYS,
                "note": "Proximity in space and time only; not an aftershock classification.",
                "events": self.reader.nearby(doc, radius_km=NEARBY_RADIUS_KM, days=NEARBY_DAYS),
            },
        }

    def map(self, f: EventFilter) -> dict[str, Any]:
        if f.bbox is None:
            raise ValidationFailed(
                "The map endpoint requires a viewport bbox.",
                details={"fields": {"bbox": "required: south,west,north,east"}},
            )
        points, truncated = self.reader.map_points(f)
        if not truncated:
            return {"mode": "points", "count": len(points), "points": points}
        clusters, cell = self.reader.map_clusters(f)
        return {
            "mode": "clusters",
            "cell_degrees": cell,
            "count": sum(c["count"] for c in clusters),
            "clusters": clusters,
        }


class SavedSearchStore(Protocol):
    def list_for_user(self, user_id: int) -> list[dict[str, Any]]: ...
    def create(self, user_id: int, doc: dict[str, Any]) -> dict[str, Any] | None: ...
    def get(self, user_id: int, search_id: str) -> dict[str, Any] | None: ...
    def update(
        self, user_id: int, search_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None: ...
    def delete(self, user_id: int, search_id: str) -> bool: ...


def _search_name(raw: Any) -> str:
    name = " ".join(str(raw or "").split())
    if not 1 <= len(name) <= 120:
        raise ValidationFailed(
            "Invalid saved search.", details={"fields": {"name": "1 to 120 characters required"}}
        )
    return name


class SavedSearchService:
    """Saved explorer queries (FR-12). Filters are stored in canonical form and re-validated."""

    def __init__(self, store: SavedSearchStore, events: EventQueryService) -> None:
        self.store = store
        self.events = events

    def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        return self.store.list_for_user(user_id)

    def create(self, user_id: int, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationFailed("Invalid saved search.", details={"fields": {"body": "object"}})
        name = _search_name(payload.get("name"))
        raw_filters = payload.get("filters") or {}
        if not isinstance(raw_filters, dict):
            raise ValidationFailed(
                "Invalid saved search.", details={"fields": {"filters": "object"}}
            )
        f = EventFilter.from_params(raw_filters)
        now = now_iso()
        created = self.store.create(
            user_id,
            {
                "name": name,
                "filters": f.canonical(),
                "summary": f.summary(),
                "created_at": now,
                "updated_at": now,
            },
        )
        if created is None:
            raise Conflict("Saved search limit reached.")
        return created

    def get(self, user_id: int, search_id: str) -> dict[str, Any]:
        found = self.store.get(user_id, search_id)
        if found is None:
            raise NotFound("Saved search not found.")
        return found

    def rename(self, user_id: int, search_id: str, payload: Any) -> dict[str, Any]:
        name = _search_name(payload.get("name") if isinstance(payload, dict) else None)
        updated = self.store.update(user_id, search_id, {"name": name, "updated_at": now_iso()})
        if updated is None:
            raise NotFound("Saved search not found.")
        return updated

    def delete(self, user_id: int, search_id: str) -> None:
        if not self.store.delete(user_id, search_id):
            raise NotFound("Saved search not found.")

    def run(self, user_id: int, search_id: str, *, offset: int, limit: int) -> dict[str, Any]:
        saved = self.get(user_id, search_id)
        f = EventFilter.from_params(saved["filters"])
        return {"saved_search": saved, **self.events.search(f, offset=offset, limit=limit)}
