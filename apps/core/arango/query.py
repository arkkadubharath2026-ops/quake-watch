"""Instrumented AQL execution.

All repositories execute AQL through :func:`run_query` so that every query is named, timed
(``aql_latency_ms:<name>`` metric + structured log on slow queries), bounded by a server-side
``max_runtime``, and driver/connection errors are translated into :class:`DatabaseUnavailable`.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from arango.database import Database
from arango.exceptions import AQLQueryExecuteError, ServerConnectionError

from apps.core import metrics
from apps.core.arango.client import sync
from apps.core.errors import DatabaseUnavailable
from config.logging import get_logger

log = get_logger(__name__)

SLOW_QUERY_MS = 250.0
DEFAULT_MAX_RUNTIME_S = 30

# ArangoDB error numbers we react to explicitly.
ERR_CONFLICT = 1200
ERR_UNIQUE_CONSTRAINT = 1210
ERR_DOCUMENT_NOT_FOUND = 1202
ERR_QUERY_KILLED = 1500


@dataclass(frozen=True, slots=True)
class QueryResult:
    rows: list[Any]
    full_count: int | None
    duration_ms: float


def run_query(
    db: Database,
    name: str,
    aql: str,
    bind_vars: Mapping[str, Any] | None = None,
    *,
    full_count: bool = False,
    max_runtime: int = DEFAULT_MAX_RUNTIME_S,
    batch_size: int = 1000,
    record_metrics: bool = True,
) -> QueryResult:
    started = time.perf_counter()
    try:
        cursor = sync(
            db.aql.execute(
                aql,
                bind_vars=dict(bind_vars or {}),
                full_count=full_count or None,
                max_runtime=cast(Any, max_runtime),  # stub types it as numbers.Number
                batch_size=batch_size,
            )
        )
        rows = list(cursor)
        stats = cursor.statistics() or {}
    except ServerConnectionError as exc:
        raise DatabaseUnavailable(f"ArangoDB unreachable during {name}: {exc}") from exc
    except AQLQueryExecuteError as exc:
        if exc.error_code in (ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT):
            raise  # callers (transactions/pipeline) handle conflicts explicitly
        log.error("aql_failed", query=name, error_code=exc.error_code, error=exc.error_message)
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    if record_metrics:  # hot write paths opt out; they report per-batch metrics instead
        metrics.observe(f"aql_latency_ms:{name}", duration_ms)
    if duration_ms >= SLOW_QUERY_MS:
        log.warning("aql_slow", query=name, duration_ms=duration_ms)
    total = stats.get("fullCount", stats.get("full_count")) if full_count else None
    return QueryResult(rows=rows, full_count=total, duration_ms=duration_ms)


def explain(db: Database, aql: str, bind_vars: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics page)."""
    plan = sync(db.aql.explain(aql, bind_vars=dict(bind_vars or {}), all_plans=False))
    return plan if isinstance(plan, dict) else {"plans": plan}


def indexes_used(plan: dict[str, Any]) -> list[str]:
    """Index names (or types) used by a plan, including traversal edge indexes."""
    names: list[str] = []

    def collect(entries: Any) -> None:
        if isinstance(entries, list):
            for index in entries:
                if isinstance(index, dict):
                    names.append(str(index.get("name") or index.get("type")))
        elif isinstance(entries, dict):  # traversal nodes: {"base": [...], "levels": {...}}
            for value in entries.values():
                collect(value)

    for node in plan.get("nodes", []):  # subqueries are flattened into the node list
        collect(node.get("indexes"))
    return names
