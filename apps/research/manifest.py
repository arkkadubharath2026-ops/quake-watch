"""Reproducible research exports (FR-13, ESD §12, ADR-006) (pure).

* Rows come from immutable revision snapshots, so a dataset never changes after freezing.
* ``content_sha256`` hashes the canonical JSON-Lines serialisation of the rows (sorted keys,
  compact separators, UTF-8), independent of the download format.
* The zip bundle is byte-for-byte reproducible: sorted entries, fixed timestamps and permissions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Iterable, Sequence
from typing import Any

from apps.geo.regions import REGION_METHOD_VERSION, region_from_place

EXPORT_SCHEMA_VERSION = 1

# (column, provenance) — provenance is shown in the manifest data dictionary.
EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("event_key", "QuakeWatch canonical key"),
    ("source", "source"),
    ("source_event_id", "source (preferred id at the pinned revision)"),
    ("revision_number", "QuakeWatch revision pinned by this snapshot"),
    ("occurred_at", "source (UTC ISO-8601)"),
    ("source_updated_at", "source (UTC ISO-8601)"),
    ("latitude", "source"),
    ("longitude", "source"),
    ("depth_km", "source"),
    ("magnitude", "source"),
    ("magnitude_type", "source"),
    ("place", "source"),
    ("event_type", "source"),
    ("status", "source"),
    ("alert", "source (PAGER)"),
    ("tsunami", "source"),
    ("significance", "source"),
    ("felt", "source (DYFI responses)"),
    ("cdi", "source"),
    ("mmi", "source"),
    ("network", "source"),
    ("station_count", "source (nst)"),
    ("azimuthal_gap_deg", "source (gap)"),
    ("rms_travel_time_residual", "source (rms)"),
    ("region_name", f"derived (place suffix rule, method v{REGION_METHOD_VERSION})"),
    ("payload_hash", "QuakeWatch SHA-256 of the raw source payload"),
)
COLUMN_NAMES = tuple(name for name, _ in EXPORT_COLUMNS)


def export_row(
    event_key: str, revision_number: int, state: dict[str, Any], payload_hash: str
) -> dict[str, Any]:
    region = region_from_place(state.get("place"))
    values: dict[str, Any] = {
        "event_key": event_key,
        "revision_number": revision_number,
        "payload_hash": payload_hash,
        "region_name": region.name if region else None,
    }
    for name in COLUMN_NAMES:
        values.setdefault(name, state.get(name))
    return {name: values[name] for name in COLUMN_NAMES}


def canonical_order(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (r["occurred_at"], r["event_key"]))


def _json_line(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_sha256(rows: Sequence[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_json_line(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def to_csv(rows: Sequence[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMN_NAMES)
    for row in rows:
        writer.writerow(["" if row[c] is None else _cell(row[c]) for c in COLUMN_NAMES])
    return buffer.getvalue().encode("utf-8")


def _cell(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def to_json(rows: Sequence[dict[str, Any]], manifest: dict[str, Any]) -> bytes:
    document = {"manifest": manifest, "rows": list(rows)}
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def build_manifest(
    *,
    snapshot_id: str,
    created_at: str,
    title: str,
    notes: str,
    query_definition: dict[str, Any],
    row_count: int,
    content_hash: str,
    application_version: str,
    database_schema_version: int,
    event_document_version: int,
    revision_policy_version: int,
    source_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "title": title,
        "notes": notes,
        "created_at": created_at,
        "source": "USGS",
        "attribution": "Earthquake data courtesy of the U.S. Geological Survey (USGS).",
        "query_definition": query_definition,
        "row_count": row_count,
        "content_sha256": content_hash,
        "content_sha256_definition": "SHA-256 of the rows as JSON Lines (sorted keys, compact "
        "separators, UTF-8, one row per line, rows ordered by occurred_at then event_key)",
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "database_schema_version": database_schema_version,
        "event_document_version": event_document_version,
        "revision_policy_version": revision_policy_version,
        "application_version": application_version,
        "columns": [{"name": n, "provenance": p} for n, p in EXPORT_COLUMNS],
        "source_request_manifest": source_requests,
        "limitations": [
            "Values are as published by USGS at the pinned revision; later revisions are not "
            "reflected (by design, for reproducibility).",
            "region_name is derived by QuakeWatch from the place text and is not a USGS value.",
            "Raw source payloads are retained for a limited period; payload_hash identifies them.",
        ],
    }


_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def bundle(files: dict[str, bytes]) -> bytes:
    """Deterministic zip: sorted names, fixed timestamps/permissions, plus SHA256SUMS."""
    sums = "".join(f"{hashlib.sha256(files[n]).hexdigest()}  {n}\n" for n in sorted(files))
    entries = {**files, "SHA256SUMS": sums.encode("utf-8")}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, entries[name])
    return buffer.getvalue()
