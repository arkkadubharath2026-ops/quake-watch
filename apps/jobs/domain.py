r"""Durable job queue: statuses, control-flow exceptions and pure policy (no I/O).

Lifecycle of a document in ``jobs``::

    queued --claim--> running --success--> succeeded
       ^                 |  \--Retry, attempts left--> queued (run_at = now + countdown)
       |                 |  \--Retry, none left------> dead     (dead letter)
       |                 |  \--other exception-------> failed   (permanent; not retried)
       |                 \--worker lost (lease expired)--> queued, or dead past the crash allowance
       \--graceful shutdown releases a running job without consuming an attempt
    queued --past expires_at--> expired   (e.g. a stale schedule tick: never piles up)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
DEAD = "dead"
EXPIRED = "expired"
TERMINAL = frozenset({SUCCEEDED, FAILED, DEAD, EXPIRED})
STATUSES = (QUEUED, RUNNING, SUCCEEDED, FAILED, DEAD, EXPIRED)

# A crashed job is retried even when its task declares no retries (Celery's
# reject_on_worker_lost re-delivered it too), but never endlessly.
MIN_CRASH_ATTEMPTS = 3


class Retry(Exception):  # control flow, mirrors Celery's Retry
    """Raised by a task to be run again after ``countdown`` seconds (if attempts remain)."""

    def __init__(self, countdown: float, exc: BaseException | None = None) -> None:
        super().__init__(f"retry in {countdown:.1f}s: {exc!r}" if exc else f"retry in {countdown}s")
        self.countdown = max(0.0, float(countdown))
        self.exc = exc


class SoftTimeLimitExceeded(Exception):  # Celery-compatible name
    """Raised inside a task when its soft time limit passes (it may clean up and exit)."""


def crash_allowance(max_attempts: int) -> int:
    """How many claims a job may consume through worker loss before it is dead-lettered."""
    return max(max_attempts, MIN_CRASH_ATTEMPTS)


def schedule_tick(now: float, interval: float) -> int:
    """Index of the interval containing ``now``; one job per (entry, tick) is enqueued."""
    return math.floor(now / interval)


_RATE = re.compile(r"^\s*(\d+)\s*/\s*([smh])\s*$")
_UNIT_SECONDS = {"s": 1.0, "m": 60.0, "h": 3600.0}


@dataclass(frozen=True, slots=True)
class RateLimit:
    """At most ``count`` task starts per ``per_seconds`` per worker (Celery's rate_limit)."""

    count: int
    per_seconds: float

    @classmethod
    def parse(cls, spec: str) -> RateLimit:
        match = _RATE.match(spec)
        if not match or int(match.group(1)) < 1:
            raise ValueError(f"invalid rate limit {spec!r}; expected e.g. '30/m'")
        return cls(int(match.group(1)), _UNIT_SECONDS[match.group(2)])


class TokenBucket:
    """Classic token bucket on a monotonic clock; starts full."""

    def __init__(self, limit: RateLimit) -> None:
        self.capacity = float(limit.count)
        self.refill_per_second = limit.count / limit.per_seconds
        self.tokens = self.capacity
        self.updated: float | None = None

    def _refill(self, now: float) -> None:
        if self.updated is not None:
            elapsed = max(0.0, now - self.updated)
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated = now

    def available(self, now: float) -> bool:
        self._refill(now)
        return self.tokens >= 1.0

    def take(self, now: float) -> bool:
        self._refill(now)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False
