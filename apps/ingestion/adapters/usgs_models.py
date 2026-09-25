"""Strict contract for USGS GeoJSON payloads (summary feed, catalog query, detail feed).

These models describe what QuakeWatch relies on. Unknown extra keys are tolerated (USGS adds
fields over time), but missing/mistyped required keys raise, which the contract tests turn into
an early warning of upstream schema changes (PRD risk "source schema changes").
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class UsgsPointGeometry(_Lenient):
    type: Literal["Point"]
    coordinates: list[float | None] = Field(min_length=2, max_length=3)


class UsgsProperties(_Lenient):
    mag: float | None = None
    place: str | None = None
    time: int
    updated: int
    url: str | None = None
    detail: str | None = None
    felt: int | None = None
    cdi: float | None = None
    mmi: float | None = None
    alert: str | None = None
    status: str
    tsunami: int
    sig: int | None = None
    net: str | None = None
    code: str | None = None
    ids: str | None = None
    sources: str | None = None
    types: str | None = None
    nst: int | None = None
    dmin: float | None = None
    rms: float | None = None
    gap: float | None = None
    magType: str | None = None
    type: str


class UsgsFeature(_Lenient):
    type: Literal["Feature"]
    id: str
    properties: UsgsProperties
    geometry: UsgsPointGeometry | None


class UsgsFeedMetadata(_Lenient):
    generated: int
    url: str
    title: str | None = None
    status: int
    api: str | None = None
    # Summary feeds and un-limited queries report ``count``; queries sent with ``limit`` report
    # ``limit``/``offset`` instead (observed on the live FDSN API, 2026-09).
    count: int | None = None
    limit: int | None = None
    offset: int | None = None


class UsgsFeatureCollection(_Lenient):
    """Top level only; features are validated one by one so a bad record never sinks a feed."""

    type: Literal["FeatureCollection"]
    metadata: UsgsFeedMetadata
    features: list[dict[str, Any]]


class UsgsCatalogCount(_Lenient):
    count: int = Field(ge=0)
    maxAllowed: int = Field(gt=0)


class UsgsProduct(_Lenient):
    id: str
    type: str
    code: str
    source: str
    status: str
    updateTime: int
    preferredWeight: int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class UsgsDetailProperties(UsgsProperties):
    products: dict[str, list[UsgsProduct]] = Field(default_factory=dict)


class UsgsDetailFeature(_Lenient):
    type: Literal["Feature"]
    id: str
    properties: UsgsDetailProperties
    geometry: UsgsPointGeometry | None
