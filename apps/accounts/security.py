"""Login brute-force protection (PRD NFR security: rate limits).

Attempts are *counted before* the password is checked (atomic cache ``incr``), so concurrent
requests cannot slip past a limit while hashing is slow. A successful login clears the per-pair and
per-address counters. Three limits apply within a sliding-free 15-minute window:

* ``PAIR_LIMIT`` attempts per (username, client address) — stops single-source guessing;
* ``ADDRESS_LIMIT`` attempts per client address across all usernames — stops password spraying;
* ``USERNAME_LIMIT`` attempts per username across all addresses — stops distributed guessing.
  To prevent attackers from locking a legitimate user out, the username limit is *not* applied
  to addresses from which that user logged in successfully in the last 30 days.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.core.cache import cache

PAIR_LIMIT = 10
ADDRESS_LIMIT = 50
USERNAME_LIMIT = 30
WINDOW_SECONDS = 15 * 60
KNOWN_ADDRESS_SECONDS = 30 * 24 * 3600


def _key(kind: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(p.lower() for p in parts).encode()).hexdigest()[:32]
    return f"login:{kind}:{digest}"


def _incr(key: str) -> int:
    cache.add(key, 0, WINDOW_SECONDS)  # TTL starts at the first attempt; INCR keeps it
    try:
        return int(cache.incr(key))
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)
        return 1


@dataclass(frozen=True, slots=True)
class AttemptDecision:
    allowed: bool
    reason: str | None = None


def _known(username: str, ip: str | None) -> bool:
    return ip is not None and cache.get(_key("known", username, ip)) is not None


def register_attempt(username: str, ip: str | None) -> AttemptDecision:
    """Count this attempt and decide whether it may proceed to password verification."""
    source = ip or "-"
    if _incr(_key("pair", username, source)) > PAIR_LIMIT:
        return AttemptDecision(False, "too many attempts for this account from this address")
    if ip is not None and _incr(_key("addr", ip)) > ADDRESS_LIMIT:
        return AttemptDecision(False, "too many attempts from this address")
    per_user = _incr(_key("user", username))
    if per_user > USERNAME_LIMIT and not _known(username, ip):
        return AttemptDecision(False, "too many attempts for this account")
    return AttemptDecision(True)


def is_locked(username: str, ip: str | None) -> bool:
    """Read-only view (for display/audit); enforcement happens in :func:`register_attempt`."""
    source = ip or "-"
    if int(cache.get(_key("pair", username, source), 0)) >= PAIR_LIMIT:
        return True
    if ip is not None and int(cache.get(_key("addr", ip), 0)) >= ADDRESS_LIMIT:
        return True
    return int(cache.get(_key("user", username), 0)) >= USERNAME_LIMIT and not _known(username, ip)


def record_success(username: str, ip: str | None) -> None:
    source = ip or "-"
    cache.delete_many([_key("pair", username, source)] + ([_key("addr", ip)] if ip else []))
    if ip is not None:
        cache.set(_key("known", username, ip), 1, KNOWN_ADDRESS_SECONDS)
