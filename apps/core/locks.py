"""Job locks: at most one running instance per job name, backed by ArangoDB leases.

:func:`job_lease` / :func:`job_lock` wrap :class:`apps.core.arango.leases.LeaseRepository`
(one atomic AQL statement per operation; token-checked renew/release; expiry by ArangoDB
server time — decision P4).

Failure policy (decision P1): **fail closed**. Acquisition is retried a bounded number of times
(``ACQUIRE_ATTEMPTS``, full-jitter backoff) on transient database errors; if ownership still cannot
be established, :class:`LockUnavailable` is raised and the job body never runs unlocked. The same
token is reused across retries, so an attempt that committed but whose reply was lost is
recognised as the caller's own lease instead of being mistaken for contention.

A failed *release* is logged and counted but not raised: the job's work is already done, and the
lease expires on its own at server time, so the only cost is a delayed next run.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from apps.core import metrics
from apps.core.arango.client import get_db
from apps.core.arango.leases import Lease, LeaseRepository, LeaseStoreError
from apps.core.errors import DatabaseUnavailable
from apps.core.resilience import backoff_delay
from config.logging import get_logger

log = get_logger(__name__)

ACQUIRE_ATTEMPTS = 3
RETRY_BASE_SECONDS = 0.5
RETRY_CAP_SECONDS = 4.0

_sleep: Callable[[float], None] = time.sleep  # replaced in tests
_repository: Callable[[], LeaseRepository] = lambda: LeaseRepository(get_db())  # noqa: E731


class LockUnavailable(DatabaseUnavailable):
    """Lease ownership could not be established; the job must not run (fail closed)."""

    code = "lock_unavailable"

    def __init__(self, name: str, attempts: int, cause: BaseException) -> None:
        super().__init__(
            f"job lock {name!r} unavailable after {attempts} attempt(s): {cause}. The job was not "
            "run; the next scheduled run or a manual retry will try again."
        )
        self.lock_name = name
        self.attempts = attempts


def _owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _acquire(repo: LeaseRepository, name: str, token: str, ttl_seconds: int) -> Lease | None:
    last: BaseException | None = None
    for attempt in range(1, ACQUIRE_ATTEMPTS + 1):
        try:
            return repo.acquire(name, token=token, owner=_owner(), ttl_seconds=ttl_seconds)
        except LeaseStoreError as exc:  # not transient (e.g. collection missing): no retries
            metrics.incr("job_lock_unavailable")
            log.error("job_lock_unavailable", lock=name, attempts=attempt, error=str(exc))
            raise LockUnavailable(name, attempt, exc) from exc
        except DatabaseUnavailable as exc:
            last = exc
            log.warning("job_lock_acquire_retry", lock=name, attempt=attempt, error=str(exc))
            if attempt < ACQUIRE_ATTEMPTS:
                _sleep(backoff_delay(attempt, base=RETRY_BASE_SECONDS, cap=RETRY_CAP_SECONDS))
    assert last is not None
    metrics.incr("job_lock_unavailable")
    log.error("job_lock_unavailable", lock=name, attempts=ACQUIRE_ATTEMPTS, error=str(last))
    raise LockUnavailable(name, ACQUIRE_ATTEMPTS, last) from last


def _release(repo: LeaseRepository, lease: Lease) -> None:
    try:
        released = repo.release(lease)
    except (DatabaseUnavailable, LeaseStoreError) as exc:
        metrics.incr("job_lock_release_failed")
        log.warning(
            "job_lock_release_failed",
            lock=lease.name,
            fencing=lease.fencing,
            error=str(exc),
            note="the lease expires on its own at server time",
        )
        return
    if not released:
        # The job outlived its lease and another worker reclaimed it: the job's work overlapped.
        metrics.incr("job_lock_lost")
        log.warning("job_lock_lost_before_release", lock=lease.name, fencing=lease.fencing)
        return
    log.info("job_lock_released", lock=lease.name, fencing=lease.fencing)


def describe_holder(name: str) -> str:
    """Human-readable holder of ``name`` for operator messages (never decides ownership)."""
    try:
        info = _repository().describe(name)
    except (DatabaseUnavailable, LeaseStoreError):
        return "holder unknown: lease store unavailable"
    if info is None:
        return "the holder has just finished"
    remaining = max(0, round(float(info["expires_in_s"])))
    return f"held by {info['owner']}, fencing {info['fencing']}, expires in {remaining} s"


def renew_job_lease(lease: Lease, *, ttl_seconds: int) -> Lease | None:
    """Extend ``lease``; ``None`` means ownership is lost and the caller must stop its work.

    Prepared for decision P3 (renewal policy) and not called by any job yet. Database errors are
    raised (``DatabaseUnavailable``/``LeaseStoreError``): ownership is then unknown, and the
    caller must not assume it still holds the lease.
    """
    try:
        renewed = _repository().renew(lease, ttl_seconds=ttl_seconds)
    except (DatabaseUnavailable, LeaseStoreError) as exc:
        metrics.incr("job_lease_renew_failed")
        log.warning(
            "job_lease_renew_failed", lock=lease.name, fencing=lease.fencing, error=str(exc)
        )
        raise
    if renewed is None:
        metrics.incr("job_lease_renew_lost")
        log.warning("job_lease_renew_lost", lock=lease.name, fencing=lease.fencing)
        return None
    log.info("job_lease_renewed", lock=lease.name, fencing=lease.fencing, ttl_s=ttl_seconds)
    return renewed


@contextmanager
def job_lease(name: str, *, ttl_seconds: int) -> Iterator[Lease | None]:
    """Yield the :class:`Lease` if acquired, ``None`` if another worker holds it.

    Raises :class:`LockUnavailable` (before the body runs) when ownership cannot be established.
    The lease is released when the body finishes, also when it raises.
    """
    repo = _repository()
    token = uuid.uuid4().hex
    lease = _acquire(repo, name, token, ttl_seconds)
    if lease is None:
        metrics.incr("job_lock_contended")
        log.info("job_lock_contended", lock=name)
        yield None
        return
    metrics.incr("job_lock_acquired")
    log.info("job_lock_acquired", lock=name, fencing=lease.fencing, ttl_s=ttl_seconds)
    if lease.reclaimed_from is not None:
        # The previous owner never released: it crashed, was killed, or outlived its lease.
        metrics.incr("job_lease_reclaimed")
        log.warning(
            "job_lease_reclaimed",
            lock=name,
            fencing=lease.fencing,
            previous_owner=lease.reclaimed_from,
            expired_for_s=round(lease.expired_for_s or 0.0, 1),
        )
    try:
        yield lease
    finally:
        _release(repo, lease)


@contextmanager
def job_lock(name: str, *, ttl_seconds: int) -> Iterator[bool]:
    """Yield True if the lock was acquired; the body should skip work when False.

    Raises :class:`LockUnavailable` instead of running the body unlocked (fail closed).
    """
    with job_lease(name, ttl_seconds=ttl_seconds) as lease:
        yield lease is not None
