"""Resilience primitives: jittered exponential backoff and a shared circuit breaker (ESD §13).

The circuit breaker keeps its state in Redis so every web/worker/beat process sees the same view
of an upstream source. States:

* **closed**  — calls allowed; consecutive failures counted.
* **open**    — after ``failure_threshold`` consecutive failures: calls rejected with
  :class:`CircuitOpen` until ``reset_seconds`` elapse (reduces retry pressure; stored data keeps
  being served and freshness is reported as degraded).
* **half-open** — after the reset period exactly one caller (Redis ``SET NX`` probe lock) may try;
  success closes the circuit, failure re-opens it.

If Redis itself is unavailable the breaker *fails open* (allows calls) and logs a warning: it is a
protective optimisation, and blocking all ingestion because the cache is down would be worse.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import redis

from apps.core.errors import CircuitOpen
from apps.core.redis_client import get_redis, key
from config.logging import get_logger

log = get_logger(__name__)

BreakerStatus = Literal["closed", "open", "half_open", "unknown"]


def backoff_delay(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 60.0,
    retry_after: float | None = None,
    rng: Callable[[float, float], float] = random.uniform,
) -> float:
    """Full-jitter exponential backoff for retry ``attempt`` (1-based).

    An upstream ``Retry-After`` is honoured (bounded by ``cap``) instead of the computed delay.
    """
    if retry_after is not None and retry_after >= 0:
        return min(retry_after, cap)
    ceiling = min(cap, base * (2 ** max(0, attempt - 1)))
    return rng(0.0, ceiling)


@dataclass(frozen=True, slots=True)
class BreakerState:
    name: str
    status: BreakerStatus
    consecutive_failures: int
    open_until: float | None


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int,
        reset_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._clock = clock

    def _k(self, suffix: str) -> str:
        return key("circuit", self.name, suffix)

    def before_call(self) -> None:
        """Raise :class:`CircuitOpen` if calls must not be attempted right now."""
        try:
            client = get_redis()
            open_until_raw = client.get(self._k("open_until"))
            if open_until_raw is None:
                return
            open_until = float(str(open_until_raw))
            now = self._clock()
            if now < open_until:
                raise CircuitOpen(self.name, open_until - now)
            acquired = client.set(self._k("probe"), "1", nx=True, ex=max(30, self.reset_seconds))
            if not acquired:
                raise CircuitOpen(self.name, float(self.reset_seconds))
            log.info("circuit_half_open_probe", circuit=self.name)
        except redis.RedisError as exc:
            log.warning("circuit_state_unavailable_fail_open", circuit=self.name, error=str(exc))

    def record_success(self) -> None:
        try:
            client = get_redis()
            was_open = bool(client.exists(self._k("open_until")))
            client.delete(self._k("failures"), self._k("open_until"), self._k("probe"))
            if was_open:
                log.info("circuit_closed", circuit=self.name)
        except redis.RedisError as exc:
            log.warning("circuit_state_unavailable", circuit=self.name, error=str(exc))

    def record_failure(self) -> None:
        try:
            client = get_redis()
            failures = int(str(client.incr(self._k("failures"))))
            client.expire(self._k("failures"), self.reset_seconds * 4)
            was_probe = bool(client.delete(self._k("probe")))
            if failures >= self.failure_threshold or was_probe:
                open_until = self._clock() + self.reset_seconds
                client.set(self._k("open_until"), str(open_until), ex=self.reset_seconds * 4)
                log.warning(
                    "circuit_opened",
                    circuit=self.name,
                    consecutive_failures=failures,
                    reset_seconds=self.reset_seconds,
                )
        except redis.RedisError as exc:
            log.warning("circuit_state_unavailable", circuit=self.name, error=str(exc))

    def state(self) -> BreakerState:
        try:
            client = get_redis()
            failures = int(str(client.get(self._k("failures")) or 0))
            open_until_raw = client.get(self._k("open_until"))
        except redis.RedisError:
            return BreakerState(self.name, "unknown", 0, None)
        if open_until_raw is None:
            return BreakerState(self.name, "closed", failures, None)
        open_until = float(str(open_until_raw))
        status: BreakerStatus = "open" if self._clock() < open_until else "half_open"
        return BreakerState(self.name, status, failures, open_until)

    def reset(self) -> None:
        get_redis().delete(self._k("failures"), self._k("open_until"), self._k("probe"))
