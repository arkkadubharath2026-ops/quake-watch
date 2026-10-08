"""Pure job-queue policy: rate limits, token buckets, schedule ticks, crash allowance."""

from __future__ import annotations

import pytest

from apps.jobs import domain as d


@pytest.mark.parametrize(
    ("spec", "count", "per"), [("30/m", 30, 60.0), ("5/s", 5, 1.0), (" 2 / h ", 2, 3600.0)]
)
def test_rate_limit_parse(spec: str, count: int, per: float) -> None:
    assert d.RateLimit.parse(spec) == d.RateLimit(count, per)


@pytest.mark.parametrize("spec", ["", "30", "0/m", "3/d", "x/m"])
def test_rate_limit_rejects_bad_specs(spec: str) -> None:
    with pytest.raises(ValueError, match="invalid rate limit"):
        d.RateLimit.parse(spec)


def test_token_bucket_starts_full_then_refills() -> None:
    bucket = d.TokenBucket(d.RateLimit(2, 60.0))
    assert bucket.take(0.0) is True
    assert bucket.take(0.0) is True
    assert bucket.take(1.0) is False
    assert bucket.available(29.0) is False
    assert bucket.available(31.0) is True  # one token per 30 s
    assert bucket.take(31.0) is True
    assert bucket.take(31.0) is False


def test_token_bucket_never_exceeds_capacity() -> None:
    bucket = d.TokenBucket(d.RateLimit(1, 1.0))
    assert bucket.take(0.0) is True
    assert bucket.take(1000.0) is True
    assert bucket.take(1000.0) is False


def test_schedule_tick_and_crash_allowance() -> None:
    assert d.schedule_tick(599.9, 300) == 1
    assert d.schedule_tick(600.0, 300) == 2
    assert d.crash_allowance(1) == d.MIN_CRASH_ATTEMPTS
    assert d.crash_allowance(11) == 11


def test_retry_carries_countdown_and_cause() -> None:
    cause = RuntimeError("upstream 503")
    retry = d.Retry(-5, cause)
    assert retry.countdown == 0.0
    assert retry.exc is cause
    assert "upstream 503" in str(retry)


def test_terminal_statuses() -> None:
    assert {d.SUCCEEDED, d.FAILED, d.DEAD, d.EXPIRED} == d.TERMINAL
    assert d.QUEUED not in d.TERMINAL
