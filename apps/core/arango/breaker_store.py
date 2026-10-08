"""ArangoDB state for the shared circuit breaker (replaces the Redis keys of apps.core.resilience).

One document per breaker in ``circuit_breakers``::

    {_key: sha1(name), name,
     failures, failures_exp,   # consecutive failures; forgotten ``keep`` seconds after the last one
     open_until, open_exp,     # worker-clock reopen time; the record itself kept ``keep`` seconds
     probe_exp}                # half-open probe claim, held until success/failure or expiry

``*_exp`` fields are ArangoDB server time (``DATE_NOW()``), exactly like the Redis key TTLs they
replace; ``open_until`` comes from the caller's clock, as before. Every operation is a single AQL
statement: the read and the write commit together, and a concurrent writer to the same breaker
gets a write-write conflict that :func:`run_atomic` resolves by re-running against the committed
state — so exactly one caller wins the half-open probe and no failure is lost. Driver errors are
translated to :class:`DatabaseUnavailable` (the breaker fails open on it).
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

_READ = """
LET now = DATE_NOW() / 1000
LET d = DOCUMENT(@@b, @k)
RETURN {
  failures: d != null AND d.failures_exp > now ? d.failures : 0,
  open_until: d != null AND d.open_exp > now ? d.open_until : null
}
"""
_CLAIM_PROBE = """
LET now = DATE_NOW() / 1000
LET d = DOCUMENT(@@b, @k)
LET free = d == null OR d.probe_exp == null OR d.probe_exp <= now
UPSERT { _key: @k }
  INSERT { _key: @k, name: @name, probe_exp: now + @probe_ttl }
  UPDATE { probe_exp: free ? now + @probe_ttl : d.probe_exp }
  IN @@b
RETURN free
"""
_RECORD_FAILURE = """
LET now = DATE_NOW() / 1000
LET d = DOCUMENT(@@b, @k)
LET failures = (d != null AND d.failures_exp > now ? d.failures : 0) + 1
LET was_probe = d != null AND d.probe_exp != null AND d.probe_exp > now
LET opened = failures >= @threshold OR was_probe
LET still_open = d != null AND d.open_exp > now
LET doc = {
  _key: @k, name: @name, failures: failures, failures_exp: now + @keep, probe_exp: null,
  open_until: opened ? @open_until : (still_open ? d.open_until : null),
  open_exp: opened ? now + @keep : (still_open ? d.open_exp : null)
}
UPSERT { _key: @k } INSERT doc REPLACE doc IN @@b
RETURN { failures: failures, opened: opened }
"""
_CLEAR = """
LET now = DATE_NOW() / 1000
FOR d IN @@b FILTER d._key == @k
  REMOVE d IN @@b
  RETURN d.open_exp != null AND d.open_exp > now
"""


@dataclass(frozen=True, slots=True)
class StoredState:
    failures: int
    open_until: float | None


def _key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8"), usedforsecurity=False).hexdigest()


def _run(name: str, aql: str, binds: dict[str, Any]) -> list[Any]:
    try:
        return run_atomic(get_db(), name, aql, {"@b": s.CIRCUIT_BREAKERS, **binds}, attempts=30)
    except (ArangoError, OSError) as exc:
        raise DatabaseUnavailable(f"circuit breaker store: {exc}") from exc


def read(name: str) -> StoredState:
    row = _run("breaker_read", _READ, {"k": _key(name)})[0]
    open_until = row["open_until"]
    return StoredState(int(row["failures"]), None if open_until is None else float(open_until))


def claim_probe(name: str, probe_ttl: float) -> bool:
    """Atomically take the half-open probe; False if another caller holds it."""
    rows = _run(
        "breaker_claim_probe", _CLAIM_PROBE, {"k": _key(name), "name": name, "probe_ttl": probe_ttl}
    )
    return bool(rows[0])


def record_failure(
    name: str, *, threshold: int, open_until: float, keep: float
) -> tuple[int, bool]:
    """Count a failure; open (until ``open_until``) at ``threshold`` or after a failed probe."""
    binds = {
        "k": _key(name), "name": name, "threshold": threshold, "open_until": open_until,
        "keep": keep,
    }  # fmt: skip
    row = _run("breaker_record_failure", _RECORD_FAILURE, binds)[0]
    return int(row["failures"]), bool(row["opened"])


def clear(name: str) -> bool:
    """Forget all state; returns whether the circuit was open."""
    return any(_run("breaker_clear", _CLEAR, {"k": _key(name)}))
