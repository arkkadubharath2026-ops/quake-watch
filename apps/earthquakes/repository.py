"""Read-side persistence for events: search, detail, revisions, map, graph relationships.

The search builder concatenates only allow-listed AQL fragments; every value is a bind variable
and the sort attribute comes from :data:`apps.earthquakes.filters.SORT_FIELDS`. Merged records are
always excluded (ADR-003).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from arango.database import Database

from apps.core.arango import catalog
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.client import sync_optional
from apps.core.arango.query import run_query
from apps.core.arango.transactions import exclusive_query
from apps.core.clock import from_iso, to_iso
from apps.earthquakes.filters import SORT_FIELDS, EventFilter

LIST_FIELDS = (
    "source_event_id", "magnitude", "magnitude_type", "place", "occurred_at", "depth_km",
    "latitude", "longitude", "alert", "status", "tsunami", "network", "significance",
    "event_type", "felt", "revision_count", "source_updated_at",
)  # fmt: skip

_LIST_PROJECTION = "MERGE(KEEP(e, @fields), {key: e._key, region_name: e.derived.region_name})"

MAP_POINT_LIMIT = 2000
MAP_GRID_CELLS = 48  # target cells across the viewport's longer side when clustering
TEXT_SEARCH = (
    "SEARCH ANALYZER(TOKENS(@q, 'text_en') ALL == e.place, 'text_en') "
    "OR ANALYZER(TOKENS(@q, 'text_en') ALL == e.derived.region_name, 'text_en')"
)


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    head: str
    filters: list[str]
    binds: dict[str, Any]

    def body(self) -> str:
        return "\n".join([self.head, *(f"  FILTER {c}" for c in self.filters)])


def compile_filter(f: EventFilter) -> CompiledQuery:
    binds: dict[str, Any] = {}
    filters: list[str] = []
    if f.text:
        head = f"FOR e IN events_search {TEXT_SEARCH}"
        binds["q"] = f.text
    else:
        head = "FOR e IN events"
    if f.radius is not None:
        filters.append("GEO_DISTANCE(e.coordinates, [@lon, @lat]) <= @radius_m")
        binds.update(
            lon=f.radius.longitude, lat=f.radius.latitude, radius_m=f.radius.radius_km * 1000
        )
    if f.bbox is not None:
        polygons = f.bbox.polygons()
        if len(polygons) == 1:
            filters.append("GEO_CONTAINS(@bbox0, e.coordinates)")
        else:
            filters.append(
                "(GEO_CONTAINS(@bbox0, e.coordinates) OR GEO_CONTAINS(@bbox1, e.coordinates))"
            )
        for i, ring in enumerate(polygons):
            binds[f"bbox{i}"] = {"type": "Polygon", "coordinates": [ring]}
    if f.start is not None:
        filters.append("e.occurred_at >= @start")
        binds["start"] = to_iso(f.start)
    if f.end is not None:
        filters.append("e.occurred_at < @end")
        binds["end"] = to_iso(f.end)
    if f.min_magnitude is not None:
        filters.append("e.magnitude >= @min_mag")
        binds["min_mag"] = f.min_magnitude
    if f.max_magnitude is not None:
        filters.append("e.magnitude != null AND e.magnitude <= @max_mag")
        binds["max_mag"] = f.max_magnitude
    if f.min_depth_km is not None:
        filters.append("e.depth_km >= @min_depth")
        binds["min_depth"] = f.min_depth_km
    if f.max_depth_km is not None:
        filters.append("e.depth_km != null AND e.depth_km <= @max_depth")
        binds["max_depth"] = f.max_depth_km
    if f.alerts:
        levels = [a for a in f.alerts if a != "none"]
        clause = "e.alert IN @alerts"
        if "none" in f.alerts:
            clause = f"({clause} OR e.alert == null)"
        filters.append(clause)
        binds["alerts"] = levels
    if f.tsunami is not None:
        filters.append("e.tsunami == @tsunami")
        binds["tsunami"] = f.tsunami
    if f.statuses:
        filters.append("e.status IN @statuses")
        binds["statuses"] = list(f.statuses)
    if f.networks:
        filters.append("e.network IN @networks")
        binds["networks"] = list(f.networks)
    if f.event_types:
        filters.append("e.event_type IN @event_types")
        binds["event_types"] = list(f.event_types)
    filters.append("e.merged_into == null")
    return CompiledQuery(head=head, filters=filters, binds=binds)


def search_aql(f: EventFilter) -> tuple[str, dict[str, Any]]:
    compiled = compile_filter(f)
    sort_attr = SORT_FIELDS[f.sort]  # allow-listed
    direction = "ASC" if f.direction == "asc" else "DESC"
    aql = (
        f"{compiled.body()}\n"
        f"  SORT e.{sort_attr} {direction}, e._key {direction}\n"
        f"  LIMIT @offset, @limit\n"
        f"  RETURN {_LIST_PROJECTION}"
    )
    return aql, {**compiled.binds, "fields": list(LIST_FIELDS)}


def search_page_aql(f: EventFilter) -> tuple[str, dict[str, Any]]:
    """One page plus the total match count, in one query (one consistent snapshot).

    The total comes from a separate ``COLLECT WITH COUNT`` over the same filters rather than
    ``fullCount``: ``fullCount`` forces the sorted page query to materialise every matching
    document, while the count subquery is answered from index entries (docs/BENCHMARKS.md).
    """
    compiled = compile_filter(f)
    page, binds = search_aql(f)
    aql = "\n".join(
        [
            "LET total = FIRST(",
            compiled.body(),
            "  COLLECT WITH COUNT INTO n",
            "  RETURN n",
            ")",
            "LET rows = (",
            page,
            ")",
            "RETURN {total: total, rows: rows}",
        ]
    )
    return aql, binds


# ---- representative variants registered for EXPLAIN / docs -----------------------------------
def _with_page(binds: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    return lambda: {**binds, "offset": 0, "limit": 25}


def _variant(name: str, question: str, params: dict[str, str], indexes: tuple[str, ...],
             features: tuple[str, ...]) -> None:  # fmt: skip
    f = EventFilter.from_params(params)
    aql, binds = search_page_aql(f)
    catalog.register(
        NamedQuery(
            name=name,
            category="search",
            question=question,
            aql=aql,
            sample_binds=_with_page(binds),
            expected_indexes=indexes,
            features=features,
        )
    )


_variant(
    "events_recent_strong",
    "Most recent events at or above a magnitude, newest first (explorer default view).",
    {"min_magnitude": "4.5"},
    ("qw_events_occurred_at", "qw_events_magnitude"),
    ("filter", "sort", "pagination"),
)
_variant(
    "events_strongest_in_range",
    "Strongest events in a date range (README Q1).",
    {"start": "2026-09-01", "end": "2026-09-15", "sort": "magnitude"},
    ("qw_events_magnitude",),
    ("range filter", "sort"),
)
_variant(
    "events_within_radius",
    "Events within a geographic radius of a point (README Q2).",
    {"lat": "61.2", "lon": "-149.9", "radius_km": "300", "min_magnitude": "2.5"},
    ("qw_events_geo",),
    ("geo index", "GEO_DISTANCE"),
)
_variant(
    "events_in_viewport",
    "Events inside a map viewport bounding box.",
    {"bbox": "50,-170,72,-130"},
    ("qw_events_geo",),
    ("geo index", "GEO_CONTAINS"),
)
_variant(
    "events_tsunami_flagged",
    "Tsunami-flagged events (README Q6).",
    {"tsunami": "true"},
    ("qw_events_occurred_at",),
    ("filter",),
)
_variant(
    "events_deepest",
    "Deepest events (README Q5).",
    {"sort": "depth"},
    (),
    ("sort",),
)
_variant(
    "events_location_text",
    "Full-text location search over place and derived region (ArangoSearch view).",
    {"q": "fiji islands"},
    (),
    ("ArangoSearch view", "text analyzer"),
)

DETAIL_BY_ID = catalog.register(
    NamedQuery(
        name="event_resolve_id",
        category="detail",
        question="Resolve any USGS id (current or historical) to its live canonical event.",
        aql="""
        LET direct = DOCUMENT("events", @key)
        LET claim = DOCUMENT("event_identities", @claim_key)
        LET doc = direct != null ? direct
                  : (claim != null ? DOCUMENT("events", claim.event_key) : null)
        LET live = doc == null ? null
                   : (doc.merged_into == null ? doc : DOCUMENT("events", doc.merged_into))
        RETURN live
        """,
        sample_binds=lambda: {"key": "usgs_x", "claim_key": "usgs_x"},
        features=("primary-key lookup",),
    )
)

REVISIONS = catalog.register(
    NamedQuery(
        name="event_revisions",
        category="revisions",
        question="Revision timeline of one event, oldest first.",
        aql="""
        FOR r IN event_revisions
          FILTER r.event_key == @key
          SORT r.revision_number ASC
          RETURN UNSET(r, "_id", "_rev")
        """,
        sample_binds=lambda: {"key": "usgs_x"},
        expected_indexes=("qw_revisions_event_rev",),
        features=("persistent index", "sort"),
    )
)

RELATIONSHIPS = catalog.register(
    NamedQuery(
        name="event_graph_relationships",
        category="graph",
        question="Region and network of an event and other recent events in the same region "
        "(graph traversal event → region ← events; README Q10).",
        aql="""
        LET start = DOCUMENT("events", @key)
        LET region = FIRST(FOR v IN 1..1 OUTBOUND start event_in_region RETURN v)
        LET network = FIRST(FOR v IN 1..1 OUTBOUND start event_reported_by_network RETURN v)
        LET same_region = region == null ? [] : (
          FOR other IN 1..1 INBOUND region event_in_region
            FILTER other._key != @key AND other.merged_into == null
            SORT other.occurred_at DESC
            LIMIT @limit
            RETURN MERGE(KEEP(other, "magnitude", "place", "occurred_at", "depth_km"),
                         {key: other._key})
        )
        LET region_total = region == null ? 0 : LENGTH(
          FOR other IN 1..1 INBOUND region event_in_region
            FILTER other.merged_into == null RETURN 1)
        RETURN {region: region == null ? null : UNSET(region, "_id", "_rev"),
                network: network == null ? null : UNSET(network, "_id", "_rev"),
                same_region: same_region, region_event_count: region_total}
        """,
        sample_binds=lambda: {"key": "usgs_x", "limit": 10},
        expected_indexes=("edge",),
        features=("graph traversal", "OUTBOUND", "INBOUND"),
    )
)

NEARBY = catalog.register(
    NamedQuery(
        name="event_nearby_space_time",
        category="geo",
        question="Other events within a radius and a time window of an event (proximity only; "
        "not an aftershock classification — ESD §20C).",
        aql="""
        FOR e IN events
          FILTER GEO_DISTANCE(e.coordinates, @point) <= @radius_m
          FILTER e.occurred_at >= @start AND e.occurred_at <= @end
          FILTER e._key != @key AND e.merged_into == null
          LET distance_km = GEO_DISTANCE(e.coordinates, @point) / 1000
          SORT distance_km ASC
          LIMIT @limit
          RETURN {key: e._key, magnitude: e.magnitude, place: e.place,
                  occurred_at: e.occurred_at, distance_km: ROUND(distance_km * 10) / 10}
        """,
        sample_binds=lambda: {
            "point": [-150.0, 61.0],
            "radius_m": 100000,
            "start": "2026-09-01T00:00:00.000Z",
            "end": "2026-09-15T00:00:00.000Z",
            "key": "usgs_x",
            "limit": 10,
        },
        expected_indexes=("qw_events_geo",),
        features=("geo index", "GEO_DISTANCE", "time window"),
    )
)

RAW_PAYLOAD = catalog.register(
    NamedQuery(
        name="event_raw_payload",
        category="provenance",
        question="Retained raw source payload by content hash (ADR-007).",
        aql='RETURN DOCUMENT("raw_payloads", @hash)',
        sample_binds=lambda: {"hash": "0" * 64},
        features=("primary-key lookup", "TTL retention"),
    )
)

RUNS_BY_ID = catalog.register(
    NamedQuery(
        name="ingestion_runs_by_ids",
        category="provenance",
        question="Ingestion runs (with request manifests) that touched an event.",
        aql="""
        FOR k IN @keys
          LET r = DOCUMENT("ingestion_runs", k)
          FILTER r != null
          RETURN KEEP(r, "_key", "kind", "status", "started_at", "finished_at", "requests",
                      "source_generated_at")
        """,
        sample_binds=lambda: {"keys": ["x"]},
        features=("primary-key lookup",),
    )
)


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def search(
        self, f: EventFilter, *, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        aql, binds = search_page_aql(f)
        result = run_query(
            self.db, "events_search", aql, {**binds, "offset": offset, "limit": limit}
        )
        page = result.rows[0]
        return page["rows"], int(page["total"] or 0)

    def export_rows(self, f: EventFilter, *, limit: int) -> list[dict[str, Any]]:
        aql, binds = search_aql(f)
        return run_query(
            self.db, "events_export", aql, {**binds, "offset": 0, "limit": limit}, max_runtime=120
        ).rows

    def resolve(self, identifier: str) -> dict[str, Any] | None:
        key = identifier if identifier.startswith("usgs_") else f"usgs_{identifier}"
        rows = run_query(
            self.db, DETAIL_BY_ID.name, DETAIL_BY_ID.aql, {"key": key, "claim_key": key}
        ).rows
        return rows[0] if rows and rows[0] else None

    def revisions(self, key: str) -> list[dict[str, Any]]:
        return run_query(self.db, REVISIONS.name, REVISIONS.aql, {"key": key}).rows

    def relationships(self, key: str, *, limit: int = 10) -> dict[str, Any]:
        rows = run_query(
            self.db, RELATIONSHIPS.name, RELATIONSHIPS.aql, {"key": key, "limit": limit}
        ).rows
        return rows[0] if rows else {}

    def nearby(
        self, event: dict[str, Any], *, radius_km: float, days: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        occurred = from_iso(event["occurred_at"])
        return run_query(
            self.db,
            NEARBY.name,
            NEARBY.aql,
            {
                "point": event["coordinates"],
                "radius_m": radius_km * 1000,
                "start": to_iso(occurred - timedelta(days=days)),
                "end": to_iso(occurred + timedelta(days=days)),
                "key": event["_key"],
                "limit": limit,
            },
        ).rows

    def raw_payload(self, payload_hash: str) -> dict[str, Any] | None:
        doc = sync_optional(self.db.collection("raw_payloads").get(payload_hash))
        return doc if isinstance(doc, dict) else None

    def runs(self, run_ids: list[str]) -> list[dict[str, Any]]:
        if not run_ids:
            return []
        return run_query(self.db, RUNS_BY_ID.name, RUNS_BY_ID.aql, {"keys": run_ids}).rows

    # ---- map ----------------------------------------------------------------------------------
    def map_points(self, f: EventFilter) -> tuple[list[list[Any]], bool]:
        """Compact points ``[key, lat, lon, mag, depth, occurred_at]``; flag if over the limit."""
        compiled = compile_filter(f)
        aql = (
            f"{compiled.body()}\n"
            "  SORT e.magnitude DESC\n"
            "  LIMIT @limit\n"
            "  RETURN [e._key, e.latitude, e.longitude, e.magnitude, e.depth_km, e.occurred_at]"
        )
        rows = run_query(
            self.db, "events_map_points", aql, {**compiled.binds, "limit": MAP_POINT_LIMIT + 1}
        ).rows
        return rows[:MAP_POINT_LIMIT], len(rows) > MAP_POINT_LIMIT

    def map_clusters(self, f: EventFilter) -> tuple[list[dict[str, Any]], float]:
        """Server-side grid clustering for dense viewports (bounded result size)."""
        assert f.bbox is not None
        span = max(f.bbox.north - f.bbox.south, (f.bbox.east - f.bbox.west) % 360 or 360)
        cell = max(0.05, span / MAP_GRID_CELLS)
        compiled = compile_filter(f)
        aql = (
            f"{compiled.body()}\n"
            "  COLLECT cell = [FLOOR(e.latitude / @cell), FLOOR(e.longitude / @cell)]\n"
            "  AGGREGATE n = LENGTH(1), max_mag = MAX(e.magnitude),\n"
            "            lat = AVG(e.latitude), lon = AVG(e.longitude)\n"
            "  RETURN {lat: lat, lon: lon, count: n, max_magnitude: max_mag}"
        )
        rows = run_query(self.db, "events_map_clusters", aql, {**compiled.binds, "cell": cell}).rows
        return rows, round(cell, 4)


SAVED_BY_USER = catalog.register(
    NamedQuery(
        name="saved_searches_by_user",
        category="saved searches",
        question="A user's saved explorer searches, newest first.",
        aql="""
        FOR s IN saved_searches
          FILTER s.user_id == @user_id
          SORT s.user_id DESC, s.created_at DESC
          RETURN MERGE(UNSET(s, "_id", "_rev", "_key"), {id: s._key})
        """,
        sample_binds=lambda: {"user_id": 1},
        expected_indexes=("qw_saved_user",),
        features=("composite index",),
    )
)

MAX_SAVED_SEARCHES = 50


class SavedSearchRepository:
    """User-owned saved searches (FR-12). Every query is scoped by ``user_id``."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        return run_query(self.db, SAVED_BY_USER.name, SAVED_BY_USER.aql, {"user_id": user_id}).rows

    def create(self, user_id: int, doc: dict[str, Any]) -> dict[str, Any] | None:
        rows = exclusive_query(
            self.db,
            "saved_searches_create",
            """
            LET existing = LENGTH(FOR s IN saved_searches FILTER s.user_id == @uid RETURN 1)
            FILTER existing < @max
            INSERT MERGE(@doc, {user_id: @uid}) INTO saved_searches
            RETURN MERGE(UNSET(NEW, "_id", "_rev", "_key"), {id: NEW._key})
            """,
            {"uid": user_id, "doc": doc, "max": MAX_SAVED_SEARCHES},
            exclusive=["saved_searches"],
        )
        return rows[0] if rows else None

    def get(self, user_id: int, search_id: str) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            "saved_searches_get",
            """
            LET s = DOCUMENT("saved_searches", @id)
            FILTER s != null AND s.user_id == @uid
            RETURN MERGE(UNSET(s, "_id", "_rev", "_key"), {id: s._key})
            """,
            {"id": search_id, "uid": user_id},
        ).rows
        return rows[0] if rows else None

    def update(self, user_id: int, search_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            "saved_searches_update",
            """
            LET s = DOCUMENT("saved_searches", @id)
            FILTER s != null AND s.user_id == @uid
            UPDATE s WITH @fields IN saved_searches OPTIONS {mergeObjects: false}
            RETURN MERGE(UNSET(NEW, "_id", "_rev", "_key"), {id: NEW._key})
            """,
            {"id": search_id, "uid": user_id, "fields": fields},
        ).rows
        return rows[0] if rows else None

    def delete(self, user_id: int, search_id: str) -> bool:
        rows = run_query(
            self.db,
            "saved_searches_delete",
            """
            LET s = DOCUMENT("saved_searches", @id)
            FILTER s != null AND s.user_id == @uid
            REMOVE s IN saved_searches
            RETURN 1
            """,
            {"id": search_id, "uid": user_id},
        ).rows
        return bool(rows)
