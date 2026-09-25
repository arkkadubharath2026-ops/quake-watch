"""Shared Redis client for support concerns (metrics, circuit breaker, job locks).

Keys are namespaced by environment so the test suite never touches development data.
"""

from __future__ import annotations

from functools import lru_cache

import redis

from config.env import Environment, get_settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        decode_responses=True,
    )


def key(*parts: str) -> str:
    prefix = "qw:test" if get_settings().env is Environment.TEST else "qw"
    return ":".join((prefix, *parts))
