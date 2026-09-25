"""Research snapshot use cases: freeze a query, verify, export with a manifest (FR-13, ADR-006)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from apps.core.arango.schema import SCHEMA_VERSION as DATABASE_SCHEMA_VERSION
from apps.core.clock import now_iso
from apps.core.errors import Conflict, NotFound, QuakeWatchError, ValidationFailed
from apps.earthquakes.domain import SCHEMA_VERSION as EVENT_DOCUMENT_VERSION
from apps.earthquakes.filters import EventFilter
from apps.ingestion.revision_policy import POLICY_VERSION
from apps.research import manifest as m

MAX_SNAPSHOT_ROWS = 50_000
MAX_SNAPSHOTS_PER_USER = 20
ExportFormat = Literal["zip", "csv", "json"]


class SnapshotStore(Protocol):
    def freeze_members(self, f: EventFilter, *, limit: int) -> list[list[Any]]: ...
    def pinned_revisions(self, members: list[list[Any]]) -> list[dict[str, Any]]: ...
    def source_requests(self, run_ids: list[str]) -> list[dict[str, Any]]: ...
    def insert_capped(self, doc: dict[str, Any], *, max_per_user: int) -> bool: ...
    def list_for_user(self, user_id: int) -> list[dict[str, Any]]: ...
    def get(self, user_id: int, snapshot_id: str) -> dict[str, Any] | None: ...
    def delete(self, user_id: int, snapshot_id: str) -> bool: ...


class IntegrityError(QuakeWatchError):
    code = "integrity_error"
    http_status = 500


@dataclass(frozen=True, slots=True)
class ExportFile:
    filename: str
    content_type: str
    content: bytes
    content_sha256: str


def _text(payload: dict[str, Any], name: str, *, max_len: int, required: bool) -> str:
    value = " ".join(str(payload.get(name) or "").split())
    if required and not value:
        raise ValidationFailed("Invalid snapshot.", details={"fields": {name: "required"}})
    if len(value) > max_len:
        raise ValidationFailed(
            "Invalid snapshot.", details={"fields": {name: f"at most {max_len} characters"}}
        )
    return value


class ResearchService:
    def __init__(self, store: SnapshotStore, *, application_version: str) -> None:
        self.store = store
        self.application_version = application_version

    def create(self, user_id: int, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationFailed("Invalid snapshot.", details={"fields": {"body": "object"}})
        title = _text(payload, "title", max_len=200, required=True)
        notes = _text(payload, "notes", max_len=4000, required=False)
        raw_filters = payload.get("filters") or {}
        if not isinstance(raw_filters, dict):
            raise ValidationFailed("Invalid snapshot.", details={"fields": {"filters": "object"}})
        f = EventFilter.from_params(raw_filters)

        members = self.store.freeze_members(f, limit=MAX_SNAPSHOT_ROWS)
        if len(members) > MAX_SNAPSHOT_ROWS:
            raise ValidationFailed(
                f"The query matches more than {MAX_SNAPSHOT_ROWS} events; narrow the filters.",
                details={"fields": {"filters": "too many matching events"}},
            )
        rows, run_ids = self._reconstruct(members)
        snapshot_id = uuid.uuid4().hex
        created_at = now_iso()
        query_definition = {"filters": f.canonical(), "summary": f.summary()}
        content_hash = m.content_sha256(rows)
        manifest = m.build_manifest(
            snapshot_id=snapshot_id,
            created_at=created_at,
            title=title,
            notes=notes,
            query_definition=query_definition,
            row_count=len(rows),
            content_hash=content_hash,
            application_version=self.application_version,
            database_schema_version=DATABASE_SCHEMA_VERSION,
            event_document_version=EVENT_DOCUMENT_VERSION,
            revision_policy_version=POLICY_VERSION,
            source_requests=self.store.source_requests(run_ids),
        )
        inserted = self.store.insert_capped(
            {
                "_key": snapshot_id,
                "user_id": user_id,
                "title": title,
                "notes": notes,
                "created_at": created_at,
                "query_definition": query_definition,
                "members": members,
                "row_count": len(rows),
                "content_sha256": content_hash,
                "application_version": self.application_version,
                "manifest": manifest,
            },
            max_per_user=MAX_SNAPSHOTS_PER_USER,
        )
        if not inserted:
            raise Conflict(
                f"Snapshot limit reached ({MAX_SNAPSHOTS_PER_USER}); delete an old snapshot first."
            )
        return {"id": snapshot_id, **self._summary(manifest)}

    def _reconstruct(self, members: list[list[Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        pinned = self.store.pinned_revisions(members)
        missing = [p["missing"] for p in pinned if "missing" in p]
        if missing:
            raise IntegrityError(
                "Pinned revisions are missing; the snapshot cannot be reproduced.",
                details={"missing": missing[:20]},
            )
        rows = m.canonical_order(
            m.export_row(p["event_key"], p["revision_number"], p["state"], p["payload_hash"])
            for p in pinned
        )
        run_ids = sorted({p["ingestion_run_id"] for p in pinned if p.get("ingestion_run_id")})
        return rows, run_ids

    @staticmethod
    def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": manifest["title"],
            "created_at": manifest["created_at"],
            "row_count": manifest["row_count"],
            "content_sha256": manifest["content_sha256"],
            "query_definition": manifest["query_definition"],
            "application_version": manifest["application_version"],
        }

    def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        return self.store.list_for_user(user_id)

    def get(self, user_id: int, snapshot_id: str) -> dict[str, Any]:
        snapshot = self.store.get(user_id, snapshot_id)
        if snapshot is None:
            raise NotFound("Research snapshot not found.")
        return {"id": snapshot["_key"], "manifest": snapshot["manifest"]}

    def delete(self, user_id: int, snapshot_id: str) -> None:
        if not self.store.delete(user_id, snapshot_id):
            raise NotFound("Research snapshot not found.")

    def export(self, user_id: int, snapshot_id: str, fmt: str) -> ExportFile:
        if fmt not in ("zip", "csv", "json"):
            raise ValidationFailed(
                "Invalid format.", details={"fields": {"format": "zip|csv|json"}}
            )
        snapshot = self.store.get(user_id, snapshot_id)
        if snapshot is None:
            raise NotFound("Research snapshot not found.")
        rows, _ = self._reconstruct(snapshot["members"])
        digest = m.content_sha256(rows)
        if digest != snapshot["content_sha256"]:  # immutable revisions make this impossible
            raise IntegrityError(
                "Snapshot content does not match its recorded checksum.",
                details={"expected": snapshot["content_sha256"], "actual": digest},
            )
        manifest = snapshot["manifest"]
        base = f"quakewatch-snapshot-{snapshot_id[:12]}"
        csv_bytes = m.to_csv(rows)
        if fmt == "csv":
            return ExportFile(f"{base}.csv", "text/csv; charset=utf-8", csv_bytes, digest)
        json_bytes = m.to_json(rows, manifest)
        if fmt == "json":
            return ExportFile(f"{base}.json", "application/json", json_bytes, digest)
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        archive = m.bundle(
            {"data.csv": csv_bytes, "data.json": json_bytes, "manifest.json": manifest_bytes}
        )
        return ExportFile(f"{base}.zip", "application/zip", archive, digest)
