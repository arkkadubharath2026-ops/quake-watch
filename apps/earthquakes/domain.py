"""Earthquake domain model (pure).

:class:`CanonicalEventInput` is the source-neutral structure every source adapter normalises into
(ESD §4.1). ``to_state()`` produces the JSON-safe *source state* that is persisted on the canonical
event and snapshotted in each revision; it contains only source values — never derived or
operational fields (ADR-010).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.core.clock import to_iso

Source = Literal["USGS"]
EventStatus = Literal["automatic", "reviewed", "deleted"]
AlertLevel = Literal["green", "yellow", "orange", "red"]

SCHEMA_VERSION = 1
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def event_key(source: str, source_event_id: str) -> str:
    """Deterministic ArangoDB ``_key`` for the first-seen identity of a source event."""
    return f"{source.lower()}_{source_event_id}"


class CanonicalEventInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Source
    source_event_id: str
    associated_ids: tuple[str, ...] = Field(min_length=1)
    event_type: str = Field(min_length=1, max_length=40)
    magnitude: float | None = Field(default=None, ge=-2, le=11)
    magnitude_type: str | None = Field(default=None, max_length=16)
    place: str | None = Field(default=None, max_length=300)
    occurred_at: datetime
    source_updated_at: datetime
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    depth_km: float | None = Field(default=None, ge=-10, le=1000)
    felt: int | None = Field(default=None, ge=0)
    cdi: float | None = Field(default=None, ge=0, le=12)
    mmi: float | None = Field(default=None, ge=0, le=12)
    alert: AlertLevel | None = None
    status: EventStatus
    tsunami: bool
    significance: int | None = Field(default=None, ge=0)
    network: str | None = Field(default=None, max_length=16)
    contributors: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    detail_url: str | None = Field(default=None, max_length=500)
    event_page_url: str | None = Field(default=None, max_length=500)
    station_count: int | None = Field(default=None, ge=0)
    min_station_distance_deg: float | None = Field(default=None, ge=0)
    rms_travel_time_residual: float | None = Field(default=None, ge=0)
    azimuthal_gap_deg: float | None = Field(default=None, ge=0, le=360)

    @field_validator("source_event_id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError("source_event_id must match [A-Za-z0-9_-]{1,64}")
        return value

    @field_validator("associated_ids")
    @classmethod
    def _valid_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not _ID_RE.match(item):
                raise ValueError(f"invalid associated id {item!r}")
        return tuple(sorted(set(value)))

    @field_validator("occurred_at", "source_updated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _id_in_associated(self) -> CanonicalEventInput:
        if self.source_event_id not in self.associated_ids:
            raise ValueError("source_event_id must be one of associated_ids")
        return self

    @property
    def key(self) -> str:
        return event_key(self.source, self.source_event_id)

    def to_state(self) -> dict[str, Any]:
        """JSON-safe source state (persisted on the event and in revision snapshots)."""
        data = self.model_dump(mode="python")
        data["occurred_at"] = to_iso(self.occurred_at)
        data["source_updated_at"] = to_iso(self.source_updated_at)
        data["associated_ids"] = list(self.associated_ids)
        data["contributors"] = list(self.contributors)
        data["products"] = list(self.products)
        return data


SOURCE_STATE_FIELDS: tuple[str, ...] = tuple(CanonicalEventInput.model_fields)

# Products whose availability the UI surfaces (USGS product type -> label).
KEY_PRODUCTS: dict[str, str] = {
    "shakemap": "ShakeMap",
    "losspager": "PAGER",
    "dyfi": "Did You Feel It?",
    "moment-tensor": "Moment tensor",
    "finite-fault": "Finite fault",
    "ground-failure": "Ground failure",
    "oaf": "Aftershock forecast",
}


IMPORTANT_MAGNITUDE = 6.0
IMPORTANT_SIGNIFICANCE = 600


def is_important(event: CanonicalEventInput) -> bool:
    """Events that get eager detail enrichment (ESD §4.3 "important events")."""
    return (
        (event.magnitude is not None and event.magnitude >= IMPORTANT_MAGNITUDE)
        or (event.significance is not None and event.significance >= IMPORTANT_SIGNIFICANCE)
        or event.alert is not None
        or event.tsunami
    )
