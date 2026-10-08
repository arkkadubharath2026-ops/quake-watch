"""Operational metrics on the real ArangoDB store (buffered per process, flushed atomically)."""

from __future__ import annotations

import multiprocessing

import pytest
from arango.database import StandardDatabase

from apps.core import metrics
from apps.core.arango import metrics_store


def test_counters_and_series(clean_metrics: None) -> None:
    metrics.incr("things")
    metrics.incr("things", 4)
    for value in range(1, 101):
        metrics.observe("latency", float(value))
    assert metrics.counters()["things"] == 5
    summary = metrics.summarize("latency")
    assert (summary.count, summary.p50, summary.p95, summary.max) == (100, 50, 95, 100)
    assert metrics.series_names() == ["latency"]


def test_series_is_capped_keeping_the_newest(clean_metrics: None) -> None:
    for value in range(metrics.MAX_SAMPLES + 50):
        metrics.observe("capped", float(value))
    summary = metrics.summarize("capped")
    assert summary.count == metrics.MAX_SAMPLES
    assert summary.max == metrics.MAX_SAMPLES + 49  # the oldest 50 were dropped, not the newest
    assert min(metrics_store.samples("capped")) == 50


def test_reset_clears_namespace(clean_metrics: None) -> None:
    metrics.incr("x")
    metrics.observe("y", 1)
    metrics.reset()
    assert metrics.counters() == {}
    assert metrics.series_names() == []


def test_pending_threshold_flushes_without_a_read(clean_metrics: None) -> None:
    for value in range(metrics.FLUSH_MAX_PENDING):
        metrics.observe("hot", float(value))
    assert len(metrics_store.samples("hot")) == metrics.FLUSH_MAX_PENDING  # store read, no flush


def test_store_outage_never_raises_and_keeps_buffered_data(
    clean_metrics: None, dead_arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as patched:
        patched.setattr(metrics_store, "get_db", lambda: dead_arango_db)
        metrics.incr("x")
        metrics.observe("y", 1.0)
        assert metrics.flush() is False
        assert metrics.counters() == {}
        assert metrics.series_names() == []
        assert metrics.summarize("y").count == 0
        assert metrics.ping() is False
    # Store back: the deltas recorded during the outage were kept and now land exactly once.
    assert metrics.ping() is True
    assert metrics.counters()["x"] == 1
    assert metrics.summarize("y").count == 1


def _child_increments(n: int) -> None:
    for _ in range(n):
        metrics.incr("shared")
        metrics.observe("shared_latency", 1.0)
    metrics.flush()  # multiprocessing children leave via os._exit, which skips atexit


def test_concurrent_processes_add_up_exactly_and_forks_do_not_duplicate(
    clean_metrics: None,
) -> None:
    metrics.incr("parent_only")  # buffered in the parent when the children fork
    ctx = multiprocessing.get_context("fork")
    children = [ctx.Process(target=_child_increments, args=(250,)) for _ in range(4)]
    for child in children:
        child.start()
    for child in children:
        child.join(timeout=120)
    assert [c.exitcode for c in children] == [0] * len(children)
    counters = metrics.counters()
    assert counters["shared"] == 1000
    assert counters["parent_only"] == 1  # not re-flushed by any child
    assert metrics.summarize("shared_latency").count == 1000
