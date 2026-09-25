"""Source freshness (ADR-004): is the stored data current, and is the upstream reachable?"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from apps.core.clock import from_iso, utc_now
from apps.core.resilience import BreakerState

FreshnessStatus = Literal["fresh", "degraded", "stale", "unknown"]


class RunReader(Protocol):
    def latest_run(
        self, kind: str, *, statuses: list[str] | None = None
    ) -> dict[str, Any] | None: ...


@dataclass(frozen=True, slots=True)
class Freshness:
    status: FreshnessStatus
    source: str
    last_success_at: str | None
    minutes_since_success: float | None
    source_generated_at: str | None
    last_attempt: dict[str, Any] | None
    circuit: dict[str, Any]
    thresholds_minutes: dict[str, int]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify(minutes: float | None, *, degraded: int, stale: int) -> FreshnessStatus:
    if minutes is None:
        return "unknown"
    if minutes <= degraded:
        return "fresh"
    if minutes <= stale:
        return "degraded"
    return "stale"


_MESSAGES: dict[FreshnessStatus, str] = {
    "fresh": "Data is current.",
    "degraded": "Updates are delayed; showing the most recent stored data.",
    "stale": "Upstream updates have not succeeded for a long time; data may be outdated.",
    "unknown": "No successful synchronisation has been recorded yet.",
}


class FreshnessService:
    def __init__(
        self,
        runs: RunReader,
        breaker_state: Callable[[], BreakerState],
        *,
        degraded_minutes: int,
        stale_minutes: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.runs = runs
        self.breaker_state = breaker_state
        self.degraded = degraded_minutes
        self.stale = stale_minutes
        self.clock = clock

    def current(self) -> Freshness:
        success = self.runs.latest_run("feed_sync", statuses=["succeeded", "partial"])
        attempt = self.runs.latest_run("feed_sync")
        minutes = None
        if success and success.get("finished_at"):
            minutes = round(
                (self.clock() - from_iso(success["finished_at"])).total_seconds() / 60, 1
            )
        status = classify(minutes, degraded=self.degraded, stale=self.stale)
        breaker = self.breaker_state()
        message = _MESSAGES[status]
        if breaker.status == "open":
            message += " The USGS source is currently failing; retries are paused briefly."
        return Freshness(
            status=status,
            source="USGS",
            last_success_at=success.get("finished_at") if success else None,
            minutes_since_success=minutes,
            source_generated_at=success.get("source_generated_at") if success else None,
            last_attempt=(
                {
                    "status": attempt.get("status"),
                    "started_at": attempt.get("started_at"),
                    "finished_at": attempt.get("finished_at"),
                    "error": (attempt.get("error") or {}).get("message"),
                }
                if attempt
                else None
            ),
            circuit={
                "status": breaker.status,
                "consecutive_failures": breaker.consecutive_failures,
            },
            thresholds_minutes={"degraded_after": self.degraded, "stale_after": self.stale},
            message=message,
        )
