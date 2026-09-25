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
from functools import lru_cache
from typing import cast

import redis

from config.env import get_settings
from config.logging import get_logger

MAX_SAMPLES = 1000
_COUNTERS_KEY = "qw:metrics:counters"
_SAMPLES_PREFIX = "qw:metrics:samples:"
_SAMPLES_INDEX = "qw:metrics:series"
_WARN_INTERVAL_SECONDS = 60.0

log = get_logger(__name__)
_last_warning = 0.0


@lru_cache(maxsize=1)
def _client() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        decode_responses=True,
    )


def _namespace() -> str:
    return "test:" if get_settings().env.value == "test" else ""


def _warn(exc: Exception) -> None:
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= _WARN_INTERVAL_SECONDS:
        _last_warning = now
        log.warning("metrics_backend_unavailable", error=str(exc))


def incr(name: str, amount: int = 1) -> None:
    try:
        _client().hincrby(_namespace() + _COUNTERS_KEY, name, amount)
    except redis.RedisError as exc:
        _warn(exc)


def observe(name: str, value: float) -> None:
    key = _namespace() + _SAMPLES_PREFIX + name
    try:
        pipe = _client().pipeline(transaction=False)
        pipe.lpush(key, value)
        pipe.ltrim(key, 0, MAX_SAMPLES - 1)
        pipe.sadd(_namespace() + _SAMPLES_INDEX, name)
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
        raw = cast(
            list[str], _client().lrange(_namespace() + _SAMPLES_PREFIX + name, 0, MAX_SAMPLES - 1)
        )
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
        raw = cast(dict[str, str], _client().hgetall(_namespace() + _COUNTERS_KEY))
    except redis.RedisError as exc:
        _warn(exc)
        return {}
    return {k: int(v) for k, v in raw.items()}


def series_names() -> list[str]:
    try:
        return sorted(cast(set[str], _client().smembers(_namespace() + _SAMPLES_INDEX)))
    except redis.RedisError as exc:
        _warn(exc)
        return []


def reset() -> None:
    """Delete all metrics in the current namespace (used by tests and the admin reset action)."""
    client = _client()
    names = series_names()
    keys = [_namespace() + _SAMPLES_PREFIX + n for n in names]
    keys += [_namespace() + _COUNTERS_KEY, _namespace() + _SAMPLES_INDEX]
    client.delete(*keys)


def ping() -> bool:
    try:
        return bool(_client().ping())
    except redis.RedisError:
        return False
