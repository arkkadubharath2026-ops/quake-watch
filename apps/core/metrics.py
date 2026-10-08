"""Lightweight operational metrics stored in ArangoDB.

Counters and latency series (the most recent ``MAX_SAMPLES`` observations, from which the
Operations dashboard computes p50/p95/p99) live in :mod:`apps.core.arango.metrics_store`.

``incr``/``observe`` sit on hot paths (every AQL query, every API request), so they only append to
a per-process buffer; the buffer is flushed in one atomic statement per kind when
``FLUSH_INTERVAL_SECONDS`` has passed or ``FLUSH_MAX_PENDING`` observations are pending, when this
process reads metrics, and at interpreter exit. Increments from concurrent processes therefore
add up exactly; another process sees them after at most one flush interval.

Metrics are best-effort: a store outage is logged (rate-limited) but never breaks the request or
job being measured. While the store is down, counter deltas are kept (they are tiny) and the
newest ``BUFFER_CAP`` samples per series survive; flush attempts back off for one interval.
"""

from __future__ import annotations

import atexit
import math
import os
import threading
import time
from dataclasses import dataclass
from types import ModuleType

from apps.core.errors import DatabaseUnavailable
from config.logging import get_logger

MAX_SAMPLES = 1000
FLUSH_INTERVAL_SECONDS = 5.0
FLUSH_MAX_PENDING = 500
BUFFER_CAP = 5 * MAX_SAMPLES
_WARN_INTERVAL_SECONDS = 60.0

log = get_logger(__name__)
_last_warning = 0.0


class _Buffer:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.counters: dict[str, int] = {}
        self.series: dict[str, list[float]] = {}
        self.pending = 0
        self.next_flush = time.monotonic() + FLUSH_INTERVAL_SECONDS

    def take(self) -> tuple[dict[str, int], dict[str, list[float]]]:
        """Detach the buffered data (call with ``lock`` held)."""
        counters, series = self.counters, self.series
        self.counters, self.series, self.pending = {}, {}, 0
        return counters, series

    def restore(self, counters: dict[str, int], series: dict[str, list[float]]) -> None:
        """Put back data whose flush failed, ahead of anything buffered meanwhile."""
        for name, delta in counters.items():
            self.counters[name] = self.counters.get(name, 0) + delta
        for name, values in series.items():
            self.series[name] = (values + self.series.get(name, []))[-BUFFER_CAP:]
        self.pending = sum(len(v) for v in self.series.values())


_buffer = _Buffer()


def _store() -> ModuleType:
    # Imported lazily: the store runs AQL through apps.core.arango.query, which imports this module.
    from apps.core.arango import metrics_store

    return metrics_store


def _reset_after_fork() -> None:
    """A forked child must not re-flush data its parent will flush."""
    global _buffer
    _buffer = _Buffer()


os.register_at_fork(after_in_child=_reset_after_fork)


def _warn(exc: Exception) -> None:
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= _WARN_INTERVAL_SECONDS:
        _last_warning = now
        log.warning("metrics_backend_unavailable", error=str(exc))


def flush() -> bool:
    """Write buffered metrics; returns False (data kept) when the store is unavailable."""
    buf = _buffer
    with buf.lock:
        counters, series = buf.take()
        buf.next_flush = time.monotonic() + FLUSH_INTERVAL_SECONDS
    if not counters and not series:
        return True
    try:
        _store().flush(counters, series, MAX_SAMPLES)
    except DatabaseUnavailable as exc:
        _warn(exc)
        with buf.lock:
            buf.restore(counters, series)
        return False
    return True


def _maybe_flush(buf: _Buffer) -> None:
    if buf.pending >= FLUSH_MAX_PENDING or time.monotonic() >= buf.next_flush:
        flush()


def incr(name: str, amount: int = 1) -> None:
    buf = _buffer
    with buf.lock:
        buf.counters[name] = buf.counters.get(name, 0) + amount
    _maybe_flush(buf)


def observe(name: str, value: float) -> None:
    buf = _buffer
    with buf.lock:
        values = buf.series.setdefault(name, [])
        values.append(float(value))
        if len(values) > BUFFER_CAP:
            del values[: len(values) - BUFFER_CAP]
        else:
            buf.pending += 1
    _maybe_flush(buf)


atexit.register(flush)


@dataclass(frozen=True, slots=True)
class SeriesSummary:
    name: str
    count: int
    p50: float | None
    p95: float | None
    p99: float | None
    max: float | None


def percentile(sorted_values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile on an ascending list."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(pct / 100.0 * len(sorted_values)))
    return sorted_values[rank - 1]


def summarize(name: str) -> SeriesSummary:
    flush()
    try:
        raw = _store().samples(name)
    except DatabaseUnavailable as exc:
        _warn(exc)
        raw = []  # degraded: report an empty series rather than failing the caller
    values = sorted(raw)
    return SeriesSummary(
        name=name,
        count=len(values),
        p50=percentile(values, 50),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        max=values[-1] if values else None,
    )


def counters() -> dict[str, int]:
    flush()
    try:
        stored: dict[str, int] = _store().counters()
        return stored
    except DatabaseUnavailable as exc:
        _warn(exc)
        return {}


def series_names() -> list[str]:
    flush()
    try:
        names: list[str] = _store().series_names()
        return names
    except DatabaseUnavailable as exc:
        _warn(exc)
        return []


def reset() -> None:
    """Delete all metrics, buffered and stored (tests and the admin reset action)."""
    with _buffer.lock:
        _buffer.take()
    _store().clear()


def ping() -> bool:
    try:
        _store().ping()
    except DatabaseUnavailable:
        return False
    return True
