"""Django cache backend on ArangoDB (replaces the Redis cache).

Serves every ``django.core.cache`` user: DRF throttles, login brute-force counters
(:mod:`apps.accounts.security`), analytics and diagnostics caches. It sits on the request path
(an anonymous API request makes four cache calls through the two DRF throttles), so the common
operations use ArangoDB's **document API** - one key lookup or write per call, no AQL parsing or
planning - and only the conditional operations run as one atomic AQL statement:

* ``get`` / ``has_key``: read by ``_key``; an entry past ``expires_at`` counts as absent;
* ``set``: insert-or-replace of the whole entry (overwrite mode ``replace``);
* ``add``: plain insert, atomic on the unique ``_key`` like Redis ``SET NX``; only when the key
  exists does one AQL statement replace it *if* it has expired (racing adders: one wins);
* ``incr``: one AQL statement increments server-side (concurrent increments are never lost; a
  missing/expired/non-integer key raises ``ValueError`` like Django's other backends);
* ``touch`` / ``delete``: single-document operations.

Expiry uses the application clock, as Django's database cache does (the job leases, where expiry is
safety-critical, use the ArangoDB server clock - decision P4). A TTL index on ``expires_at`` removes
expired entries in the background; correctness never depends on it. Integers are stored natively
(so ``incr`` works); other values are pickled, as Django's Redis backend does. Database errors
surface as ``DatabaseUnavailable``.
"""

from __future__ import annotations

import base64
import hashlib
import pickle
import time
from typing import Any

from arango.collection import StandardCollection
from arango.exceptions import ArangoError, DocumentInsertError, ServerConnectionError
from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache

from apps.core.arango import schema as s
from apps.core.arango.atomic import run_atomic
from apps.core.arango.client import get_db, sync, sync_optional
from apps.core.arango.query import ERR_UNIQUE_CONSTRAINT
from apps.core.errors import DatabaseUnavailable

_C = {"@c": s.CACHE_ENTRIES}
# One key can be hot (a throttle or login counter under attack): allow many conflict re-runs.
HOT_KEY_ATTEMPTS = 30

_ADD_IF_EXPIRED = """
FOR d IN @@c
  FILTER d._key == @k AND d.expires_at != null AND d.expires_at <= @now
  REPLACE d WITH @doc IN @@c
  RETURN 1
"""
_INCR = """
FOR d IN @@c
  FILTER d._key == @k AND (d.expires_at == null OR d.expires_at > @now) AND IS_NUMBER(d.i)
  UPDATE d WITH { i: d.i + @delta } IN @@c
  RETURN NEW.i
"""
_TOUCH = """
FOR d IN @@c
  FILTER d._key == @k AND (d.expires_at == null OR d.expires_at > @now)
  UPDATE d WITH { expires_at: @expires_at } IN @@c
  RETURN 1
"""
_FAILURES = (ArangoError, ServerConnectionError, OSError)


def _encode(value: Any) -> dict[str, Any]:
    if type(value) is int:  # exact int (not bool): stored natively so incr() can work on it
        return {"i": value}
    return {"p": base64.b64encode(pickle.dumps(value, pickle.HIGHEST_PROTOCOL)).decode("ascii")}


def _decode(doc: dict[str, Any]) -> Any:
    if doc.get("i") is not None:
        return int(doc["i"])
    return pickle.loads(base64.b64decode(doc["p"]))  # noqa: S301 - our own trusted store


def _live(doc: dict[str, Any] | None, now: float) -> bool:
    if doc is None:
        return False
    expires_at = doc.get("expires_at")
    return expires_at is None or float(expires_at) > now


def _unavailable(op: str, exc: Exception) -> DatabaseUnavailable:
    return DatabaseUnavailable(f"cache {op}: {exc}")


class ArangoCache(BaseCache):
    def __init__(self, location: str, params: dict[str, Any]) -> None:
        super().__init__(params)

    # -- helpers --------------------------------------------------------------------------
    @staticmethod
    def _col() -> StandardCollection:
        return get_db().collection(s.CACHE_ENTRIES)

    def _timeout(self, timeout: Any) -> float | None:
        if timeout is DEFAULT_TIMEOUT:
            timeout = self.default_timeout
        return None if timeout is None else float(timeout)

    def _ids(self, key: Any, version: int | None) -> tuple[str, str]:
        full = self.make_and_validate_key(key, version=version)
        return hashlib.sha256(full.encode("utf-8")).hexdigest(), full

    @staticmethod
    def _doc(k: str, full: str, value: Any, expires_at: float | None) -> dict[str, Any]:
        return {"_key": k, "k": full, "expires_at": expires_at, **_encode(value)}

    def _read(self, k: str) -> dict[str, Any] | None:
        try:
            return sync_optional(self._col().get(k))
        except _FAILURES as exc:
            raise _unavailable("get", exc) from exc

    @staticmethod
    def _aql(name: str, aql: str, binds: dict[str, Any]) -> list[Any]:
        try:
            return run_atomic(get_db(), name, aql, {**_C, **binds}, attempts=HOT_KEY_ATTEMPTS)
        except ArangoError as exc:
            raise _unavailable(name, exc) from exc

    def _remove(self, k: str) -> bool:
        try:
            return bool(self._col().delete(k, ignore_missing=True, silent=True))
        except _FAILURES as exc:
            raise _unavailable("delete", exc) from exc

    # -- Django cache API -----------------------------------------------------------------
    def get(self, key: Any, default: Any = None, version: int | None = None) -> Any:
        k, _ = self._ids(key, version)
        doc = self._read(k)
        if doc is None or not _live(doc, time.time()):
            return default
        return _decode(doc)

    def has_key(self, key: Any, version: int | None = None) -> bool:
        k, _ = self._ids(key, version)
        return _live(self._read(k), time.time())

    def set(
        self, key: Any, value: Any, timeout: Any = DEFAULT_TIMEOUT, version: int | None = None
    ) -> None:
        k, full = self._ids(key, version)
        ttl = self._timeout(timeout)
        if ttl is not None and ttl <= 0:
            self._remove(k)
            return
        doc = self._doc(k, full, value, None if ttl is None else time.time() + ttl)
        try:
            self._col().insert(doc, overwrite=True, silent=True)
        except _FAILURES as exc:
            raise _unavailable("set", exc) from exc

    def add(
        self, key: Any, value: Any, timeout: Any = DEFAULT_TIMEOUT, version: int | None = None
    ) -> bool:
        k, full = self._ids(key, version)
        ttl = self._timeout(timeout)
        if ttl is not None and ttl <= 0:
            return False
        now = time.time()
        doc = self._doc(k, full, value, None if ttl is None else now + ttl)
        try:
            self._col().insert(doc, silent=True)
            return True
        except DocumentInsertError as exc:
            if exc.error_code != ERR_UNIQUE_CONSTRAINT:
                raise _unavailable("add", exc) from exc
        except _FAILURES as exc:
            raise _unavailable("add", exc) from exc
        # The key exists: take it over only if it has expired (one statement, atomic).
        binds = {"k": k, "now": now, "doc": doc}
        return bool(self._aql("cache_add_expired", _ADD_IF_EXPIRED, binds))

    def incr(self, key: Any, delta: int = 1, version: int | None = None) -> int:
        k, full = self._ids(key, version)
        rows = self._aql("cache_incr", _INCR, {"k": k, "delta": delta, "now": time.time()})
        if not rows:
            raise ValueError(f"Key '{full}' not found")
        return int(rows[0])

    def touch(self, key: Any, timeout: Any = DEFAULT_TIMEOUT, version: int | None = None) -> bool:
        k, _ = self._ids(key, version)
        ttl = self._timeout(timeout)
        if ttl is not None and ttl <= 0:
            return self._remove(k)
        now = time.time()
        binds = {"k": k, "now": now, "expires_at": None if ttl is None else now + ttl}
        return bool(self._aql("cache_touch", _TOUCH, binds))

    def delete(self, key: Any, version: int | None = None) -> bool:
        k, _ = self._ids(key, version)
        return self._remove(k)

    def clear(self) -> None:
        sync(self._col().truncate())

    def close(self, **kwargs: Any) -> None:
        """Connections are pooled per process by apps.core.arango.client; nothing to close."""
