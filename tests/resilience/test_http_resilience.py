"""Resilience tests for the upstream HTTP adapter and the shared circuit breaker.

Transport behaviour is simulated with ``httpx.MockTransport``; the circuit breaker uses the real
ArangoDB test database. Sleeps are captured instead of performed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx
import pytest
from arango.database import StandardDatabase

from apps.core.arango import breaker_store
from apps.core.errors import CircuitOpen
from apps.core.resilience import CircuitBreaker, backoff_delay
from apps.ingestion.adapters.http import ResilientHttpClient, UpstreamRequestFailed
from apps.ingestion.adapters.usgs import UsgsClient
from apps.ingestion.normalizer import parse_feed
from tests.conftest import load_fixture

URL = "https://upstream.test/feed.geojson"


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def breaker(clock: FakeClock, arango_session_db: StandardDatabase) -> Iterator[CircuitBreaker]:
    cb = CircuitBreaker("TEST", failure_threshold=3, reset_seconds=60, clock=clock)
    cb.reset()
    yield cb
    cb.reset()


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    breaker: CircuitBreaker,
    sleeps: list[float],
    max_retries: int = 3,
) -> ResilientHttpClient:
    return ResilientHttpClient(
        source="TEST",
        breaker=breaker,
        connect_timeout=1,
        read_timeout=1,
        max_retries=max_retries,
        user_agent="tests",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )


def sequence(*responses: httpx.Response | Exception) -> Callable[[httpx.Request], httpx.Response]:
    queue = list(responses)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


class TestBackoff:
    def test_exponential_ceiling_with_full_jitter(self) -> None:
        upper = lambda lo, hi: hi  # noqa: E731 - deterministic "max jitter"
        assert [backoff_delay(a, base=1, cap=60, rng=upper) for a in (1, 2, 3, 4)] == [1, 2, 4, 8]
        assert backoff_delay(10, base=1, cap=60, rng=upper) == 60

    def test_jitter_is_bounded(self) -> None:
        for attempt in range(1, 8):
            assert 0 <= backoff_delay(attempt, base=1, cap=30) <= min(30, 2 ** (attempt - 1))

    def test_retry_after_is_honoured_and_capped(self) -> None:
        assert backoff_delay(1, retry_after=7) == 7
        assert backoff_delay(1, retry_after=500, cap=60) == 60


class TestRetries:
    def test_success_first_try(self, breaker: CircuitBreaker) -> None:
        sleeps: list[float] = []
        client = make_client(sequence(httpx.Response(200, content=b"{}")), breaker, sleeps)
        result = client.get(URL, {"a": "1"})
        assert result.body == b"{}"
        assert result.request.attempts == 1
        assert result.request.response_sha256 is not None
        assert result.request.params == {"a": "1"}
        assert sleeps == []

    def test_transient_5xx_then_success(self, breaker: CircuitBreaker) -> None:
        sleeps: list[float] = []
        handler = sequence(
            httpx.Response(503), httpx.Response(502), httpx.Response(200, content=b"ok")
        )
        result = make_client(handler, breaker, sleeps).get(URL)
        assert result.request.attempts == 3
        assert len(sleeps) == 2
        assert breaker.state().consecutive_failures == 0

    def test_timeouts_exhaust_retries(self, breaker: CircuitBreaker) -> None:
        sleeps: list[float] = []
        handler = sequence(httpx.ReadTimeout("slow"))
        with pytest.raises(UpstreamRequestFailed) as exc_info:
            make_client(handler, breaker, sleeps, max_retries=2).get(URL)
        assert exc_info.value.transient is True
        assert exc_info.value.request.attempts == 3
        assert len(handler.calls) == 3  # type: ignore[attr-defined]
        assert breaker.state().consecutive_failures == 1

    def test_non_transient_4xx_fails_fast_without_tripping_breaker(
        self, breaker: CircuitBreaker
    ) -> None:
        sleeps: list[float] = []
        handler = sequence(httpx.Response(404))
        with pytest.raises(UpstreamRequestFailed) as exc_info:
            make_client(handler, breaker, sleeps).get(URL)
        assert exc_info.value.transient is False
        assert exc_info.value.status_code == 404
        assert len(handler.calls) == 1  # type: ignore[attr-defined]
        assert sleeps == []
        assert breaker.state().consecutive_failures == 0

    def test_429_retry_after_is_used(self, breaker: CircuitBreaker) -> None:
        sleeps: list[float] = []
        handler = sequence(
            httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, content=b"x")
        )
        make_client(handler, breaker, sleeps).get(URL)
        assert sleeps == [7.0]

    def test_connection_error_is_transient(self, breaker: CircuitBreaker) -> None:
        sleeps: list[float] = []
        handler = sequence(httpx.ConnectError("refused"), httpx.Response(200, content=b"x"))
        assert make_client(handler, breaker, sleeps).get(URL).request.attempts == 2


class TestCircuitBreaker:
    def test_opens_after_threshold_and_blocks_calls(
        self, breaker: CircuitBreaker, clock: FakeClock
    ) -> None:
        sleeps: list[float] = []
        failing = sequence(httpx.Response(500))
        client = make_client(failing, breaker, sleeps, max_retries=0)
        for _ in range(3):
            with pytest.raises(UpstreamRequestFailed):
                client.get(URL)
        assert breaker.state().status == "open"

        calls_before = len(failing.calls)  # type: ignore[attr-defined]
        with pytest.raises(CircuitOpen):
            client.get(URL)
        assert len(failing.calls) == calls_before  # type: ignore[attr-defined]  # no upstream call

    def test_half_open_probe_success_closes(
        self, breaker: CircuitBreaker, clock: FakeClock
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        clock.now += 61
        assert breaker.state().status == "half_open"
        breaker.before_call()  # this caller wins the probe
        with pytest.raises(CircuitOpen):
            breaker.before_call()  # concurrent callers are still rejected
        breaker.record_success()
        assert breaker.state().status == "closed"
        breaker.before_call()

    def test_half_open_probe_failure_reopens(
        self, breaker: CircuitBreaker, clock: FakeClock
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        clock.now += 61
        breaker.before_call()
        breaker.record_failure()
        assert breaker.state().status == "open"

    def test_store_outage_fails_open(
        self, dead_arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(breaker_store, "get_db", lambda: dead_arango_db)
        cb = CircuitBreaker("OUTAGE", failure_threshold=1, reset_seconds=60)
        cb.before_call()  # must not raise: breaker fails open
        cb.record_failure()
        cb.record_success()
        assert cb.state().status == "unknown"


class TestUsgsAdapter:
    def test_summary_feed_end_to_end_through_adapter(self, breaker: CircuitBreaker) -> None:
        body = load_fixture("usgs/all_day.geojson")
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, content=body)

        usgs = UsgsClient(make_client(handler, breaker, []), "https://earthquake.usgs.gov")
        result = usgs.summary_feed("all_day")
        assert seen == ["https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"]
        assert len(parse_feed(result.body).records) > 0

    @pytest.mark.parametrize("feed", ["../../etc/passwd", "all_year", "ALL_DAY", ""])
    def test_feed_name_is_allow_listed(self, breaker: CircuitBreaker, feed: str) -> None:
        usgs = UsgsClient(make_client(sequence(httpx.Response(200)), breaker, []), "https://x")
        with pytest.raises(Exception, match="unknown USGS summary feed"):
            usgs.summary_feed(feed)

    @pytest.mark.parametrize("event_id", ["../x", "a/b", "x" * 65, "id?q=1"])
    def test_detail_event_id_is_validated(self, breaker: CircuitBreaker, event_id: str) -> None:
        usgs = UsgsClient(make_client(sequence(httpx.Response(200)), breaker, []), "https://x")
        with pytest.raises(Exception, match="invalid event id"):
            usgs.detail(event_id)
