"""Alert rule model (pure). Rules are data, never executable user code (ESD §11)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AlertLevel = Literal["green", "yellow", "orange", "red"]
MAX_RULES_PER_USER = 25


class RuleConditions(BaseModel):
    """All given conditions must hold (logical AND). At least one condition is required."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_magnitude: float | None = Field(default=None, ge=-2, le=11)
    maximum_depth_km: float | None = Field(default=None, ge=-10, le=1000)
    minimum_depth_km: float | None = Field(default=None, ge=-10, le=1000)
    center: tuple[float, float] | None = None  # [longitude, latitude] (GeoJSON order, ESD §11)
    radius_km: float | None = Field(default=None, gt=0, le=20_000)
    alert_levels: tuple[AlertLevel, ...] = ()
    tsunami_only: bool = False
    event_types: tuple[str, ...] = ("earthquake",)

    @field_validator("center")
    @classmethod
    def _valid_center(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is None:
            return None
        lon, lat = value
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("center must be [longitude, latitude] within valid ranges")
        return value

    @field_validator("event_types")
    @classmethod
    def _valid_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(sorted({v.strip().lower() for v in value if v.strip()}))
        if len(cleaned) > 10 or any(len(v) > 40 for v in cleaned):
            raise ValueError("at most 10 event types of up to 40 characters")
        return cleaned

    @field_validator("alert_levels")
    @classmethod
    def _sorted_levels(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def _consistent(self) -> RuleConditions:
        if (self.center is None) != (self.radius_km is None):
            raise ValueError("center and radius_km must be given together")
        if (
            self.minimum_depth_km is not None
            and self.maximum_depth_km is not None
            and self.minimum_depth_km > self.maximum_depth_km
        ):
            raise ValueError("minimum_depth_km must be <= maximum_depth_km")
        if not any(
            (
                self.minimum_magnitude is not None,
                self.maximum_depth_km is not None,
                self.minimum_depth_km is not None,
                self.center is not None,
                self.alert_levels,
                self.tsunami_only,
            )
        ):
            raise ValueError(
                "a rule needs at least one condition (magnitude, depth, area, alert level or "
                "tsunami flag); a rule matching every event would only produce noise"
            )
        return self


class RuleInput(BaseModel):
    """Create/replace payload. ``cooldown_minutes`` suppresses repeat notifications (PRD risk)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    conditions: RuleConditions
    cooldown_minutes: int = Field(default=30, ge=0, le=10_080)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("name must not be blank")
        return value


class RulePatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    conditions: RuleConditions | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10_080)

    def apply(self, current: RuleInput) -> RuleInput:
        data: dict[str, Any] = current.model_dump()
        data.update(self.model_dump(exclude_none=True))
        return RuleInput.model_validate(data)
