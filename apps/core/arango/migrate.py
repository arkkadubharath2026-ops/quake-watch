"""Idempotent schema reconciliation for ArangoDB.

``apply_schema`` makes the database match :mod:`apps.core.arango.schema`:
collections (created with the right type), JSON-schema validation rules, ``qw_*`` indexes
(created, replaced if the definition drifted, dropped if no longer declared), the ArangoSearch
view and the named graph. Running it twice is a no-op. Non-``qw_`` indexes are never touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arango.database import StandardDatabase

from apps.core.arango import schema as s
from apps.core.arango.client import sync
from apps.core.clock import now_iso
from config.logging import get_logger

log = get_logger(__name__)


@dataclass
class MigrationReport:
    created_collections: list[str] = field(default_factory=list)
    created_indexes: list[str] = field(default_factory=list)
    replaced_indexes: list[str] = field(default_factory=list)
    dropped_indexes: list[str] = field(default_factory=list)
    view: str = "unchanged"
    graph: str = "unchanged"

    @property
    def changed(self) -> bool:
        return bool(
            self.created_collections
            or self.created_indexes
            or self.replaced_indexes
            or self.dropped_indexes
            or self.view != "unchanged"
            or self.graph != "unchanged"
        )


def _normalize_existing(index: dict[str, Any]) -> dict[str, Any]:
    kind = index.get("type")
    norm: dict[str, Any] = {"type": kind, "fields": list(index.get("fields", []))}
    if kind == "persistent":
        norm["unique"] = bool(index.get("unique", False))
        norm["sparse"] = bool(index.get("sparse", False))
    elif kind == "geo":
        norm["geoJson"] = bool(index.get("geo_json", index.get("geoJson", False)))
    elif kind == "ttl":
        norm["expireAfter"] = int(index.get("expiry_time", index.get("expireAfter", 0)) or 0)
    return norm


def _normalize_declared(spec: s.IndexSpec) -> dict[str, Any]:
    declared = spec.as_arango()
    declared.pop("name")
    return declared


def _reconcile_indexes(
    db: StandardDatabase, spec: s.CollectionSpec, report: MigrationReport, *, drop_undeclared: bool
) -> None:
    collection = db.collection(spec.name)
    existing = {
        str(ix["name"]): ix
        for ix in sync(collection.indexes())
        if str(ix.get("name", "")).startswith("qw_")
    }
    declared = {ix.name: ix for ix in spec.indexes}

    for name, ix_spec in declared.items():
        current = existing.get(name)
        if current is None:
            collection.add_index(ix_spec.as_arango())
            report.created_indexes.append(f"{spec.name}.{name}")
        elif _normalize_existing(current) != _normalize_declared(ix_spec):
            collection.delete_index(current["id"])
            collection.add_index(ix_spec.as_arango())
            report.replaced_indexes.append(f"{spec.name}.{name}")

    if drop_undeclared:
        for name, current in existing.items():
            if name not in declared:
                collection.delete_index(current["id"])
                report.dropped_indexes.append(f"{spec.name}.{name}")


def _schema_payload(rule: dict[str, Any] | None) -> dict[str, Any] | None:
    if rule is None:
        return None
    return {
        "rule": rule,
        "level": "strict",
        "message": "Document does not match the QuakeWatch collection schema.",
    }


def apply_schema(db: StandardDatabase, *, drop_undeclared_indexes: bool = True) -> MigrationReport:
    report = MigrationReport()

    for spec in s.COLLECTIONS:
        if not sync(db.has_collection(spec.name)):
            db.create_collection(spec.name, edge=spec.edge, schema=_schema_payload(spec.rule))
            report.created_collections.append(spec.name)
        elif spec.rule is not None:
            db.collection(spec.name).configure(schema=_schema_payload(spec.rule))
        _reconcile_indexes(db, spec, report, drop_undeclared=drop_undeclared_indexes)

    existing_views = {v["name"] for v in sync(db.views())}
    if s.EVENTS_SEARCH_VIEW not in existing_views:
        db.create_arangosearch_view(
            s.EVENTS_SEARCH_VIEW, properties=s.EVENTS_SEARCH_VIEW_PROPERTIES
        )
        report.view = "created"
    else:
        links_only = {"links": s.EVENTS_SEARCH_VIEW_PROPERTIES["links"]}
        db.update_arangosearch_view(s.EVENTS_SEARCH_VIEW, properties=links_only)

    if not sync(db.has_graph(s.GRAPH_NAME)):
        db.create_graph(s.GRAPH_NAME, edge_definitions=list(s.EDGE_DEFINITIONS))
        report.graph = "created"
    else:
        graph = db.graph(s.GRAPH_NAME)
        current = {d["edge_collection"]: d for d in sync(graph.edge_definitions())}
        for definition in s.EDGE_DEFINITIONS:
            name = definition["edge_collection"]
            if name not in current:
                graph.create_edge_definition(**definition)
                report.graph = "updated"
            elif sorted(current[name]["from_vertex_collections"]) != sorted(
                definition["from_vertex_collections"]
            ) or sorted(current[name]["to_vertex_collections"]) != sorted(
                definition["to_vertex_collections"]
            ):
                graph.replace_edge_definition(**definition)
                report.graph = "updated"

    meta = db.collection(s.SCHEMA_META)
    meta.insert(
        {"_key": "current", "version": s.SCHEMA_VERSION, "applied_at": now_iso()},
        overwrite=True,
    )
    log.info(
        "arango_schema_applied",
        version=s.SCHEMA_VERSION,
        created_collections=report.created_collections,
        created_indexes=report.created_indexes,
        replaced_indexes=report.replaced_indexes,
        dropped_indexes=report.dropped_indexes,
        view=report.view,
        graph=report.graph,
    )
    return report


def applied_version(db: StandardDatabase) -> int | None:
    if not sync(db.has_collection(s.SCHEMA_META)):
        return None
    doc = sync(db.collection(s.SCHEMA_META).get("current"))
    return int(doc["version"]) if isinstance(doc, dict) else None
