"""Lightweight operational metrics stored in Redis.

Counters are Redis hash fields; latency series keep the most recent ``MAX_SAMPLES``
observations in a capped list, from which the Operations dashboard computes p50/p95/p99.
Metrics are best-effort: a Redis outage is logged (rate-limited) but never breaks the
request or job that is being measured.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import cast

import redis

from apps.core.redis_client import get_redis, key
from config.logging import get_logger

MAX_SAMPLES = 1000
_WARN_INTERVAL_SECONDS = 60.0

log = get_logger(__name__)
_last_warning = 0.0


def _counters_key() -> str:
    return key("metrics", "counters")


def _series_key(name: str) -> str:
    return key("metrics", "samples", name)


def _index_key() -> str:
    return key("metrics", "series")


def _warn(exc: Exception) -> None:
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= _WARN_INTERVAL_SECONDS:
        _last_warning = now
        log.warning("metrics_backend_unavailable", error=str(exc))


def incr(name: str, amount: int = 1) -> None:
    try:
        get_redis().hincrby(_counters_key(), name, amount)
    except redis.RedisError as exc:
        _warn(exc)


def observe(name: str, value: float) -> None:
    series = _series_key(name)
    try:
        pipe = get_redis().pipeline(transaction=False)
        pipe.lpush(series, value)
        pipe.ltrim(series, 0, MAX_SAMPLES - 1)
        pipe.sadd(_index_key(), name)
        pipe.execute()
    except redis.RedisError as exc:
        _warn(exc)


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
    try:
        raw = cast(list[str], get_redis().lrange(_series_key(name), 0, MAX_SAMPLES - 1))
    except redis.RedisError as exc:
        _warn(exc)
        raw = []  # degraded: report an empty series rather than failing the caller
    values = sorted(float(v) for v in raw)
    return SeriesSummary(
        name=name,
        count=len(values),
        p50=percentile(values, 50),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        max=values[-1] if values else None,
    )


def counters() -> dict[str, int]:
    try:
        raw = cast(dict[str, str], get_redis().hgetall(_counters_key()))
    except redis.RedisError as exc:
        _warn(exc)
        return {}
    return {k: int(v) for k, v in raw.items()}


def series_names() -> list[str]:
    try:
        return sorted(cast(set[str], get_redis().smembers(_index_key())))
    except redis.RedisError as exc:
        _warn(exc)
        return []


def reset() -> None:
    """Delete all metrics in the current namespace (tests and the admin reset action)."""
    keys = [_series_key(n) for n in series_names()] + [_counters_key(), _index_key()]
    get_redis().delete(*keys)


def ping() -> bool:
    try:
        return bool(get_redis().ping())
    except redis.RedisError:
        return False
