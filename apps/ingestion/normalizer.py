"""USGS GeoJSON → :class:`CanonicalEventInput` (pure).

A feed is parsed in two stages: the envelope must be a valid FeatureCollection (otherwise the whole
fetch is a source-schema error), then each feature is normalised independently. A feature that
fails validation becomes a :class:`RecordRejected` with a machine-readable reason and is routed to
dead letters by the pipeline; the rest of the feed still ingests (PRD NFR reliability).

Principle "never invent missing scientific values": absent/None source values stay None. The only
coercions are representational (epoch ms → UTC datetime, ``tsunami`` 0/1 → bool, CSV lists →
tuples) and are listed in docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from apps.core.clock import from_epoch_ms
from apps.core.errors import SourceSchemaError
from apps.earthquakes.domain import CanonicalEventInput, Source
from apps.ingestion.adapters.usgs_models import (
    UsgsFeature,
    UsgsFeatureCollection,
    UsgsFeedMetadata,
)

SOURCE: Source = "USGS"
KNOWN_ALERTS = {"green", "yellow", "orange", "red"}
KNOWN_STATUSES = {"automatic", "reviewed", "deleted"}


@dataclass(frozen=True, slots=True)
class RecordRejected:
    reason: str
    detail: str
    source_event_id: str | None
    payload_hash: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    event: CanonicalEventInput
    payload_hash: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ParsedFeed:
    metadata: UsgsFeedMetadata
    records: list[NormalizedRecord]
    rejected: list[RecordRejected]


def payload_hash(payload: dict[str, Any]) -> str:
    """Stable SHA-256 of a JSON payload (sorted keys, compact separators)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(sorted({part.strip() for part in value.split(",") if part.strip()}))


def parse_feed(body: bytes) -> ParsedFeed:
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceSchemaError(f"feed is not valid JSON: {exc}") from exc
    try:
        collection = UsgsFeatureCollection.model_validate(document)
    except ValidationError as exc:
        raise SourceSchemaError(
            "feed envelope does not match the USGS FeatureCollection contract",
            details={"errors": exc.errors(include_url=False)[:10]},
        ) from exc

    records: list[NormalizedRecord] = []
    rejected: list[RecordRejected] = []
    for raw in collection.features:
        result = normalize_feature(raw)
        if isinstance(result, NormalizedRecord):
            records.append(result)
        else:
            rejected.append(result)
    return ParsedFeed(metadata=collection.metadata, records=records, rejected=rejected)


def normalize_feature(raw: Any) -> NormalizedRecord | RecordRejected:
    if not isinstance(raw, dict):
        return RecordRejected("not_an_object", type(raw).__name__, None, payload_hash({}), {})
    digest = payload_hash(raw)
    raw_id = raw.get("id") if isinstance(raw.get("id"), str) else None

    def reject(reason: str, detail: str) -> RecordRejected:
        return RecordRejected(reason, detail[:1000], raw_id, digest, raw)

    try:
        feature = UsgsFeature.model_validate(raw)
    except ValidationError as exc:
        return reject("contract_violation", _summarize(exc))

    props = feature.properties
    if feature.geometry is None:
        return reject("missing_geometry", "feature has no geometry")
    coords = feature.geometry.coordinates
    lon, lat = coords[0], coords[1]
    depth = coords[2] if len(coords) > 2 else None
    if lon is None or lat is None:
        return reject("missing_coordinates", f"coordinates={coords!r}")
    if props.status not in KNOWN_STATUSES:
        return reject("unknown_status", f"status={props.status!r}")
    alert = props.alert.lower() if isinstance(props.alert, str) else None
    if alert is not None and alert not in KNOWN_ALERTS:
        return reject("unknown_alert", f"alert={props.alert!r}")

    associated = set(_csv(props.ids)) | {feature.id}
    try:
        event = CanonicalEventInput(
            source=SOURCE,
            source_event_id=feature.id,
            associated_ids=tuple(associated),
            event_type=props.type,
            magnitude=props.mag,
            magnitude_type=props.magType,
            place=props.place,
            occurred_at=from_epoch_ms(props.time),
            source_updated_at=from_epoch_ms(props.updated),
            longitude=lon,
            latitude=lat,
            depth_km=depth,
            felt=props.felt,
            cdi=props.cdi,
            mmi=props.mmi,
            alert=alert,  # type: ignore[arg-type]  # checked against KNOWN_ALERTS above
            status=props.status,  # type: ignore[arg-type]  # checked against KNOWN_STATUSES above
            tsunami=bool(props.tsunami),
            significance=props.sig,
            network=props.net,
            contributors=_csv(props.sources),
            products=_csv(props.types),
            detail_url=props.detail,
            event_page_url=props.url,
            station_count=props.nst,
            min_station_distance_deg=props.dmin,
            rms_travel_time_residual=props.rms,
            azimuthal_gap_deg=props.gap,
        )
    except ValidationError as exc:
        return reject("value_out_of_range", _summarize(exc))
    except (OverflowError, OSError, ValueError) as exc:  # e.g. absurd epoch values
        return reject("invalid_timestamp", str(exc))
    return NormalizedRecord(event=event, payload_hash=digest, payload=raw)


def _summarize(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors(include_url=False)[:5]:
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
