"""ArangoDB storage for operational metrics (replaces the Redis hash, lists and index set).

Writes are batched by :mod:`apps.core.metrics`; each flush is one AQL statement per kind, which
ArangoDB applies atomically, so concurrent flushes from many processes never lose increments
(contention is re-evaluated by :func:`apps.core.arango.atomic.run_atomic`). Metrics I/O never
records metrics itself (``record_metrics=False``), which would recurse.

Documents: ``metric_counters`` ``{_key: sha1(name), name, value}`` and ``metric_series``
``{_key: sha1(name), name, samples}`` with samples newest first (as Redis ``LPUSH`` kept them),
capped so the most recent observations survive.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable
from typing import Any

from arango.exceptions import ArangoError

from apps.core.arango import schema as s
from apps.core.arango.atomic import run_atomic
from apps.core.arango.client import get_db, sync
from apps.core.errors import DatabaseUnavailable


def _translated[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Callers outside apps/core/arango never see driver exceptions (boundary rule)."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except (ArangoError, OSError) as exc:
            raise DatabaseUnavailable(f"metrics store: {exc}") from exc

    return wrapper


_FLUSH_COUNTERS = """
FOR c IN @rows
  UPSERT { _key: c.key }
    INSERT { _key: c.key, name: c.name, value: c.delta }
    UPDATE { value: OLD.value + c.delta }
    IN @@counters
"""
_FLUSH_SERIES = """
FOR r IN @rows
  UPSERT { _key: r.key }
    INSERT { _key: r.key, name: r.name, samples: SLICE(r.values, 0, @cap) }
    UPDATE { samples: SLICE(APPEND(r.values, OLD.samples), 0, @cap) }
    IN @@series
"""
# Every process flushes the same hot counters (api_requests_total, ...): allow many re-runs.
FLUSH_ATTEMPTS = 30
_COUNTERS = "FOR c IN @@counters RETURN [c.name, c.value]"
_SAMPLES = "LET d = DOCUMENT(@@series, @key) RETURN d == null ? [] : d.samples"
_NAMES = "FOR d IN @@series SORT d.name RETURN d.name"


def doc_key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8"), usedforsecurity=False).hexdigest()


@_translated
def flush(counters: dict[str, int], series: dict[str, list[float]], cap: int) -> None:
    """Apply buffered deltas; ``series`` values are oldest first (observation order)."""
    db = get_db()
    if counters:
        rows = [{"key": doc_key(n), "name": n, "delta": d} for n, d in counters.items()]
        run_atomic(
            db, "metrics_flush_counters", _FLUSH_COUNTERS,
            {"@counters": s.METRIC_COUNTERS, "rows": rows},
            attempts=FLUSH_ATTEMPTS,
        )  # fmt: skip
    if series:
        rows = [
            {"key": doc_key(n), "name": n, "values": list(reversed(v[-cap:]))}
            for n, v in series.items()
        ]
        run_atomic(
            db, "metrics_flush_series", _FLUSH_SERIES,
            {"@series": s.METRIC_SERIES, "rows": rows, "cap": cap},
            attempts=FLUSH_ATTEMPTS,
        )  # fmt: skip


@_translated
def counters() -> dict[str, int]:
    rows = run_atomic(get_db(), "metrics_counters", _COUNTERS, {"@counters": s.METRIC_COUNTERS})
    return {str(name): int(value) for name, value in rows}


@_translated
def samples(name: str) -> list[float]:
    rows = run_atomic(
        get_db(), "metrics_samples", _SAMPLES, {"@series": s.METRIC_SERIES, "key": doc_key(name)}
    )
    return [float(v) for v in (rows[0] if rows else [])]


@_translated
def series_names() -> list[str]:
    rows: list[Any] = run_atomic(get_db(), "metrics_series", _NAMES, {"@series": s.METRIC_SERIES})
    return [str(n) for n in rows]


@_translated
def clear() -> None:
    db = get_db()
    sync(db.collection(s.METRIC_COUNTERS).truncate())
    sync(db.collection(s.METRIC_SERIES).truncate())


@_translated
def ping() -> None:
    """Raise DatabaseUnavailable if the store cannot be reached."""
    run_atomic(get_db(), "metrics_ping", "RETURN 1", {})
