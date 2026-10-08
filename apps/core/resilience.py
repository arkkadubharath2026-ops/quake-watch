"""Resilience primitives: jittered exponential backoff and a shared circuit breaker (ESD §13).

The circuit breaker keeps its state in ArangoDB (:mod:`apps.core.arango.breaker_store`) so every
web/worker/beat process sees the same view of an upstream source. States:

* **closed**  — calls allowed; consecutive failures counted.
* **open**    — after ``failure_threshold`` consecutive failures: calls rejected with
  :class:`CircuitOpen` until ``reset_seconds`` elapse (reduces retry pressure; stored data keeps
  being served and freshness is reported as degraded).
* **half-open** — after the reset period exactly one caller (atomic probe claim) may try;
  success closes the circuit, failure re-opens it.

If the state store is unavailable the breaker *fails open* (allows calls) and logs a warning: it is
a protective optimisation, and blocking all ingestion because shared state is down would be worse.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from apps.core.arango import breaker_store
from apps.core.errors import CircuitOpen, DatabaseUnavailable
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

    @property
    def _keep_seconds(self) -> float:
        return float(self.reset_seconds * 4)

    def before_call(self) -> None:
        """Raise :class:`CircuitOpen` if calls must not be attempted right now."""
        try:
            open_until = breaker_store.read(self.name).open_until
            if open_until is None:
                return
            now = self._clock()
            if now < open_until:
                raise CircuitOpen(self.name, open_until - now)
            if not breaker_store.claim_probe(self.name, float(max(30, self.reset_seconds))):
                raise CircuitOpen(self.name, float(self.reset_seconds))
            log.info("circuit_half_open_probe", circuit=self.name)
        except DatabaseUnavailable as exc:
            log.warning("circuit_state_unavailable_fail_open", circuit=self.name, error=str(exc))

    def record_success(self) -> None:
        try:
            if breaker_store.clear(self.name):
                log.info("circuit_closed", circuit=self.name)
        except DatabaseUnavailable as exc:
            log.warning("circuit_state_unavailable", circuit=self.name, error=str(exc))

    def record_failure(self) -> None:
        try:
            failures, opened = breaker_store.record_failure(
                self.name,
                threshold=self.failure_threshold,
                open_until=self._clock() + self.reset_seconds,
                keep=self._keep_seconds,
            )
            if opened:
                log.warning(
                    "circuit_opened",
                    circuit=self.name,
                    consecutive_failures=failures,
                    reset_seconds=self.reset_seconds,
                )
        except DatabaseUnavailable as exc:
            log.warning("circuit_state_unavailable", circuit=self.name, error=str(exc))

    def state(self) -> BreakerState:
        try:
            stored = breaker_store.read(self.name)
        except DatabaseUnavailable:
            return BreakerState(self.name, "unknown", 0, None)
        if stored.open_until is None:
            return BreakerState(self.name, "closed", stored.failures, None)
        status: BreakerStatus = "open" if self._clock() < stored.open_until else "half_open"
        return BreakerState(self.name, status, stored.failures, stored.open_until)

    def reset(self) -> None:
        breaker_store.clear(self.name)
