"""Atomic sliding-window rate limits (``rate_limits``), used by :mod:`apps.core.throttling`.

The stock DRF throttles keep each window in the cache with a separate ``get`` and ``set``: two
round trips per throttle (four per anonymous request) and a race in which concurrent requests all
pass a nearly full window. Here every check of a request is decided and recorded in ONE AQL
statement: per check, the request is recorded only if the window still has room, exactly like the
stock ``throttle_success``. Concurrent requests on the same window conflict and are re-run, so a
window never admits more than its limit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from arango.exceptions import ArangoError

from apps.core.arango import schema as s
from apps.core.arango.atomic import run_atomic
from apps.core.arango.client import get_db
from apps.core.errors import DatabaseUnavailable

# A window under attack is one hot document: allow many conflict re-runs.
ATTEMPTS = 30

# `limit` is an AQL keyword: the bound attribute is called `cap`.
_HIT = """
LET windows = (FOR c IN @checks RETURN DOCUMENT(@@rl, c.key))  // read all before any write
FOR i IN 0..LENGTH(@checks) - 1
  LET c = @checks[i]
  LET d = windows[i]
  LET recent = d == null ? [] : (FOR h IN d.h FILTER h > @now - c.duration RETURN h)
  LET ok = LENGTH(recent) < c.cap
  LET written = (
    FOR x IN (ok ? [1] : [])
      UPSERT { _key: c.key }
        INSERT { _key: c.key, h: APPEND(recent, [@now]), expires_at: @now + c.duration }
        REPLACE { _key: c.key, h: APPEND(recent, [@now]), expires_at: @now + c.duration }
        IN @@rl
      RETURN 1
  )
  RETURN { ok: ok, count: LENGTH(recent), oldest: LENGTH(recent) > 0 ? MIN(recent) : null }
"""


@dataclass(frozen=True, slots=True)
class Check:
    scope: str
    ident: str
    limit: int
    duration: float

    @property
    def key(self) -> str:
        raw = f"{self.scope}:{self.ident}".encode()
        return hashlib.sha1(raw, usedforsecurity=False).hexdigest()


@dataclass(frozen=True, slots=True)
class Outcome:
    check: Check
    allowed: bool
    count: int  # requests already in the window before this one
    oldest: float | None

    def wait(self, now: float) -> float | None:
        """The stock DRF wait(): seconds until a request may pass, spread over what remains."""
        if self.allowed:
            return None
        if self.oldest is None:
            remaining = self.check.duration
        else:
            remaining = self.check.duration - (now - self.oldest)
        available = self.check.limit - self.count + 1
        return remaining / float(available) if available > 0 else None


def hit(checks: list[Check], now: float) -> list[Outcome]:
    if not checks:
        return []
    binds: dict[str, Any] = {
        "@rl": s.RATE_LIMITS,
        "now": now,
        "checks": [{"key": c.key, "cap": c.limit, "duration": c.duration} for c in checks],
    }
    try:
        rows = run_atomic(get_db(), "rate_limit_hit", _HIT, binds, attempts=ATTEMPTS)
    except ArangoError as exc:
        raise DatabaseUnavailable(f"rate_limit_hit: {exc}") from exc
    return [
        Outcome(c, bool(r["ok"]), int(r["count"]), r["oldest"])
        for c, r in zip(checks, rows, strict=True)
    ]
