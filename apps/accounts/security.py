"""Login brute-force protection (PRD NFR security: rate limits).

Failed attempts are counted per (username, client IP) and per username in the shared cache.
After ``LOCK_THRESHOLD`` failures within ``WINDOW_SECONDS`` further attempts are refused without
checking the password until the window expires. Successful login clears the counters.
"""

from __future__ import annotations

import hashlib

from django.core.cache import cache

LOCK_THRESHOLD = 10
USERNAME_THRESHOLD = 30  # guards against one account being attacked from many addresses
WINDOW_SECONDS = 15 * 60


def _key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(p.lower() for p in parts).encode()).hexdigest()[:32]
    return f"login-fail:{digest}"


def _keys(username: str, ip: str | None) -> tuple[str, str]:
    return _key(username, ip or "-"), _key(username)


def is_locked(username: str, ip: str | None) -> bool:
    pair, per_user = _keys(username, ip)
    return (
        int(cache.get(pair, 0)) >= LOCK_THRESHOLD
        or int(cache.get(per_user, 0)) >= USERNAME_THRESHOLD
    )


def register_failure(username: str, ip: str | None) -> int:
    count = 0
    for key in _keys(username, ip):
        cache.add(key, 0, WINDOW_SECONDS)
        try:
            count = max(count, int(cache.incr(key)))
        except ValueError:  # key expired between add and incr
            cache.set(key, 1, WINDOW_SECONDS)
            count = max(count, 1)
    return count


def reset(username: str, ip: str | None) -> None:
    cache.delete_many(list(_keys(username, ip)))
