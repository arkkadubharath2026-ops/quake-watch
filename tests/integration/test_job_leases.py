"""Job leases against a real ArangoDB: atomicity, ownership, server-time expiry, fail-closed.

Races use a ``threading.Barrier`` so every worker starts its operation at the same moment, and
each worker has its own database connection (separate HTTP session), as separate processes would.
Expiry is made deterministic by moving ``expires_at`` into the past, or by polling the *server*
clock until it passes the lease's expiry — never by sleeping a fixed time.
"""

from __future__ import annotations

import itertools
import multiprocessing
import os
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from arango import ArangoClient
from arango.database import StandardDatabase

from apps.core import locks
from apps.core.arango import schema as s
from apps.core.arango.client import _connect, database_name
from apps.core.arango.leases import Lease, LeaseRepository
from apps.core.arango.migrate import apply_schema
from apps.core.errors import DatabaseUnavailable

WORKERS = 16
ROUNDS = 8


def _token() -> str:
    return uuid.uuid4().hex


def _server_now(db: StandardDatabase) -> float:
    return float(next(iter(db.aql.execute("RETURN DATE_NOW() / 1000"))))


def _expire(db: StandardDatabase, name: str) -> None:
    db.collection(s.JOB_LEASES).update({"_key": name, "expires_at": _server_now(db) - 1})


def _race(name: str, attempt: Callable[[LeaseRepository, str], Any]) -> list[Any]:
    """Run ``attempt(repo, name)`` from WORKERS threads released together; return outcomes."""
    barrier = threading.Barrier(WORKERS)
    outcomes: list[Any] = []
    lock = threading.Lock()
    repos = [LeaseRepository(_connect(database_name())) for _ in range(WORKERS)]

    def worker(repo: LeaseRepository) -> None:
        barrier.wait()
        try:
            result: Any = attempt(repo, name)
        except Exception as exc:  # noqa: BLE001 - every outcome is recorded and asserted on
            result = exc
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(r,)) for r in repos]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(outcomes) == WORKERS
    return outcomes


def _acquire_with_fresh_token(repo: LeaseRepository, name: str) -> Lease | None:
    return repo.acquire(name, token=_token(), owner="race", ttl_seconds=60)


def _single_winner(outcomes: list[Any]) -> Lease:
    errors = [o for o in outcomes if isinstance(o, Exception)]
    winners = [o for o in outcomes if isinstance(o, Lease)]
    assert errors == []
    assert len(winners) == 1
    return winners[0]


class TestAcquisition:
    def test_first_acquisition_succeeds_and_records_ownership(
        self, arango_db: StandardDatabase
    ) -> None:
        repo, token = LeaseRepository(arango_db), _token()
        before = _server_now(arango_db)
        lease = repo.acquire("sync:all_day", token=token, owner="w1", ttl_seconds=60)
        assert lease is not None
        assert lease.token == token
        assert lease.fencing == 1
        assert lease.reclaimed_from is None
        doc = repo.get("sync:all_day")
        assert doc is not None
        assert (doc["owner"], doc["token"]) == ("w1", token)
        assert before + 59 <= doc["expires_at"] <= _server_now(arango_db) + 61

    def test_second_worker_cannot_take_an_active_lease(self, arango_db: StandardDatabase) -> None:
        repo = LeaseRepository(arango_db)
        first = repo.acquire("sync:all_day", token=_token(), owner="w1", ttl_seconds=60)
        assert first is not None
        assert repo.acquire("sync:all_day", token=_token(), owner="w2", ttl_seconds=60) is None
        doc = repo.get("sync:all_day")
        assert doc is not None
        assert doc["token"] == first.token

    def test_expired_lease_is_reclaimed_with_a_new_fencing_token(
        self, arango_db: StandardDatabase
    ) -> None:
        repo = LeaseRepository(arango_db)
        old = repo.acquire("backfill:j1", token=_token(), owner="w1", ttl_seconds=60)
        assert old is not None
        _expire(arango_db, "backfill:j1")
        new = repo.acquire("backfill:j1", token=_token(), owner="w2", ttl_seconds=60)
        assert new is not None
        assert new.fencing == old.fencing + 1
        assert new.token != old.token
        assert new.reclaimed_from == "w1"  # observability: who held it before
        assert new.expired_for_s is not None
        assert new.expired_for_s >= 0

    def test_retry_with_the_same_token_returns_the_same_lease(
        self, arango_db: StandardDatabase
    ) -> None:
        # Models an acquire that committed but whose reply was lost: the retry (same token) must
        # recognise its own lease, not report contention and not bump the fencing token.
        repo, token = LeaseRepository(arango_db), _token()
        first = repo.acquire("sync:all_day", token=token, owner="w1", ttl_seconds=60)
        again = repo.acquire("sync:all_day", token=token, owner="w1", ttl_seconds=60)
        assert first is not None
        assert again is not None
        assert again.fencing == first.fencing

    def test_repeated_attempts_never_create_duplicate_lease_records(
        self, arango_db: StandardDatabase
    ) -> None:
        repo = LeaseRepository(arango_db)
        for _ in range(10):
            repo.acquire("sync:all_day", token=_token(), owner="w", ttl_seconds=60)
        assert arango_db.collection(s.JOB_LEASES).count() == 1


class TestConcurrency:
    def test_racing_workers_on_a_fresh_lease_have_exactly_one_winner(
        self, arango_db: StandardDatabase
    ) -> None:
        for round_ in range(ROUNDS):
            name = f"race:fresh:{round_}"
            winner = _single_winner(_race(name, _acquire_with_fresh_token))
            doc = arango_db.collection(s.JOB_LEASES).get(name)
            assert (doc["token"], doc["fencing"]) == (winner.token, 1)

    def test_racing_workers_on_an_expired_lease_have_exactly_one_winner(
        self, arango_db: StandardDatabase
    ) -> None:
        repo = LeaseRepository(arango_db)
        for round_ in range(ROUNDS):
            name = f"race:expired:{round_}"
            assert repo.acquire(name, token=_token(), owner="dead", ttl_seconds=60) is not None
            _expire(arango_db, name)
            winner = _single_winner(_race(name, _acquire_with_fresh_token))
            doc = arango_db.collection(s.JOB_LEASES).get(name)
            assert (doc["token"], doc["fencing"]) == (winner.token, 2)

    def test_stale_renewal_racing_takeovers_never_leaves_two_owners(
        self, arango_db: StandardDatabase
    ) -> None:
        repo = LeaseRepository(arango_db)
        for round_ in range(ROUNDS):
            name = f"race:renew:{round_}"
            stale = repo.acquire(name, token=_token(), owner="old", ttl_seconds=60)
            assert stale is not None
            _expire(arango_db, name)
            round_roles, round_lock = itertools.count(), threading.Lock()

            def attempt(
                r: LeaseRepository,
                n: str,
                stale: Lease = stale,
                roles: Any = round_roles,
                role_lock: threading.Lock = round_lock,
            ) -> Any:
                with role_lock:
                    role = next(roles)
                if role == 0:  # exactly one worker is the stale owner trying to renew
                    return ("renew", r.renew(stale, ttl_seconds=60))
                return ("acquire", r.acquire(n, token=_token(), owner="new", ttl_seconds=60))

            outcomes = _race(name, attempt)
            assert not [o for o in outcomes if isinstance(o, Exception)]
            renewals = [v for kind, v in outcomes if kind == "renew"]
            takeovers = [v for kind, v in outcomes if kind == "acquire" and v is not None]
            assert renewals == [None]  # an expired lease is never renewed
            assert len(takeovers) == 1
            doc = arango_db.collection(s.JOB_LEASES).get(name)
            assert (doc["token"], doc["fencing"]) == (takeovers[0].token, 2)


class TestOwnership:
    def test_owner_can_renew_while_valid(self, arango_db: StandardDatabase) -> None:
        repo = LeaseRepository(arango_db)
        lease = repo.acquire("sync:all_day", token=_token(), owner="w1", ttl_seconds=5)
        assert lease is not None
        renewed = repo.renew(lease, ttl_seconds=120)
        assert renewed is not None
        assert renewed.expires_at > lease.expires_at + 100
        assert renewed.fencing == lease.fencing

    def test_stale_owner_cannot_renew_or_release_the_replacement(
        self, arango_db: StandardDatabase
    ) -> None:
        repo = LeaseRepository(arango_db)
        old = repo.acquire("backfill:j1", token=_token(), owner="old", ttl_seconds=60)
        assert old is not None
        _expire(arango_db, "backfill:j1")
        new = repo.acquire("backfill:j1", token=_token(), owner="new", ttl_seconds=60)
        assert new is not None
        assert repo.renew(old, ttl_seconds=600) is None
        assert repo.release(old) is False
        doc = repo.get("backfill:j1")
        assert doc is not None
        assert (doc["token"], doc["fencing"]) == (new.token, new.fencing)

    def test_owner_cannot_renew_its_own_expired_lease(self, arango_db: StandardDatabase) -> None:
        repo = LeaseRepository(arango_db)
        lease = repo.acquire("sync:all_day", token=_token(), owner="w1", ttl_seconds=60)
        assert lease is not None
        _expire(arango_db, "sync:all_day")
        assert repo.renew(lease, ttl_seconds=60) is None  # lost: must not silently extend

    def test_release_of_an_already_removed_lease_is_safe(self, arango_db: StandardDatabase) -> None:
        repo = LeaseRepository(arango_db)
        lease = repo.acquire("sync:all_day", token=_token(), owner="w1", ttl_seconds=60)
        assert lease is not None
        assert repo.release(lease) is True
        assert repo.release(lease) is False
        assert repo.get("sync:all_day") is None


class TestServerTime:
    def test_expiry_uses_server_time_not_the_worker_clock(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(time, "time", lambda: 0.0)  # a wildly wrong worker clock
        lease = LeaseRepository(arango_db).acquire(
            "sync:all_day", token=_token(), owner="w1", ttl_seconds=60
        )
        monkeypatch.undo()
        server_now = _server_now(arango_db)
        assert lease is not None
        assert server_now + 50 < lease.expires_at < server_now + 61

    def test_crashed_owner_lease_becomes_reclaimable_after_server_expiry(
        self, arango_db: StandardDatabase
    ) -> None:
        # The owner "crashes" (never releases). Others are refused until the *server* clock
        # passes expires_at, then the next acquirer gets it with a new fencing token.
        repo = LeaseRepository(arango_db)
        crashed = repo.acquire("sync:all_day", token=_token(), owner="crashed", ttl_seconds=1)
        assert crashed is not None
        assert repo.acquire("sync:all_day", token=_token(), owner="w2", ttl_seconds=60) is None
        deadline = time.monotonic() + 10
        while _server_now(arango_db) <= crashed.expires_at:
            assert time.monotonic() < deadline, "server clock did not advance"
            time.sleep(0.05)
        taken = repo.acquire("sync:all_day", token=_token(), owner="w2", ttl_seconds=60)
        assert taken is not None
        assert taken.fencing == crashed.fencing + 1


def _failing_job() -> None:
    with locks.job_lock("sync:all_day", ttl_seconds=60):
        raise RuntimeError("job failed")


class TestJobLockIntegration:
    def test_job_lock_is_exclusive_while_held(self, arango_db: StandardDatabase) -> None:
        with (
            locks.job_lock("sync:all_day", ttl_seconds=60) as first,
            locks.job_lock("sync:all_day", ttl_seconds=60) as second,
        ):
            assert (first, second) == (True, False)
        with locks.job_lock("sync:all_day", ttl_seconds=60) as again:
            assert again is True

    def test_exception_in_job_releases_the_lease(self, arango_db: StandardDatabase) -> None:
        with pytest.raises(RuntimeError, match="job failed"):
            _failing_job()
        assert arango_db.collection(s.JOB_LEASES).count() == 0

    def test_lease_is_held_in_arango(self, arango_db: StandardDatabase) -> None:
        with locks.job_lock("sync:all_day", ttl_seconds=60) as acquired:
            assert acquired is True
            assert arango_db.collection(s.JOB_LEASES).get("sync:all_day") is not None

    def test_unreachable_database_fails_closed_after_bounded_retries(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dead = ArangoClient(hosts="http://127.0.0.1:9", request_timeout=2).db(
            "quakewatch_test", username="root", password="unused", verify=False
        )
        sleeps: list[float] = []
        entered: list[bool] = []
        monkeypatch.setattr(locks, "_repository", lambda: LeaseRepository(dead))
        monkeypatch.setattr(locks, "_sleep", sleeps.append)
        with (
            pytest.raises(locks.LockUnavailable) as info,
            locks.job_lock("sync:all_day", ttl_seconds=60),
        ):
            entered.append(True)
        assert entered == []
        assert info.value.attempts == locks.ACQUIRE_ATTEMPTS
        assert len(sleeps) == locks.ACQUIRE_ATTEMPTS - 1
        assert isinstance(info.value.__cause__, DatabaseUnavailable)

    def test_missing_collection_fails_closed_without_retry(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        system = _connect("_system")  # has no job_leases collection: models "not migrated yet"
        sleeps: list[float] = []
        entered: list[bool] = []
        monkeypatch.setattr(locks, "_repository", lambda: LeaseRepository(system))
        monkeypatch.setattr(locks, "_sleep", sleeps.append)
        with (
            pytest.raises(locks.LockUnavailable, match="arango_migrate"),
            locks.job_lock("sync:all_day", ttl_seconds=60),
        ):
            entered.append(True)
        assert entered == []
        assert sleeps == []


def _child_cycles(rounds: int) -> None:
    from apps.core.arango.client import get_client, get_db

    # The at-fork hook must have dropped the parent's client: no inherited connection pool.
    if get_client.cache_info().currsize != 0:
        os._exit(3)
    repo = LeaseRepository(get_db())
    for i in range(rounds):
        lease = repo.acquire(f"fork:{i % 2}", token=_token(), owner="child", ttl_seconds=30)
        if lease is not None:
            repo.release(lease)
    os._exit(0)


class TestForkSafety:
    def test_children_forked_after_db_use_do_not_share_connections(
        self, arango_db: StandardDatabase
    ) -> None:
        # Regression: a child reusing the parent's pooled keep-alive socket interleaved requests
        # and lost a begin_transaction reply, leaving the exclusive job_leases lock held.
        get_db_handle = _connect(database_name())
        assert get_db_handle.collection(s.JOB_LEASES).count() == 0  # parent uses its pool
        LeaseRepository(arango_db).release(  # and runs a transaction before forking
            Lease("fork:none", _token(), 1, 0.0)
        )
        ctx = multiprocessing.get_context("fork")
        children = [ctx.Process(target=_child_cycles, args=(15,)) for _ in range(8)]
        for child in children:
            child.start()
        for _ in range(30):  # the parent keeps using its own connection meanwhile
            arango_db.collection(s.JOB_LEASES).count()
        for child in children:
            child.join(timeout=120)
        assert [c.exitcode for c in children] == [0] * len(children)
        assert arango_db.list_transactions() == []


class TestMigration:
    def test_job_leases_collection_and_ttl_index_are_migrated(
        self, arango_db: StandardDatabase
    ) -> None:
        indexes = {i["name"]: i for i in arango_db.collection(s.JOB_LEASES).indexes()}
        ttl = indexes["qw_leases_ttl"]
        assert ttl["type"] == "ttl"
        assert ttl["fields"] == ["expires_at"]
        assert ttl.get("expireAfter", ttl.get("expiry_time")) == 0

    def test_migration_is_idempotent_for_job_leases(self, arango_db: StandardDatabase) -> None:
        report = apply_schema(arango_db)
        assert s.JOB_LEASES not in report.created_collections
        assert not [i for i in report.created_indexes if i.startswith(s.JOB_LEASES)]
