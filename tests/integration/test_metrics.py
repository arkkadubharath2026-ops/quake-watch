from __future__ import annotations

from collections.abc import Callable

import pytest
import redis

from apps.core import metrics


class DeadRedis:
    def __getattr__(self, name: str) -> Callable[..., None]:
        def fail(*args: object, **kwargs: object) -> None:
            raise redis.ConnectionError("down")

        return fail


def test_counters_and_series(clean_metrics: None) -> None:
    metrics.incr("things")
    metrics.incr("things", 4)
    for value in range(1, 101):
        metrics.observe("latency", float(value))
    assert metrics.counters()["things"] == 5
    summary = metrics.summarize("latency")
    assert (summary.count, summary.p50, summary.p95, summary.max) == (100, 50, 95, 100)
    assert metrics.series_names() == ["latency"]


def test_series_is_capped(clean_metrics: None) -> None:
    for value in range(metrics.MAX_SAMPLES + 50):
        metrics.observe("capped", float(value))
    assert metrics.summarize("capped").count == metrics.MAX_SAMPLES


def test_reset_clears_namespace(clean_metrics: None) -> None:
    metrics.incr("x")
    metrics.observe("y", 1)
    metrics.reset()
    assert metrics.counters() == {}
    assert metrics.series_names() == []


def test_redis_outage_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics, "get_redis", DeadRedis)
    metrics.incr("x")
    metrics.observe("y", 1.0)
    assert metrics.counters() == {}
    assert metrics.series_names() == []
    assert metrics.summarize("y").count == 0
    assert metrics.ping() is False
