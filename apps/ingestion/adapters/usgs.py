"""USGS Earthquake Hazards Program adapter (summary feeds, FDSN catalog, detail feed).

URLs are built only from validated inputs (allow-listed feed names, strict event-id pattern,
ISO timestamps), so no caller-controlled string can redirect requests elsewhere (SSRF safety).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from apps.core.clock import to_iso
from apps.core.errors import SourceSchemaError, ValidationFailed
from apps.core.resilience import CircuitBreaker
from apps.ingestion.adapters.http import FetchResult, ResilientHttpClient, SourceRequest
from apps.ingestion.adapters.usgs_models import UsgsCatalogCount, UsgsDetailFeature
from config.env import get_settings

SOURCE = "USGS"
CATALOG_MAX_LIMIT = 20_000
_FEED_RE = re.compile(r"^(significant|4\.5|2\.5|1\.0|all)_(hour|day|week|month)$")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True, slots=True)
class CatalogCount:
    count: int
    max_allowed: int
    request: SourceRequest


@dataclass(frozen=True, slots=True)
class DetailResult:
    feature: UsgsDetailFeature
    request: SourceRequest


def _fdsn_time(value: datetime) -> str:
    return to_iso(value)[:-1]  # FDSN accepts ISO without the trailing Z (UTC implied)


class UsgsClient:
    def __init__(self, http: ResilientHttpClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def close(self) -> None:
        self._http.close()

    def summary_feed(self, feed: str) -> FetchResult:
        if not _FEED_RE.match(feed):
            raise ValidationFailed(f"unknown USGS summary feed {feed!r}")
        return self._http.get(f"{self._base}/earthquakes/feed/v1.0/summary/{feed}.geojson")

    def _catalog_params(
        self, start: datetime, end: datetime, min_magnitude: float | None
    ) -> dict[str, str]:
        if end <= start:
            raise ValidationFailed("catalog window end must be after start")
        params = {
            "format": "geojson",
            "starttime": _fdsn_time(start),
            "endtime": _fdsn_time(end),
        }
        if min_magnitude is not None:
            params["minmagnitude"] = f"{min_magnitude:g}"
        return params

    def catalog_count(
        self, *, start: datetime, end: datetime, min_magnitude: float | None
    ) -> CatalogCount:
        result = self._http.get(
            f"{self._base}/fdsnws/event/1/count",
            self._catalog_params(start, end, min_magnitude),
        )
        try:
            parsed = UsgsCatalogCount.model_validate_json(result.body)
        except ValidationError as exc:
            raise SourceSchemaError(f"unexpected catalog count payload: {exc}") from exc
        return CatalogCount(parsed.count, parsed.maxAllowed, result.request)

    def catalog_query(
        self, *, start: datetime, end: datetime, min_magnitude: float | None
    ) -> FetchResult:
        params = self._catalog_params(start, end, min_magnitude)
        params.update({"orderby": "time-asc", "limit": str(CATALOG_MAX_LIMIT)})
        return self._http.get(f"{self._base}/fdsnws/event/1/query", params)

    def detail(self, source_event_id: str) -> DetailResult:
        if not _EVENT_ID_RE.match(source_event_id):
            raise ValidationFailed("invalid event id")
        result = self._http.get(
            f"{self._base}/earthquakes/feed/v1.0/detail/{source_event_id}.geojson"
        )
        try:
            feature = UsgsDetailFeature.model_validate_json(result.body)
        except ValidationError as exc:
            raise SourceSchemaError(f"unexpected detail payload: {exc}") from exc
        return DetailResult(feature, result.request)


def usgs_breaker() -> CircuitBreaker:
    cfg = get_settings()
    return CircuitBreaker(
        SOURCE,
        failure_threshold=cfg.circuit_failure_threshold,
        reset_seconds=cfg.circuit_reset_seconds,
    )


def build_usgs_client() -> UsgsClient:
    cfg = get_settings()
    http = ResilientHttpClient(
        source=SOURCE,
        breaker=usgs_breaker(),
        connect_timeout=cfg.http_connect_timeout,
        read_timeout=cfg.http_read_timeout,
        max_retries=cfg.http_max_retries,
        user_agent=f"QuakeWatch/{cfg.app_version} (academic earthquake research application)",
    )
    return UsgsClient(http, cfg.usgs_base_url)
