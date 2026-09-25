"""Distributed job locks on Redis (prevents overlapping scheduled runs of the same job).

``SET key token NX EX ttl`` acquires; release deletes only if the token still matches (Lua), so a
job that outlived its TTL can never delete a lock re-acquired by another worker.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import redis

from apps.core.redis_client import get_redis, key
from config.logging import get_logger

log = get_logger(__name__)

_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


@contextmanager
def job_lock(name: str, *, ttl_seconds: int) -> Iterator[bool]:
    """Yield True if the lock was acquired; the body should skip work when False."""
    lock_key = key("lock", name)
    token = uuid.uuid4().hex
    client = get_redis()
    try:
        acquired = bool(client.set(lock_key, token, nx=True, ex=ttl_seconds))
    except redis.RedisError as exc:
        # Without Redis the broker is down too; running unlocked risks only duplicate (idempotent)
        # work, so proceed rather than silently skipping ingestion.
        log.warning("job_lock_unavailable", lock=name, error=str(exc))
        yield True
        return
    try:
        yield acquired
    finally:
        if acquired:
            try:
                client.eval(_RELEASE, 1, lock_key, token)
            except redis.RedisError as exc:
                log.warning("job_lock_release_failed", lock=name, error=str(exc))
