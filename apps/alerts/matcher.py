"""Deterministic, explainable rule evaluation (FR-11) (pure).

Each condition yields a human-readable clause, e.g. ``magnitude 5.9 >= 5.5`` or
``distance 214 km <= 300 km``. A match lists every satisfied clause; a non-match lists the first
failing clauses. Missing source values never satisfy a condition (we do not invent values).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apps.alerts.domain import RuleConditions
from apps.geo.geodesic import haversine_km


@dataclass(frozen=True, slots=True)
class Evaluation:
    matched: bool
    reasons: tuple[str, ...]
    failed: tuple[str, ...] = field(default=())
    distance_km: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "reason": list(self.reasons),
            "failed": list(self.failed),
            "distance_km": self.distance_km,
        }


def _pair(value: float, threshold: float, *, base: int) -> tuple[str, str]:
    """Format value and threshold with the fewest decimals (>= ``base``) that keep them distinct.

    Prevents explanations that read as contradictions, e.g. "depth 100 km > 100 km" for 100.4.
    """
    decimals = base
    while (
        decimals < 4 and value != threshold and round(value, decimals) == round(threshold, decimals)
    ):
        decimals += 1

    def fmt(x: float) -> str:
        text = f"{x:.{decimals}f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    return fmt(value), fmt(threshold)


def _compare(
    label: str, value: float, op: str, threshold: float, unit: str, base: int
) -> tuple[bool, str]:
    ok = value >= threshold if op == ">=" else value <= threshold
    shown_op = op if ok else ("<" if op == ">=" else ">")
    v, t = _pair(value, threshold, base=base)
    return ok, f"{label} {v}{unit} {shown_op} {t}{unit}"


def evaluate(conditions: RuleConditions, event: Mapping[str, Any]) -> Evaluation:
    passed: list[str] = []
    failed: list[str] = []

    def check(result: tuple[bool, str]) -> None:
        ok, clause = result
        (passed if ok else failed).append(clause)

    event_type = str(event.get("event_type") or "")
    if conditions.event_types:
        check(
            (
                event_type in conditions.event_types,
                f"type {event_type or 'unknown'} in {list(conditions.event_types)}",
            )
        )

    magnitude = event.get("magnitude")
    if conditions.minimum_magnitude is not None:
        if magnitude is None:
            failed.append("magnitude unknown")
        else:
            check(_compare("magnitude", magnitude, ">=", conditions.minimum_magnitude, "", 1))

    depth = event.get("depth_km")
    for bound, op in ((conditions.maximum_depth_km, "<="), (conditions.minimum_depth_km, ">=")):
        if bound is None:
            continue
        if depth is None:
            failed.append("depth unknown")
        else:
            check(_compare("depth", depth, op, bound, " km", 0))

    distance: float | None = None
    if conditions.center is not None and conditions.radius_km is not None:
        lon, lat = conditions.center
        distance = haversine_km(lat, lon, float(event["latitude"]), float(event["longitude"]))
        check(_compare("distance", distance, "<=", conditions.radius_km, " km", 0))

    if conditions.alert_levels:
        level = event.get("alert")
        check(
            (
                level in conditions.alert_levels,
                f"PAGER alert {level or 'none'} in {list(conditions.alert_levels)}",
            )
        )

    if conditions.tsunami_only:
        flagged = bool(event.get("tsunami"))
        check((flagged, "tsunami flag set" if flagged else "tsunami flag not set"))

    return Evaluation(
        matched=not failed,
        reasons=tuple(passed) if not failed else (),
        failed=tuple(failed),
        distance_km=round(distance, 1) if distance is not None else None,
    )
