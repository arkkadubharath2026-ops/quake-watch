"""Versioned meaningful-revision policy (ESD §8) (pure).

A *revision* is recorded only when a tracked source field changes beyond its tolerance. Operational
metadata (``last_seen_at`` …) and noisy/secondary source fields (felt count, significance, station
quality metrics, URLs, contributor list) update the canonical record without creating a revision.

Changing any rule here requires bumping ``POLICY_VERSION`` (stored on every event and revision), so
revision analytics can always be interpreted against the policy that produced them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from apps.core.clock import from_iso

POLICY_VERSION = 1

Kind = Literal["exact", "numeric", "timestamp", "set"]


@dataclass(frozen=True, slots=True)
class FieldRule:
    kind: Kind
    tolerance: float = 0.0  # numeric: absolute units; timestamp: seconds
    rationale: str = ""


TRACKED_FIELDS: dict[str, FieldRule] = {
    "source_event_id": FieldRule("exact", rationale="preferred event id changed (association)"),
    "event_type": FieldRule("exact", rationale="reclassification, e.g. earthquake→quarry blast"),
    "magnitude": FieldRule("numeric", 0.005, "USGS reports to 0.01; any reported change counts"),
    "magnitude_type": FieldRule("exact", rationale="method change, e.g. ml→mww"),
    "depth_km": FieldRule("numeric", 0.1, "sub-100 m depth jitter is not analytically meaningful"),
    "latitude": FieldRule("numeric", 0.001, "~111 m; below this is float/rounding noise"),
    "longitude": FieldRule("numeric", 0.001, "~111 m at the equator"),
    "occurred_at": FieldRule("timestamp", 0.1, "origin-time relocations"),
    "place": FieldRule("exact"),
    "status": FieldRule("exact", rationale="automatic→reviewed is key for RQ1"),
    "alert": FieldRule("exact", rationale="PAGER alert level"),
    "tsunami": FieldRule("exact"),
    "mmi": FieldRule("numeric", 0.05, "ShakeMap max intensity"),
    "cdi": FieldRule("numeric", 0.05, "DYFI max intensity"),
    "products": FieldRule("set", rationale="scientific product availability"),
}

UNTRACKED_FIELDS: tuple[str, ...] = (
    "associated_ids",
    "felt",
    "significance",
    "network",
    "contributors",
    "detail_url",
    "event_page_url",
    "source_updated_at",
    "station_count",
    "min_station_distance_deg",
    "rms_travel_time_residual",
    "azimuthal_gap_deg",
)


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    before: Any
    after: Any


def _numeric_changed(before: Any, after: Any, tolerance: float) -> bool:
    if before is None or after is None:
        return before is not after
    return math.fabs(float(after) - float(before)) > tolerance


def _timestamp_changed(before: Any, after: Any, tolerance: float) -> bool:
    if before is None or after is None:
        return before is not after
    b: datetime = from_iso(before) if isinstance(before, str) else before
    a: datetime = from_iso(after) if isinstance(after, str) else after
    return abs((a - b).total_seconds()) > tolerance


def field_changed(rule: FieldRule, before: Any, after: Any) -> bool:
    if rule.kind == "numeric":
        return _numeric_changed(before, after, rule.tolerance)
    if rule.kind == "timestamp":
        return _timestamp_changed(before, after, rule.tolerance)
    if rule.kind == "set":
        return set(before or ()) != set(after or ())
    return bool(before != after)


def diff(before: dict[str, Any], after: dict[str, Any]) -> list[FieldChange]:
    """Meaningful changes between two source states (ordered as in ``TRACKED_FIELDS``)."""
    changes: list[FieldChange] = []
    for name, rule in TRACKED_FIELDS.items():
        old, new = before.get(name), after.get(name)
        if field_changed(rule, old, new):
            changes.append(FieldChange(name, old, new))
    return changes


def untracked_changed(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [name for name in UNTRACKED_FIELDS if before.get(name) != after.get(name)]
