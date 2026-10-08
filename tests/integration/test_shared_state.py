"""Shared state that replaced Redis, on the real ArangoDB test database.

Covers the Django cache backend (semantics, server-time expiry, atomic ``add``/``incr`` under
thread races), login brute-force limits through that cache, and the circuit breaker's atomic
half-open probe and failure counting. Races release all workers with a ``threading.Barrier``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from arango.database import StandardDatabase
from django.core.cache import cache, caches

from apps.accounts import security
from apps.core.arango import cache as arango_cache
from apps.core.arango import schema as s
from apps.core.errors import CircuitOpen, DatabaseUnavailable
from apps.core.resilience import CircuitBreaker

WORKERS = 10


def _race(attempt: Callable[[], Any], workers: int = WORKERS) -> list[Any]:
    barrier = threading.Barrier(workers)
    outcomes: list[Any] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        try:
            result: Any = attempt()
        except Exception as exc:  # noqa: BLE001 - every outcome is recorded and asserted on
            result = exc
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(outcomes) == workers
    return outcomes


class TestCacheSemantics:
    def test_backend_is_arango(self) -> None:
        assert isinstance(caches["default"], arango_cache.ArangoCache)

    def test_get_set_delete_and_values_round_trip(self, arango_db: StandardDatabase) -> None:
        value = {"list": [1, 2.5, "x"], "tuple": (1, 2), "none": None}
        assert cache.get("k", "default") == "default"
        cache.set("k", value)
        assert cache.get("k") == value
        cache.set("n", 7)
        assert cache.get("n") == 7
        assert type(cache.get("n")) is int
        cache.set("b", True)
        assert cache.get("b") is True  # bools are not mistaken for ints
        assert cache.has_key("k") is True
        assert cache.delete("k") is True
        assert cache.delete("k") is False
        assert cache.get("k") is None

    def test_keys_are_prefixed_and_hashed(self, arango_db: StandardDatabase) -> None:
        cache.set("visible", 1)
        doc = next(iter(arango_db.collection(s.CACHE_ENTRIES).all()))
        assert doc["k"] == "qw-test:1:visible"
        assert len(doc["_key"]) == 64

    def test_versions_are_isolated(self, arango_db: StandardDatabase) -> None:
        cache.set("v", "one", version=1)
        cache.set("v", "two", version=2)
        assert (cache.get("v", version=1), cache.get("v", version=2)) == ("one", "two")

    def test_expiry(self, arango_db: StandardDatabase) -> None:
        cache.set("short", "x", timeout=1)
        assert cache.get("short") == "x"
        time.sleep(1.3)
        assert cache.get("short") is None
        assert cache.has_key("short") is False

    def test_timeout_none_never_expires_and_zero_deletes(self, arango_db: StandardDatabase) -> None:
        cache.set("forever", 1, timeout=None)
        doc = next(iter(arango_db.collection(s.CACHE_ENTRIES).all()))
        assert doc["expires_at"] is None
        cache.set("forever", 1, timeout=0)
        assert cache.get("forever") is None
        assert cache.add("never", 1, timeout=0) is False

    def test_add_only_when_absent_or_expired(self, arango_db: StandardDatabase) -> None:
        assert cache.add("a", 1, timeout=1) is True
        assert cache.add("a", 2) is False
        assert cache.get("a") == 1
        time.sleep(1.3)
        assert cache.add("a", 3) is True
        assert cache.get("a") == 3

    def test_incr_semantics(self, arango_db: StandardDatabase) -> None:
        with pytest.raises(ValueError, match="not found"):
            cache.incr("missing")
        cache.set("c", 1)
        assert cache.incr("c") == 2
        assert cache.incr("c", 5) == 7
        assert cache.decr("c", 2) == 5
        cache.set("s", "text")
        with pytest.raises(ValueError, match="not found"):
            cache.incr("s")  # not an integer: same error as a missing key

    def test_incr_keeps_the_ttl_set_by_add(self, arango_db: StandardDatabase) -> None:
        cache.add("window", 0, timeout=1)
        assert cache.incr("window") == 1
        time.sleep(1.3)
        with pytest.raises(ValueError, match="not found"):
            cache.incr("window")  # the window was not extended by the increment

    def test_touch(self, arango_db: StandardDatabase) -> None:
        assert cache.touch("absent", 10) is False
        cache.set("t", "x", timeout=1)
        assert cache.touch("t", 30) is True
        time.sleep(1.3)
        assert cache.get("t") == "x"

    def test_many_and_clear(self, arango_db: StandardDatabase) -> None:
        cache.set_many({"m1": 1, "m2": 2})
        assert cache.get_many(["m1", "m2", "m3"]) == {"m1": 1, "m2": 2}
        cache.delete_many(["m1"])
        assert cache.get("m1") is None
        cache.clear()
        assert arango_db.collection(s.CACHE_ENTRIES).count() == 0

    def test_outage_raises_database_unavailable(
        self,
        arango_db: StandardDatabase,
        dead_arango_db: StandardDatabase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(arango_cache, "get_db", lambda: dead_arango_db)
        with pytest.raises(DatabaseUnavailable):
            cache.get("k")
        with pytest.raises(DatabaseUnavailable):
            cache.incr("k")


class TestCacheAtomicity:
    def test_concurrent_add_has_exactly_one_winner(self, arango_db: StandardDatabase) -> None:
        for round_ in range(5):
            outcomes = _race(lambda r=round_: cache.add(f"race:{r}", "v", 60))
            assert outcomes.count(True) == 1, outcomes
            assert outcomes.count(False) == WORKERS - 1, outcomes

    def test_concurrent_incr_loses_no_update(self, arango_db: StandardDatabase) -> None:
        cache.set("counter", 0, 60)

        def bump() -> int:
            last = 0
            for _ in range(20):
                last = cache.incr("counter")
            return last

        outcomes = _race(bump)
        assert all(isinstance(o, int) for o in outcomes), outcomes
        assert cache.get("counter") == WORKERS * 20


class TestLoginThrottle:
    def test_pair_limit_enforced(self, arango_db: StandardDatabase) -> None:
        decisions = [security.register_attempt("alice", "203.0.113.5") for _ in range(12)]
        assert [d.allowed for d in decisions] == [True] * security.PAIR_LIMIT + [False] * 2
        assert security.is_locked("alice", "203.0.113.5") is True
        assert security.is_locked("alice", "198.51.100.7") is False

    def test_concurrent_attempts_cannot_exceed_the_limit(self, arango_db: StandardDatabase) -> None:
        outcomes = _race(lambda: security.register_attempt("bob", "203.0.113.9"), workers=20)
        assert sum(1 for d in outcomes if d.allowed) == security.PAIR_LIMIT, outcomes

    def test_success_clears_counters_and_marks_known_address(
        self, arango_db: StandardDatabase
    ) -> None:
        for _ in range(security.PAIR_LIMIT):
            security.register_attempt("carol", "203.0.113.20")
        assert security.is_locked("carol", "203.0.113.20") is True
        security.record_success("carol", "203.0.113.20")
        assert security.is_locked("carol", "203.0.113.20") is False
        assert security.register_attempt("carol", "203.0.113.20").allowed is True

    def test_window_expires(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(security, "WINDOW_SECONDS", 1)
        for _ in range(security.PAIR_LIMIT + 1):
            security.register_attempt("dave", "203.0.113.30")
        assert security.register_attempt("dave", "203.0.113.30").allowed is False
        time.sleep(1.3)
        assert security.register_attempt("dave", "203.0.113.30").allowed is True


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class TestBreakerConcurrency:
    def test_exactly_one_half_open_probe(self, arango_db: StandardDatabase) -> None:
        clock = FakeClock()
        cb = CircuitBreaker("RACE", failure_threshold=3, reset_seconds=60, clock=clock)
        for _ in range(3):
            cb.record_failure()
        clock.now += 61
        outcomes = _race(cb.before_call)
        assert outcomes.count(None) == 1, outcomes
        assert sum(isinstance(o, CircuitOpen) for o in outcomes) == WORKERS - 1, outcomes

    def test_concurrent_failures_are_all_counted(self, arango_db: StandardDatabase) -> None:
        cb = CircuitBreaker("COUNT", failure_threshold=1000, reset_seconds=60)
        outcomes = _race(cb.record_failure)
        assert outcomes == [None] * WORKERS
        assert cb.state().consecutive_failures == WORKERS
        assert cb.state().status == "closed"

    def test_failure_count_expires(self, arango_db: StandardDatabase) -> None:
        cb = CircuitBreaker("EXPIRE", failure_threshold=5, reset_seconds=60)
        cb.record_failure()
        arango_db.aql.execute(
            "FOR d IN @@b UPDATE d WITH { failures_exp: DATE_NOW() / 1000 - 1 } IN @@b",
            bind_vars={"@b": s.CIRCUIT_BREAKERS},
        )
        assert cb.state().consecutive_failures == 0
        cb.record_failure()
        assert cb.state().consecutive_failures == 1  # counting restarted, like an expired INCR key

    def test_open_state_is_shared_across_instances(self, arango_db: StandardDatabase) -> None:
        clock = FakeClock()
        a = CircuitBreaker("SHARED", failure_threshold=2, reset_seconds=60, clock=clock)
        b = CircuitBreaker("SHARED", failure_threshold=2, reset_seconds=60, clock=clock)
        a.record_failure()
        b.record_failure()
        with pytest.raises(CircuitOpen):
            a.before_call()
        b.reset()
        a.before_call()


class TestSharedStateMigration:
    def test_collections_and_ttl_index(self, arango_db: StandardDatabase) -> None:
        for name in (s.CACHE_ENTRIES, s.METRIC_COUNTERS, s.METRIC_SERIES, s.CIRCUIT_BREAKERS):
            assert arango_db.has_collection(name)
        indexes = {i["name"]: i for i in arango_db.collection(s.CACHE_ENTRIES).indexes()}
        assert indexes["qw_cache_ttl"]["type"] == "ttl"
        assert indexes["qw_cache_ttl"]["fields"] == ["expires_at"]


class TestAtomicThrottles:
    @pytest.fixture
    def tight(self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
        from rest_framework.throttling import SimpleRateThrottle

        rates = {**(SimpleRateThrottle.THROTTLE_RATES or {}), "anon": "5/min", "user": "8/min"}
        monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)

    def test_anonymous_limit_and_retry_after(self, tight: None) -> None:
        from django.test import Client

        client = Client(REMOTE_ADDR="198.51.100.1")
        codes = [client.get("/api/v1/system/freshness").status_code for _ in range(7)]
        assert codes == [200] * 5 + [429] * 2
        throttled = client.get("/api/v1/system/freshness")
        assert throttled.status_code == 429
        assert int(throttled.headers["Retry-After"]) > 0
        other = Client(REMOTE_ADDR="198.51.100.2")
        assert other.get("/api/v1/system/freshness").status_code == 200  # per client

    def test_concurrent_requests_never_exceed_the_limit(self, tight: None) -> None:
        from apps.core.arango import rate_limits
        from apps.core.arango.rate_limits import Check

        check = Check("anon", "203.0.113.77", limit=5, duration=60.0)
        outcomes = _race(lambda: rate_limits.hit([check], time.time())[0].allowed, workers=20)
        assert outcomes.count(True) == 5, outcomes
        assert outcomes.count(False) == 15, outcomes

    def test_each_check_records_independently(self, tight: None) -> None:
        from apps.core.arango import rate_limits
        from apps.core.arango.rate_limits import Check

        small = Check("anon", "x", limit=1, duration=60.0)
        large = Check("user", "x", limit=3, duration=60.0)
        now = time.time()
        assert [o.allowed for o in rate_limits.hit([small, large], now)] == [True, True]
        assert [o.allowed for o in rate_limits.hit([small, large], now + 1)] == [False, True]
        assert [o.allowed for o in rate_limits.hit([small, large], now + 2)] == [False, True]
        assert [o.allowed for o in rate_limits.hit([small, large], now + 3)] == [False, False]
        assert rate_limits.hit([small], now + 61)[0].allowed  # window slid past

    def test_scoped_throttle_uses_view_scope(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from django.test import RequestFactory
        from rest_framework.request import Request
        from rest_framework.throttling import SimpleRateThrottle

        from apps.core.throttling import ScopedRateThrottle

        rates = {**(SimpleRateThrottle.THROTTLE_RATES or {}), "export": "2/hour"}
        monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", rates)

        class View:
            throttle_scope = "export"

        request = Request(RequestFactory().get("/", REMOTE_ADDR="192.0.2.5"))
        results = [ScopedRateThrottle().allow_request(request, View()) for _ in range(3)]
        assert results == [True, True, False]
