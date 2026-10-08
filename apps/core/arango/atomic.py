"""Single-statement atomic AQL execution with contention re-evaluation.

ArangoDB runs one AQL statement as one transaction. When two writers race on the same document,
one commits and the other fails with a write-write conflict (1200) or duplicate key (1210); its
writes are rolled back. Re-running the statement re-reads the committed state, so a racing
writer converges on the correct result instead of failing. Used by the shared-state stores
(cache, metrics, circuit breaker) that replaced Redis.

Driver errors are translated: connection problems and contention that outlasts ``attempts``
become :class:`DatabaseUnavailable`; other server errors propagate unchanged.
"""

from __future__ import annotations

import random
import time
from collections.abc import Mapping
from typing import Any

from arango.database import Database
from arango.exceptions import AQLQueryExecuteError, ServerConnectionError

from apps.core.arango.query import ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT, run_query
from apps.core.errors import DatabaseUnavailable

CONTENTION_CODES = frozenset({ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT})


def run_atomic(
    db: Database,
    name: str,
    aql: str,
    binds: Mapping[str, Any],
    *,
    attempts: int = 5,
    record_metrics: bool = False,
) -> list[Any]:
    """Execute one AQL statement; re-run it after contention; return its rows."""
    for attempt in range(1, attempts + 1):
        try:
            return run_query(db, name, aql, binds, record_metrics=record_metrics).rows
        except AQLQueryExecuteError as exc:
            if exc.error_code not in CONTENTION_CODES:
                raise
            if attempt == attempts:
                raise DatabaseUnavailable(f"{name}: contention persisted: {exc}") from exc
            # Full-jitter exponential backoff (2 ms .. 64 ms): hot single documents (counters)
            # converge without lock-step retries.
            time.sleep(random.uniform(0, min(0.064, 0.002 * 2**attempt)))  # noqa: S311 - jitter
        except (ServerConnectionError, OSError) as exc:
            raise DatabaseUnavailable(f"{name}: ArangoDB unreachable: {exc}") from exc
    raise AssertionError("unreachable")  # pragma: no cover
