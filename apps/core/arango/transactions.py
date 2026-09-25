"""Stream-transaction helpers.

:func:`run_in_transaction` executes a unit of work atomically across the declared collections
and retries the *whole unit* on write-write conflicts (error 1200), which happen when two
workers touch the same event concurrently. Units of work must therefore be idempotent — the
ingestion pipeline re-reads current state inside the transaction before deciding what to write.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Sequence
from typing import Any

from arango.database import Database, StandardDatabase, TransactionDatabase
from arango.exceptions import (
    AQLQueryExecuteError,
    ArangoServerError,
    DocumentInsertError,
    DocumentReplaceError,
    DocumentUpdateError,
    ServerConnectionError,
    TransactionAbortError,
)

from apps.core.arango.query import ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT, run_query
from apps.core.errors import DatabaseUnavailable
from config.logging import get_logger

log = get_logger(__name__)

_CONFLICT_ERRORS = (
    AQLQueryExecuteError,
    DocumentInsertError,
    DocumentUpdateError,
    DocumentReplaceError,
)


def _is_retryable(exc: BaseException, *, unique_violations: bool) -> bool:
    if not isinstance(exc, _CONFLICT_ERRORS):
        return False
    code = getattr(exc, "error_code", None)
    return code == ERR_CONFLICT or (unique_violations and code == ERR_UNIQUE_CONSTRAINT)


def run_in_transaction[T](
    db: StandardDatabase,
    work: Callable[[TransactionDatabase], T],
    *,
    write: Sequence[str],
    read: Sequence[str] = (),
    exclusive: Sequence[str] = (),
    max_attempts: int = 4,
    lock_timeout: int = 10,
    retry_unique_violations: bool = False,
) -> T:
    """Run ``work`` atomically; retry on write-write conflicts.

    ``retry_unique_violations`` also retries unique-index violations, for idempotent units that
    re-read state (a concurrent writer committed the same deterministic key first).
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            txn = db.begin_transaction(
                read=list(read) or None,
                write=list(write) or None,
                exclusive=list(exclusive) or None,
                allow_implicit=False,
                lock_timeout=lock_timeout,
            )
        except ServerConnectionError as exc:
            raise DatabaseUnavailable(f"cannot begin transaction: {exc}") from exc
        try:
            result = work(txn)
            txn.commit_transaction()
            return result
        except BaseException as exc:
            _abort_quietly(txn)
            retryable = _is_retryable(exc, unique_violations=retry_unique_violations)
            if retryable and attempt < max_attempts:
                delay = min(0.05 * 2**attempt, 1.0) * random.uniform(0.5, 1.5)  # noqa: S311
                log.info("txn_conflict_retry", attempt=attempt, delay_s=round(delay, 3))
                time.sleep(delay)
                continue
            if isinstance(exc, ServerConnectionError):
                raise DatabaseUnavailable(f"transaction failed: {exc}") from exc
            raise


def exclusive_query(
    db: Database,
    name: str,
    aql: str,
    binds: dict[str, Any],
    *,
    exclusive: Sequence[str],
    write: Sequence[str] = (),
) -> list[Any]:
    """Run one AQL statement holding exclusive locks (serialises check-then-insert limits)."""
    if not isinstance(db, StandardDatabase):  # already inside a transaction: run as-is
        return run_query(db, name, aql, binds).rows
    return run_in_transaction(
        db,
        lambda txn: run_query(txn, name, aql, binds).rows,
        write=write,
        exclusive=exclusive,
    )


def _abort_quietly(txn: TransactionDatabase) -> None:
    try:
        txn.abort_transaction()
    except (TransactionAbortError, ArangoServerError, ServerConnectionError) as exc:
        # Already committed/aborted server-side (e.g. the error came from commit itself).
        log.debug("txn_abort_skipped", error=str(exc))
