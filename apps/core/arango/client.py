"""ArangoDB connection management.

One :class:`ArangoClient` per process (it owns an HTTP connection pool). Database handles are
cheap wrappers and are cached per database name. Only repositories and this package may import
python-arango (enforced by tests/architecture).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from arango.client import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import ArangoServerError, ServerConnectionError
from arango.http import DefaultHTTPClient
from arango.job import AsyncJob, BatchJob

from apps.core.errors import DatabaseUnavailable
from config.env import get_settings


def sync[T](result: T | AsyncJob[Any] | BatchJob[Any] | None) -> T:
    """Narrow python-arango's ``Result[T]`` union for APIs that never return None.

    We only use synchronous execution, so async/batch jobs are a programming error.
    """
    if result is None or isinstance(result, (AsyncJob, BatchJob)):
        raise TypeError("expected a synchronous, non-null ArangoDB result")
    return result


def sync_optional[T](result: T | AsyncJob[Any] | BatchJob[Any] | None) -> T | None:
    """Like :func:`sync` for APIs where None is a legitimate answer (e.g. ``collection.get``)."""
    if isinstance(result, (AsyncJob, BatchJob)):
        raise TypeError("expected a synchronous ArangoDB result")
    return result


@lru_cache(maxsize=1)
def get_client() -> ArangoClient:
    cfg = get_settings()
    http_client = DefaultHTTPClient(request_timeout=cfg.arango_request_timeout, retry_attempts=2)
    return ArangoClient(hosts=cfg.arango_url, http_client=http_client)


def _connect(name: str) -> StandardDatabase:
    cfg = get_settings()
    return get_client().db(
        name, username=cfg.arango_user, password=cfg.arango_password.get_secret_value()
    )


@lru_cache(maxsize=4)
def _cached_db(name: str) -> StandardDatabase:
    return _connect(name)


def _reset_after_fork() -> None:
    """Give a forked child its own connections (job worker processes, multiprocessing).

    python-arango shares one HTTP session pool across all handles of an ArangoClient. A child
    that kept using the parent's pooled keep-alive sockets would interleave requests with other
    processes on the same TCP connection and could lose a response — for example a
    ``begin_transaction`` — leaving an exclusive stream transaction open until the server's idle
    timeout (observed: every job lease blocked). Dropping the caches makes the child connect anew.
    """
    _cached_db.cache_clear()
    get_client.cache_clear()


os.register_at_fork(after_in_child=_reset_after_fork)


def database_name() -> str:
    return get_settings().arango_database_name


def get_db() -> StandardDatabase:
    """Handle to the configured application database (``<db>_test`` under tests)."""
    return _cached_db(database_name())


def ensure_database(name: str | None = None) -> StandardDatabase:
    """Create the application database if missing (requires a user allowed to use _system)."""
    target = name or database_name()
    try:
        sys_db = _connect("_system")
        if not sync(sys_db.has_database(target)):
            sys_db.create_database(target)
    except (ServerConnectionError, ArangoServerError) as exc:
        raise DatabaseUnavailable(f"cannot prepare ArangoDB database {target!r}: {exc}") from exc
    return _cached_db(target)


def drop_database(name: str) -> None:
    """Drop a database. Guarded: only ``*_test`` databases may be dropped programmatically."""
    if not name.endswith("_test"):
        raise ValueError("refusing to drop a non-test database")
    sys_db = _connect("_system")
    if sync(sys_db.has_database(name)):
        sys_db.delete_database(name)
    _cached_db.cache_clear()


def ping() -> tuple[bool, str | None]:
    """Readiness probe: can we reach the server and our database?"""
    try:
        version: Any = sync(get_db().version())
    except (ServerConnectionError, ArangoServerError, OSError) as exc:
        return False, str(exc)
    return True, str(version)
