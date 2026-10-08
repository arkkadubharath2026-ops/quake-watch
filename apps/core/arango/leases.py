"""Job leases in ArangoDB: at most one running instance per job name (replaces the Redis lock).

One document per lock name in ``job_leases`` (``_key`` = name). Every operation is a **single
AQL statement**, which ArangoDB executes as one atomic transaction on that document: of two
workers that read the same lease state and both try to write it, exactly one commits and the
other gets a write-write conflict (1200) or duplicate key (1210); the statement is then re-run
against the committed state, so contention resolves to "not yours", never to two owners.

Single statements were chosen over an explicit stream transaction with an exclusive collection
lock (the first implementation): a ``begin_transaction`` whose reply was lost to a network
partition left an exclusive transaction open until the server's idle timeout, blocking *every*
job's lease (reproduced in the qwb harness). A single statement completes server-side in
milliseconds even if the client disappears, and only ever touches one lease.

Validity is decided **only by the ArangoDB server clock** (``DATE_NOW()``, decision P4), never by
a worker's clock, so clock skew between workers cannot let two of them hold the same lease.

* ``acquire`` takes a free or expired lease and increments ``fencing``. It is idempotent for the
  same ``token``: retrying after an ambiguous failure returns the caller's own lease unchanged
  and can neither steal another worker's lease nor create a second record.
* ``renew`` / ``release`` act only while the caller's ``token`` still owns the lease, so a worker
  whose lease expired and was taken over can neither extend nor delete the successor's lease.
* A TTL index on ``expires_at`` (epoch seconds) garbage-collects abandoned leases; correctness
  never depends on that background sweeper.

A lease bounds *when* a job may start; it cannot stop a worker that keeps running after its lease
expired. Work done under a lease must therefore stay idempotent (the ingestion pipeline is), or
compare ``fencing`` before writing.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any

from arango.database import StandardDatabase
from arango.exceptions import AQLQueryExecuteError, ArangoServerError, ServerConnectionError

from apps.core.arango import schema as s
from apps.core.arango.catalog import NamedQuery, register
from apps.core.arango.client import sync_optional
from apps.core.arango.query import ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT, run_query
from apps.core.errors import DatabaseUnavailable

# Arango document keys: at most 254 bytes of these characters.
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-:.@()+,=;$!*'%]{1,254}$")
MAX_TTL_SECONDS = 24 * 3600

# Server errors worth retrying: lock timeout (18), write-write conflict or duplicate key (contention
# that outlasted CONFLICT_ATTEMPTS), shutdown / overload.
_TRANSIENT_ERROR_CODES = frozenset({18, ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT, 30, 503})
_TRANSIENT_HTTP_CODES = frozenset({408, 429, 500, 502, 503, 504})

_LEASES = {"@leases": s.JOB_LEASES}
_CONTENTION_CODES = frozenset({ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT})
CONFLICT_ATTEMPTS = 5  # re-evaluations after contention before giving up as transient

ACQUIRE = register(
    NamedQuery(
        name="leases_acquire",
        category="operations",
        question="Job lease: take a free or expired lease, or return the caller's own lease.",
        aql="""
    LET now = DATE_NOW() / 1000
    LET cur = DOCUMENT(@@leases, @key)
    LET mine = cur != null AND cur.token == @token
    FILTER cur == null OR mine OR cur.expires_at <= now
    UPSERT { _key: @key }
      INSERT { _key: @key, token: @token, owner: @owner, acquired_at: now, renewed_at: now,
               expires_at: now + @ttl, fencing: 1 }
      UPDATE (mine ? {} : { token: @token, owner: @owner, acquired_at: now, renewed_at: now,
                            expires_at: now + @ttl, fencing: OLD.fencing + 1 })
      IN @@leases
    RETURN { token: NEW.token, fencing: NEW.fencing, expires_at: NEW.expires_at,
             reclaimed_from: (cur != null AND NOT mine) ? cur.owner : null,
             expired_for_s: (cur != null AND NOT mine) ? now - cur.expires_at : null }
    """,
        sample_binds=lambda: {
            **_LEASES,
            "key": "catalog:sample",
            "token": "catalog-sample-token",
            "owner": "catalog",
            "ttl": 60,
        },
        features=("single-statement atomic", "upsert", "server time"),
        read_only=False,
    )
)

RENEW = register(
    NamedQuery(
        name="leases_renew",
        category="operations",
        question="Job lease: extend a lease only while the caller's token still owns it.",
        aql="""
    LET now = DATE_NOW() / 1000
    FOR l IN @@leases
      FILTER l._key == @key AND l.token == @token AND l.expires_at > now
      UPDATE l WITH { renewed_at: now, expires_at: now + @ttl } IN @@leases
      RETURN { token: NEW.token, fencing: NEW.fencing, expires_at: NEW.expires_at }
    """,
        sample_binds=lambda: {
            **_LEASES,
            "key": "catalog:sample",
            "token": "catalog-sample-token",
            "ttl": 60,
        },
        expected_indexes=("primary",),
        features=("single-statement atomic", "server time"),
        read_only=False,
    )
)

RELEASE = register(
    NamedQuery(
        name="leases_release",
        category="operations",
        question="Job lease: delete a lease only if the caller's token still owns it.",
        aql="""
    FOR l IN @@leases
      FILTER l._key == @key AND l.token == @token
      REMOVE l IN @@leases
      RETURN 1
    """,
        sample_binds=lambda: {**_LEASES, "key": "catalog:sample", "token": "catalog-sample-token"},
        expected_indexes=("primary",),
        features=("single-statement atomic",),
        read_only=False,
    )
)


DESCRIBE = register(
    NamedQuery(
        name="leases_describe",
        category="operations",
        question="Job lease: current holder and remaining validity (server time), for messages.",
        aql="""
    LET now = DATE_NOW() / 1000
    LET l = DOCUMENT(@@leases, @key)
    FILTER l != null
    RETURN { owner: l.owner, fencing: l.fencing, expires_in_s: l.expires_at - now }
    """,
        sample_binds=lambda: {**_LEASES, "key": "catalog:sample"},
        features=("server time", "diagnostics"),
    )
)


class LeaseStoreError(Exception):
    """A non-transient lease-store failure (for example ``job_leases`` not migrated yet)."""


@dataclass(frozen=True, slots=True)
class Lease:
    name: str
    token: str
    fencing: int
    expires_at: float  # ArangoDB server time, epoch seconds
    # Set when this acquisition took over an expired lease: the previous owner and how long
    # (server seconds) it had been expired. Diagnostics only (crashed or overrunning worker).
    reclaimed_from: str | None = None
    expired_for_s: float | None = None


def validate_lease_request(name: str, ttl_seconds: int) -> None:
    if not _KEY_PATTERN.match(name):
        raise ValueError(f"invalid lease name {name!r} (must be a valid ArangoDB document key)")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError("ttl_seconds must be an integer")
    if not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError(f"ttl_seconds must be between 1 and {MAX_TTL_SECONDS}")


def _translate(operation: str, name: str, exc: BaseException) -> Exception | None:
    """Map driver errors to DatabaseUnavailable (retryable) or LeaseStoreError (not retryable)."""
    if isinstance(exc, DatabaseUnavailable):
        return exc
    if isinstance(exc, ServerConnectionError | OSError):
        return DatabaseUnavailable(f"lease {operation} for {name!r}: ArangoDB unreachable: {exc}")
    if isinstance(exc, ArangoServerError):
        code, http = getattr(exc, "error_code", None), getattr(exc, "http_code", None)
        if code in _TRANSIENT_ERROR_CODES or http in _TRANSIENT_HTTP_CODES:
            return DatabaseUnavailable(f"lease {operation} for {name!r} failed transiently: {exc}")
        return LeaseStoreError(
            f"lease {operation} for {name!r} failed [{code}]: {exc}. If the job_leases collection "
            "is missing, run `manage.py arango_migrate`."
        )
    return None


class LeaseRepository:
    def __init__(self, db: StandardDatabase) -> None:
        self.db = db

    def _execute(self, query: NamedQuery, name: str, binds: dict[str, Any]) -> list[Any]:
        """Run one lease statement atomically; re-evaluate it after a write-write conflict.

        A conflict (1200) or duplicate insert (1210) means another worker changed this lease
        between our read and our write, and our write was rejected. Re-running the statement
        re-reads the committed state, so contention resolves to "not yours" — never to ownership.
        """
        for attempt in range(1, CONFLICT_ATTEMPTS + 1):
            try:
                return run_query(self.db, query.name, query.aql, {**_LEASES, **binds}).rows
            except AQLQueryExecuteError as exc:
                if exc.error_code in _CONTENTION_CODES and attempt < CONFLICT_ATTEMPTS:
                    time.sleep(random.uniform(0, 0.005 * attempt))  # noqa: S311 - jitter only
                    continue
                translated = _translate(query.name, name, exc)
                if translated is None or translated is exc:
                    raise
                raise translated from exc
            except Exception as exc:
                translated = _translate(query.name, name, exc)
                if translated is None or translated is exc:
                    raise
                raise translated from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def acquire(self, name: str, *, token: str, owner: str, ttl_seconds: int) -> Lease | None:
        """Return the lease if the caller now owns it, ``None`` if another owner holds it."""
        validate_lease_request(name, ttl_seconds)
        rows = self._execute(
            ACQUIRE, name, {"key": name, "token": token, "owner": owner, "ttl": ttl_seconds}
        )
        if not rows:
            return None
        row = rows[0]
        if row["token"] != token:  # defensive: the query only returns the caller's own lease
            raise LeaseStoreError(f"lease acquire for {name!r} returned a foreign token")
        expired_for = row.get("expired_for_s")
        return Lease(
            name,
            token,
            int(row["fencing"]),
            float(row["expires_at"]),
            reclaimed_from=row.get("reclaimed_from"),
            expired_for_s=None if expired_for is None else float(expired_for),
        )

    def renew(self, lease: Lease, *, ttl_seconds: int) -> Lease | None:
        """Extend the lease; ``None`` means ownership was lost (expired or taken over)."""
        validate_lease_request(lease.name, ttl_seconds)
        rows = self._execute(
            RENEW, lease.name, {"key": lease.name, "token": lease.token, "ttl": ttl_seconds}
        )
        if not rows:
            return None
        return Lease(lease.name, lease.token, int(rows[0]["fencing"]), float(rows[0]["expires_at"]))

    def release(self, lease: Lease) -> bool:
        """Delete the lease if still owned; ``False`` means it already expired and was reclaimed."""
        rows = self._execute(RELEASE, lease.name, {"key": lease.name, "token": lease.token})
        return bool(rows)

    def describe(self, name: str) -> dict[str, Any] | None:
        """Holder, fencing and remaining validity in server seconds (negative = expired)."""
        rows = self._execute(DESCRIBE, name, {"key": name})
        return rows[0] if rows else None

    def get(self, name: str) -> dict[str, Any] | None:
        """Current lease document (diagnostics only; validity is decided by the queries above)."""
        doc = sync_optional(self.db.collection(s.JOB_LEASES).get(name))
        return doc if isinstance(doc, dict) else None
