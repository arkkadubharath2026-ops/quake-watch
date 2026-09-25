"""Analytics services: parameter validation, windowing, short-lived caching (dashboard < 800 ms)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Protocol

from django.core.cache import cache

from apps.analytics import repository as q
from apps.core.arango.catalog import NamedQuery
from apps.core.clock import to_iso, utc_now
from apps.core.errors import ValidationFailed

CACHE_SECONDS = 60
MAX_WINDOW_DAYS = 3660


class AnalyticsReader(Protocol):
    def run(self, query: NamedQuery, binds: dict[str, Any]) -> list[Any]: ...
    def first(self, query: NamedQuery, binds: dict[str, Any]) -> Any: ...


def parse_days(raw: str | None, *, default: int = 30) -> int:
    if raw in (None, ""):
        return default
    try:
        days = int(str(raw))
    except ValueError as exc:
        raise ValidationFailed(
            "Invalid window.", details={"fields": {"days": "must be an integer"}}
        ) from exc
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise ValidationFailed(
            "Invalid window.", details={"fields": {"days": f"must be 1..{MAX_WINDOW_DAYS}"}}
        )
    return days


TIME_TO_REVIEWED_DEFINITION = (
    "Review time = USGS update timestamp of the first version with status 'reviewed', so gaps in "
    "QuakeWatch polling do not inflate it. Only events QuakeWatch first saw as 'automatic' count."
)


class AnalyticsService:
    def __init__(self, reader: AnalyticsReader) -> None:
        self.reader = reader

    def _cached(self, key: str, compute: Callable[[], Any]) -> Any:
        full_key = f"analytics:{key}"
        value = cache.get(full_key)
        if value is None:
            value = compute()
            cache.set(full_key, value, CACHE_SECONDS)
        return value

    @staticmethod
    def _since(days: int) -> str:
        return to_iso(utc_now() - timedelta(days=days))

    def summary(self) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            now = utc_now()
            data = self.reader.first(
                q.SUMMARY,
                {"day": to_iso(now - timedelta(days=1)), "week": to_iso(now - timedelta(days=7))},
            )
            return {**(data or {}), "generated_at": to_iso(now)}

        return dict(self._cached("summary", compute))

    def timeseries(self, days: int) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            since = self._since(days)
            return {
                "days": days,
                "daily_by_band": self.reader.run(q.TIMESERIES, {"since": since}),
                "by_month": self.reader.run(q.BY_MONTH, {"since": since}),
                "significant_by_week": self.reader.run(q.SIGNIFICANT_BY_WEEK, {"since": since}),
            }

        return dict(self._cached(f"timeseries:{days}", compute))

    def distributions(self, days: int) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            since = self._since(days)
            return {
                "days": days,
                "magnitude": self.reader.run(q.MAGNITUDE_HISTOGRAM, {"since": since}),
                "depth": self.reader.run(q.DEPTH_HISTOGRAM, {"since": since}),
                "magnitude_depth": self.reader.run(q.SCATTER, {"since": since, "limit": 2000}),
                "status": self.reader.run(q.STATUS_COUNTS, {"since": since}),
            }

        return dict(self._cached(f"distributions:{days}", compute))

    def breakdowns(self, days: int) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            since = self._since(days)
            return {
                "days": days,
                "regions": self.reader.run(q.BY_REGION, {"since": since, "limit": 20}),
                "networks": self.reader.run(q.NETWORK_STATS, {"since": since}),
            }

        return dict(self._cached(f"breakdowns:{days}", compute))

    def revisions(self, days: int, *, magnitude_threshold: float = 0.3) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            since = self._since(days)
            return {
                "days": days,
                "field_frequency": self.reader.run(q.REVISION_FIELDS, {"since": since}),
                "revision_count_distribution": self.reader.run(
                    q.REVISION_COUNT_DISTRIBUTION, {"since": since}
                ),
                "most_revised": self.reader.run(q.MOST_REVISED, {"since": since, "limit": 15}),
                "magnitude_changes": self.reader.run(
                    q.MAGNITUDE_CHANGES, {"threshold": magnitude_threshold, "limit": 20}
                ),
                "time_to_reviewed": {
                    **(self.reader.first(q.TIME_TO_REVIEWED, {"since": since}) or {"count": 0}),
                    "definition": TIME_TO_REVIEWED_DEFINITION,
                },
            }

        return dict(self._cached(f"revisions:{days}:{magnitude_threshold}", compute))

    def latency(self, days: int) -> dict[str, Any]:
        def compute() -> dict[str, Any]:
            data = self.reader.first(q.INGESTION_LATENCY, {"since": self._since(days)})
            return {
                "days": days,
                "first_observation_latency": data,
                "definition": (
                    "QuakeWatch first observation time minus USGS origin time, for events that "
                    "occurred after live monitoring began and were first seen through the live "
                    "feed (derived). Includes USGS publication delay, the polling interval and "
                    "any QuakeWatch downtime."
                ),
            }

        return dict(self._cached(f"latency:{days}", compute))
