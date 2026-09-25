"""The index benchmark harness (manage.py arango_benchmark) against a real, disposable database."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.arango import benchmark as bench
from apps.core.arango.client import database_name, drop_database, get_client
from apps.core.management.commands.arango_benchmark import render, workloads
from config.env import get_settings

NEWEST = datetime(2026, 9, 25, 12, tzinfo=UTC)


def test_synthetic_catalogue_is_deterministic_and_shaped_like_usgs() -> None:
    first = list(bench.synthetic_catalogue(4000, NEWEST))
    assert first == list(bench.synthetic_catalogue(4000, NEWEST))  # seeded: reproducible
    events = [event for event, _ in first]
    mags = [e["magnitude"] for e in events]
    assert 0.10 < sum(m >= 2.5 for m in mags) / len(mags) < 0.20
    assert 0.02 < sum(m >= 4.5 for m in mags) / len(mags) < 0.06
    for event, revisions in first[:200]:
        assert [r["revision_number"] for r in revisions] == list(range(1, len(revisions) + 1))
        assert event["revision_count"] == len(revisions)
        assert event["coordinates"] == [event["longitude"], event["latitude"]]


def test_command_measures_both_index_states_and_cleans_up() -> None:
    out = StringIO()
    call_command("arango_benchmark", sizes="300", runs=2, stdout=out)
    log = out.getvalue()
    assert "seeded 300 events" in log
    assert "dropped indexes: qw_events_geo" in log
    for workload in workloads():
        assert f"with    {workload.name}" in log
        assert f"without {workload.name}" in log
    cfg = get_settings()
    system = get_client().db(
        "_system", username=cfg.arango_user, password=cfg.arango_password.get_secret_value()
    )
    assert not system.has_database(f"{database_name()}_bench_test")


def test_indexed_plans_use_their_indexes() -> None:
    db = bench.prepare_database(f"{database_name()}_bench_test")
    try:
        keys = bench.seed(db, 400, NEWEST)
        ctx = bench.BenchContext(newest=NEWEST, rng=random.Random(1), event_keys=keys)
        expected = {
            "event_list_filtered": "qw_events_occurred_at",
            "event_list_latest": "qw_events_occurred_at",
            "geo_radius": "qw_events_geo",
            "analytics_magnitude_histogram": "qw_events_occurred_at",
            "revision_lookup": "qw_revisions_event_rev",
        }
        for workload in workloads():
            timing = bench.measure(db, workload, ctx, size=400, indexed=True, runs=1, warmup=0)
            assert expected[workload.name] in timing.indexes, (workload.name, timing.indexes)
            assert timing.scanned_full == 0, workload.name
    finally:
        drop_database(f"{database_name()}_bench_test")


def test_render_reports_speedup_and_history() -> None:
    rows = [
        bench.Timing("revision_lookup", 1000, True, 3, 1.0, 2.0, 1.2, 4, 0, 4, ["qw_x"]),
        bench.Timing("revision_lookup", 1000, False, 3, 8.0, 10.0, 8.5, 4, 900, 0, []),
    ]
    env = {"generated_at": "t", "arangodb": "3.12", "python": "3.12", "os": "x", "cpus": 1,
           "runs_per_case": 3}  # fmt: skip
    text = render(rows, env)
    assert "| `revision_lookup` | 1,000 | 1.0 / 2.0 | 8.0 / 10.0 | 5.0x |" in text
    assert "## Tuning history" in text


def test_rejects_bad_sizes() -> None:
    with pytest.raises(CommandError):
        call_command("arango_benchmark", sizes="ten")
    with pytest.raises(ValueError, match="_test"):
        bench.prepare_database("quakewatch")
