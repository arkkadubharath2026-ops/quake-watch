"""Job-lock policy (unit level, no database): fail closed (P1), bounded retries, release rules.

Concurrency and server-time behaviour are covered against a real ArangoDB in
tests/integration/test_job_leases.py; these tests pin the decision logic around the repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from arango.exceptions import ArangoServerError, ServerConnectionError

from apps.core import locks
from apps.core.arango import leases
from apps.core.arango.leases import Lease, LeaseStoreError, validate_lease_request
from apps.core.errors import DatabaseUnavailable
from apps.ingestion import tasks


@dataclass
class FakeRepo:
    """Scripted LeaseRepository: each acquire() pops the next outcome (Lease, None or exception)."""

    outcomes: list[Any]
    release_result: Any = True
    acquire_calls: list[dict[str, Any]] = field(default_factory=list)
    released: list[Lease] = field(default_factory=list)

    def acquire(self, name: str, *, token: str, owner: str, ttl_seconds: int) -> Lease | None:
        self.acquire_calls.append({"name": name, "token": token, "ttl": ttl_seconds})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome == "own":
            return Lease(name, token, 1, 2_000_000_000.0)
        return outcome  # type: ignore[no-any-return]

    def release(self, lease: Lease) -> bool:
        self.released.append(lease)
        if isinstance(self.release_result, BaseException):
            raise self.release_result
        return bool(self.release_result)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeRepo, list[float]]:
    repo = FakeRepo(outcomes=[])
    sleeps: list[float] = []
    monkeypatch.setattr(locks, "_repository", lambda: repo)
    monkeypatch.setattr(locks, "_sleep", sleeps.append)
    monkeypatch.setattr(locks.metrics, "incr", lambda *a, **k: None)
    return repo, sleeps


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("the job body must not run without the lease")


def test_acquired_lease_runs_body_and_is_released(fake: tuple[FakeRepo, list[float]]) -> None:
    repo, sleeps = fake
    repo.outcomes = ["own"]
    with locks.job_lock("sync:all_day", ttl_seconds=600) as acquired:
        assert acquired is True
    assert [lease.name for lease in repo.released] == ["sync:all_day"]
    assert sleeps == []


def test_contended_lease_skips_body_and_never_releases(fake: tuple[FakeRepo, list[float]]) -> None:
    repo, _ = fake
    repo.outcomes = [None]
    with locks.job_lock("sync:all_day", ttl_seconds=600) as acquired:
        assert acquired is False
    assert repo.released == []  # never touch a lease we do not own


def test_transient_failures_are_retried_with_the_same_token(
    fake: tuple[FakeRepo, list[float]],
) -> None:
    repo, sleeps = fake
    repo.outcomes = [DatabaseUnavailable("down"), DatabaseUnavailable("down"), "own"]
    with locks.job_lock("backfill:job-1", ttl_seconds=1200) as acquired:
        assert acquired is True
    assert len(repo.acquire_calls) == 3
    assert len({call["token"] for call in repo.acquire_calls}) == 1  # idempotent retry
    assert len(sleeps) == 2
    assert all(0 <= s <= locks.RETRY_CAP_SECONDS for s in sleeps)


def test_unresolved_acquisition_fails_closed_after_bounded_retries(
    fake: tuple[FakeRepo, list[float]],
) -> None:
    repo, sleeps = fake
    repo.outcomes = [DatabaseUnavailable("down")] * locks.ACQUIRE_ATTEMPTS
    entered: list[bool] = []
    with (
        pytest.raises(locks.LockUnavailable) as info,
        locks.job_lock("sync:all_day", ttl_seconds=600),
    ):
        entered.append(True)
    assert entered == []  # the protected body never runs unlocked
    assert len(repo.acquire_calls) == locks.ACQUIRE_ATTEMPTS
    assert len(sleeps) == locks.ACQUIRE_ATTEMPTS - 1  # no sleep after the last attempt
    assert repo.released == []
    assert info.value.attempts == locks.ACQUIRE_ATTEMPTS
    assert "was not run" in info.value.message


def test_non_transient_store_error_fails_closed_without_retry(
    fake: tuple[FakeRepo, list[float]],
) -> None:
    repo, sleeps = fake
    repo.outcomes = [LeaseStoreError("collection job_leases not found")]
    with (
        pytest.raises(locks.LockUnavailable, match="job_leases"),
        locks.job_lock("sync:all_day", ttl_seconds=600),
    ):
        _forbidden()
    assert len(repo.acquire_calls) == 1
    assert sleeps == []


def test_programming_errors_propagate_and_never_enter_the_body(
    fake: tuple[FakeRepo, list[float]],
) -> None:
    repo, _ = fake
    repo.outcomes = [TypeError("bug")]
    with pytest.raises(TypeError, match="bug"), locks.job_lock("sync:all_day", ttl_seconds=600):
        _forbidden()
    assert len(repo.acquire_calls) == 1


def _failing_job() -> None:
    with locks.job_lock("sync:all_day", ttl_seconds=600):
        raise RuntimeError("job failed")


def test_exception_in_body_still_releases_and_propagates(
    fake: tuple[FakeRepo, list[float]],
) -> None:
    repo, _ = fake
    repo.outcomes = ["own"]
    with pytest.raises(RuntimeError, match="job failed"):
        _failing_job()
    assert len(repo.released) == 1


@pytest.mark.parametrize("result", [False, DatabaseUnavailable("down"), LeaseStoreError("x")])
def test_lost_or_failed_release_never_masks_the_job_result(
    fake: tuple[FakeRepo, list[float]], result: Any
) -> None:
    repo, _ = fake
    repo.outcomes = ["own"]
    repo.release_result = result
    with locks.job_lock("sync:all_day", ttl_seconds=600) as acquired:
        assert acquired is True  # completes normally; the lease expires on its own
    assert len(repo.released) == 1


def test_sync_task_skips_and_never_syncs_when_lock_unavailable(
    fake: tuple[FakeRepo, list[float]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = fake
    repo.outcomes = [DatabaseUnavailable("down")] * locks.ACQUIRE_ATTEMPTS
    monkeypatch.setattr(tasks, "build_usgs_client", _forbidden)
    assert tasks.sync_feed("all_day") == {"status": "skipped_lock_unavailable"}


def test_backfill_task_skips_and_never_runs_when_lock_unavailable(
    fake: tuple[FakeRepo, list[float]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = fake
    repo.outcomes = [LeaseStoreError("missing")]
    monkeypatch.setattr(tasks, "build_usgs_client", _forbidden)
    result = tasks.run_backfill.apply(args=["job-9"]).get()
    assert result == {"job_id": "job-9", "status": "skipped_lock_unavailable"}


def test_lease_ttls_exceed_task_hard_time_limits() -> None:
    sync_limit, backfill_limit = tasks.sync_feed.time_limit, tasks.run_backfill.time_limit
    assert sync_limit is not None
    assert backfill_limit is not None
    assert sync_limit < tasks.SYNC_LEASE_TTL_SECONDS
    assert backfill_limit < tasks.BACKFILL_LEASE_TTL_SECONDS


@pytest.mark.parametrize(
    ("name", "ttl", "message"),
    [
        ("", 10, "invalid lease name"),
        ("has space", 10, "invalid lease name"),
        ("x" * 255, 10, "invalid lease name"),
        ("ok:name", 0, "between 1 and"),
        ("ok:name", 86401, "between 1 and"),
        ("ok", True, "must be an integer"),
    ],
)
def test_invalid_lease_requests_are_rejected(name: str, ttl: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_lease_request(name, ttl)


def _driver_error(cls: type[ArangoServerError], error_code: int, http_code: int) -> Exception:
    exc = cls.__new__(cls)  # python-arango errors need a live request/response to construct
    exc.error_code = error_code
    exc.http_code = http_code
    return exc


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_driver_error(ServerConnectionError, 0, 0), DatabaseUnavailable),
        (OSError("connection reset"), DatabaseUnavailable),
        (_driver_error(ArangoServerError, 18, 409), DatabaseUnavailable),  # lock timeout
        (_driver_error(ArangoServerError, 1200, 409), DatabaseUnavailable),  # write conflict
        (_driver_error(ArangoServerError, 1, 503), DatabaseUnavailable),  # unavailable
        (_driver_error(ArangoServerError, 1203, 404), LeaseStoreError),  # not migrated
    ],
)
def test_driver_errors_are_classified(exc: BaseException, expected: type[Exception]) -> None:
    assert isinstance(leases._translate("leases_acquire", "sync:x", exc), expected)


@pytest.fixture
def metric_names(fake: tuple[FakeRepo, list[float]], monkeypatch: pytest.MonkeyPatch) -> list[str]:
    names: list[str] = []
    monkeypatch.setattr(locks.metrics, "incr", lambda name, *a, **k: names.append(name))
    return names


@pytest.mark.parametrize(
    ("outcomes", "release_result", "expected"),
    [
        (["own"], True, ["job_lock_acquired"]),
        ([None], True, ["job_lock_contended"]),
        (["own"], False, ["job_lock_acquired", "job_lock_lost"]),
        (["own"], DatabaseUnavailable("down"), ["job_lock_acquired", "job_lock_release_failed"]),
    ],
)
def test_each_outcome_is_counted(
    fake: tuple[FakeRepo, list[float]],
    metric_names: list[str],
    outcomes: list[Any],
    release_result: Any,
    expected: list[str],
) -> None:
    repo, _ = fake
    repo.outcomes, repo.release_result = outcomes, release_result
    with locks.job_lock("sync:all_day", ttl_seconds=600):
        pass
    assert metric_names == expected


def test_reclaimed_lease_is_reported(
    fake: tuple[FakeRepo, list[float]], metric_names: list[str]
) -> None:
    repo, _ = fake
    reclaimed = Lease("sync:all_day", "t" * 32, 7, 2e9, reclaimed_from="host:42", expired_for_s=3.5)
    repo.outcomes = [reclaimed]
    with locks.job_lock("sync:all_day", ttl_seconds=600) as acquired:
        assert acquired is True
    assert metric_names == ["job_lock_acquired", "job_lease_reclaimed"]


def test_retry_exhaustion_is_counted_once(
    fake: tuple[FakeRepo, list[float]], metric_names: list[str]
) -> None:
    repo, _ = fake
    repo.outcomes = [DatabaseUnavailable("down")] * locks.ACQUIRE_ATTEMPTS
    with pytest.raises(locks.LockUnavailable), locks.job_lock("sync:all_day", ttl_seconds=600):
        _forbidden()
    assert metric_names == ["job_lock_unavailable"]


class _RenewRepo:
    def __init__(self, result: Any) -> None:
        self.result = result

    def renew(self, lease: Lease, *, ttl_seconds: int) -> Lease | None:
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    ("result", "metric"),
    [(Lease("sync:x", "t" * 32, 1, 3e9), None), (None, "job_lease_renew_lost")],
)
def test_renew_helper_reports_renewal_and_loss(
    monkeypatch: pytest.MonkeyPatch, result: Any, metric: str | None
) -> None:
    names: list[str] = []
    monkeypatch.setattr(locks.metrics, "incr", lambda name, *a, **k: names.append(name))
    monkeypatch.setattr(locks, "_repository", lambda: _RenewRepo(result))
    assert locks.renew_job_lease(Lease("sync:x", "t" * 32, 1, 2e9), ttl_seconds=60) == result
    assert names == ([] if metric is None else [metric])


def test_renew_helper_raises_when_ownership_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    names: list[str] = []
    monkeypatch.setattr(locks.metrics, "incr", lambda name, *a, **k: names.append(name))
    monkeypatch.setattr(locks, "_repository", lambda: _RenewRepo(DatabaseUnavailable("down")))
    with pytest.raises(DatabaseUnavailable, match="down"):
        locks.renew_job_lease(Lease("sync:x", "t" * 32, 1, 2e9), ttl_seconds=60)
    assert names == ["job_lease_renew_failed"]


def test_unrelated_errors_are_not_translated() -> None:
    assert leases._translate("leases_acquire", "sync:x", KeyError("bug")) is None


def _conflict(code: int) -> Exception:
    from arango.exceptions import AQLQueryExecuteError

    exc = AQLQueryExecuteError.__new__(AQLQueryExecuteError)
    exc.error_code = code
    exc.http_code = 409
    return exc


def test_conflict_is_re_evaluated_against_committed_state(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def run_query(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            raise _conflict(1200)  # another worker committed first
        return type("R", (), {"rows": []})()  # re-read: the lease is someone else's

    monkeypatch.setattr(leases, "run_query", run_query)
    monkeypatch.setattr(leases.time, "sleep", lambda s: None)
    repo = leases.LeaseRepository(db=None)  # type: ignore[arg-type]
    assert repo.acquire("sync:x", token="t" * 32, owner="w", ttl_seconds=60) is None
    assert len(calls) == 2


def test_persistent_conflict_is_transient_never_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_query(*args: Any, **kwargs: Any) -> Any:
        raise _conflict(1210)

    monkeypatch.setattr(leases, "run_query", run_query)
    monkeypatch.setattr(leases.time, "sleep", lambda s: None)
    repo = leases.LeaseRepository(db=None)  # type: ignore[arg-type]
    with pytest.raises(DatabaseUnavailable, match="transiently"):
        repo.acquire("sync:x", token="t" * 32, owner="w", ttl_seconds=60)
