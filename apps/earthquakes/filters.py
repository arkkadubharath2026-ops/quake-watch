"""Event filter model (pure): parsing, validation, canonical form and human summary (FR-06).

The same :class:`EventFilter` drives the explorer API, the map, saved searches (L4) and research
snapshots (L4). ``canonical()`` is deterministic (sorted keys/values, ISO timestamps), so a saved
query or research manifest reproduces exactly the same selection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from apps.core.clock import to_iso
from apps.core.errors import ValidationFailed
from apps.geo.geodesic import BoundingBox, InvalidGeometry, validate_lat_lon, validate_radius_km

SORT_FIELDS: dict[str, str] = {
    "occurred_at": "occurred_at",
    "magnitude": "magnitude",
    "depth": "depth_km",
    "significance": "significance",
    "revisions": "revision_count",
    "updated": "source_updated_at",
}
ALERTS = ("green", "yellow", "orange", "red", "none")
STATUSES = ("automatic", "reviewed", "deleted")
MAX_TEXT = 100
MAX_LIST = 20

SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class Radius:
    latitude: float
    longitude: float
    radius_km: float


@dataclass(frozen=True)
class EventFilter:
    start: datetime | None = None
    end: datetime | None = None
    min_magnitude: float | None = None
    max_magnitude: float | None = None
    min_depth_km: float | None = None
    max_depth_km: float | None = None
    bbox: BoundingBox | None = None
    radius: Radius | None = None
    alerts: tuple[str, ...] = ()
    tsunami: bool | None = None
    statuses: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    text: str | None = None
    sort: str = "occurred_at"
    direction: SortDirection = "desc"

    # ---- construction -------------------------------------------------------------------------
    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> EventFilter:
        """Parse query parameters (strings) or a canonical dict; raise ValidationFailed on error."""
        errors: dict[str, str] = {}

        def text(name: str) -> str | None:
            raw = params.get(name)
            if raw is None:
                return None
            value = str(raw).strip()
            return value or None

        def number(name: str, lo: float, hi: float) -> float | None:
            raw = text(name)
            if raw is None:
                return None
            try:
                value = float(raw)
            except ValueError:
                errors[name] = "must be a number"
                return None
            if not lo <= value <= hi:
                errors[name] = f"must be between {lo:g} and {hi:g}"
                return None
            return value

        def timestamp(name: str) -> datetime | None:
            raw = text(name)
            if raw is None:
                return None
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                errors[name] = "must be an ISO-8601 date or datetime"
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)  # naive input = UTC

        def listing(name: str, allowed: tuple[str, ...] | None = None) -> tuple[str, ...]:
            raw = params.get(name)
            if raw is None or raw == "":
                return ()
            items = raw if isinstance(raw, list | tuple) else str(raw).split(",")
            values = tuple(sorted({str(v).strip().lower() for v in items if str(v).strip()}))
            if len(values) > MAX_LIST:
                errors[name] = f"at most {MAX_LIST} values"
                return ()
            if allowed is not None:
                bad = [v for v in values if v not in allowed]
                if bad:
                    errors[name] = f"unknown value(s) {bad}; allowed: {list(allowed)}"
                    return ()
            elif any(not v.replace("-", "").replace(" ", "").isalnum() for v in values):
                errors[name] = "values must be alphanumeric"
                return ()
            return values

        start, end = timestamp("start"), timestamp("end")
        if start and end and start >= end:
            errors["end"] = "must be after start"

        min_mag = number("min_magnitude", -2, 11)
        max_mag = number("max_magnitude", -2, 11)
        if min_mag is not None and max_mag is not None and min_mag > max_mag:
            errors["max_magnitude"] = "must be >= min_magnitude"
        min_depth = number("min_depth_km", -10, 1000)
        max_depth = number("max_depth_km", -10, 1000)
        if min_depth is not None and max_depth is not None and min_depth > max_depth:
            errors["max_depth_km"] = "must be >= min_depth_km"

        bbox = None
        if (raw_bbox := text("bbox")) is not None:
            try:
                bbox = BoundingBox.parse(raw_bbox)
            except InvalidGeometry as exc:
                errors["bbox"] = str(exc)

        radius = None
        lat, lon, rad = text("lat"), text("lon"), text("radius_km")
        if any(v is not None for v in (lat, lon, rad)):
            try:
                if lat is None or lon is None or rad is None:
                    raise InvalidGeometry("lat, lon and radius_km must be given together")
                radius = Radius(float(lat), float(lon), float(rad))
                validate_lat_lon(radius.latitude, radius.longitude)
                validate_radius_km(radius.radius_km)
            except (InvalidGeometry, ValueError) as exc:
                errors["radius_km"] = str(exc) if isinstance(exc, InvalidGeometry) else "invalid"
                radius = None
        if bbox is not None and radius is not None:
            errors["bbox"] = "use either bbox or a radius, not both"

        tsunami = None
        if (raw_tsunami := text("tsunami")) is not None:
            lowered = raw_tsunami.lower()
            if lowered in ("true", "1", "yes"):
                tsunami = True
            elif lowered in ("false", "0", "no"):
                tsunami = False
            else:
                errors["tsunami"] = "must be true or false"

        query_text = text("q")
        if query_text is not None and len(query_text) > MAX_TEXT:
            errors["q"] = f"at most {MAX_TEXT} characters"

        sort = text("sort") or "occurred_at"
        direction = (text("direction") or "desc").lower()
        if sort not in SORT_FIELDS:
            errors["sort"] = f"must be one of {sorted(SORT_FIELDS)}"
        if direction not in ("asc", "desc"):
            errors["direction"] = "must be asc or desc"

        alerts = listing("alert", ALERTS)
        statuses = listing("status", STATUSES)
        networks = listing("network")
        event_types = listing("event_type")

        if errors:
            raise ValidationFailed("Invalid event filters.", details={"fields": errors})
        return cls(
            start=start,
            end=end,
            min_magnitude=min_mag,
            max_magnitude=max_mag,
            min_depth_km=min_depth,
            max_depth_km=max_depth,
            bbox=bbox,
            radius=radius,
            alerts=alerts,
            tsunami=tsunami,
            statuses=statuses,
            networks=networks,
            event_types=event_types,
            text=query_text,
            sort=sort,
            direction=direction,  # type: ignore[arg-type]  # validated above
        )

    # ---- representations ----------------------------------------------------------------------
    def canonical(self) -> dict[str, Any]:
        """Deterministic, JSON-safe representation (only set fields; sorted keys)."""
        data: dict[str, Any] = {}
        if self.start:
            data["start"] = to_iso(self.start)
        if self.end:
            data["end"] = to_iso(self.end)
        for name in ("min_magnitude", "max_magnitude", "min_depth_km", "max_depth_km"):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        if self.bbox:
            b = self.bbox
            data["bbox"] = f"{b.south:g},{b.west:g},{b.north:g},{b.east:g}"
        if self.radius:
            data["lat"] = self.radius.latitude
            data["lon"] = self.radius.longitude
            data["radius_km"] = self.radius.radius_km
        for name, key in (
            ("alerts", "alert"),
            ("statuses", "status"),
            ("networks", "network"),
            ("event_types", "event_type"),
        ):
            values = getattr(self, name)
            if values:
                data[key] = ",".join(values)
        if self.tsunami is not None:
            data["tsunami"] = "true" if self.tsunami else "false"
        if self.text:
            data["q"] = self.text
        data["sort"] = self.sort
        data["direction"] = self.direction
        return dict(sorted(data.items()))

    def summary(self) -> str:
        """Human-readable query summary for the explorer and exports."""
        parts: list[str] = []
        if self.start or self.end:
            start = to_iso(self.start)[:16] if self.start else "…"
            end = to_iso(self.end)[:16] if self.end else "now"
            parts.append(f"time {start} to {end} UTC")
        if self.min_magnitude is not None or self.max_magnitude is not None:
            lo = f"{self.min_magnitude:g}" if self.min_magnitude is not None else "any"
            hi = f"{self.max_magnitude:g}" if self.max_magnitude is not None else "any"
            parts.append(f"magnitude {lo} to {hi}")
        if self.min_depth_km is not None or self.max_depth_km is not None:
            lo = f"{self.min_depth_km:g}" if self.min_depth_km is not None else "any"
            hi = f"{self.max_depth_km:g}" if self.max_depth_km is not None else "any"
            parts.append(f"depth {lo} to {hi} km")
        if self.radius:
            r = self.radius
            parts.append(f"within {r.radius_km:g} km of ({r.latitude:g}, {r.longitude:g})")
        if self.bbox:
            parts.append("inside the map viewport")
        if self.alerts:
            parts.append("alert " + "/".join(self.alerts))
        if self.tsunami is not None:
            parts.append("tsunami flag " + ("set" if self.tsunami else "not set"))
        if self.statuses:
            parts.append("status " + "/".join(self.statuses))
        if self.networks:
            parts.append("network " + "/".join(self.networks))
        if self.event_types:
            parts.append("type " + "/".join(self.event_types))
        if self.text:
            parts.append(f'location matches "{self.text}"')
        body = "; ".join(parts) if parts else "all events"
        return f"{body} — sorted by {self.sort} {self.direction}"
