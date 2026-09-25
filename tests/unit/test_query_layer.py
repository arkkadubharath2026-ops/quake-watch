from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from apps.analytics.services import parse_days
from apps.core.errors import ValidationFailed
from apps.core.resilience import BreakerState
from apps.earthquakes.filters import EventFilter
from apps.earthquakes.repository import compile_filter, search_aql
from apps.earthquakes.services import present_event, safe_usgs_url
from apps.operations.freshness import FreshnessService, classify


class TestEventFilter:
    def test_canonical_is_deterministic_and_order_independent(self) -> None:
        a = EventFilter.from_params(
            {"network": "us,ak", "alert": "red,green", "min_magnitude": "4"}
        )
        b = EventFilter.from_params(
            {"alert": "green,red", "min_magnitude": "4.0", "network": "ak,us"}
        )
        assert a.canonical() == b.canonical()
        assert list(a.canonical()) == sorted(a.canonical())

    def test_canonical_round_trips(self) -> None:
        original = EventFilter.from_params(
            {
                "start": "2026-09-01T00:00:00Z",
                "end": "2026-09-02",
                "lat": "17.385",
                "lon": "78.4867",
                "radius_km": "300",
                "tsunami": "false",
                "q": "hyderabad",
                "sort": "magnitude",
                "direction": "asc",
            }
        )
        again = EventFilter.from_params(original.canonical())
        assert again == original
        assert again.canonical() == original.canonical()

    def test_naive_dates_are_utc(self) -> None:
        f = EventFilter.from_params({"start": "2026-09-01"})
        assert f.start == datetime(2026, 9, 1, tzinfo=UTC)

    def test_summary_is_human_readable(self) -> None:
        f = EventFilter.from_params(
            {"min_magnitude": "5.5", "lat": "17.4", "lon": "78.5", "radius_km": "300"}
        )
        summary = f.summary()
        assert "magnitude 5.5 to any" in summary
        assert "within 300 km of (17.4, 78.5)" in summary
        assert EventFilter().summary().startswith("all events")

    def test_multiple_errors_reported_together(self) -> None:
        with pytest.raises(ValidationFailed) as exc_info:
            EventFilter.from_params({"min_magnitude": "x", "sort": "bad", "tsunami": "maybe"})
        assert set(exc_info.value.details["fields"]) == {"min_magnitude", "sort", "tsunami"}

    def test_bbox_and_radius_are_exclusive(self) -> None:
        with pytest.raises(ValidationFailed, match="Invalid"):
            EventFilter.from_params(
                {"bbox": "0,0,10,10", "lat": "5", "lon": "5", "radius_km": "10"}
            )

    @pytest.mark.parametrize("value", ["us;DROP", "a" * 5 + "'", "x" * 1 + "/"])
    def test_free_list_values_must_be_alphanumeric(self, value: str) -> None:
        with pytest.raises(ValidationFailed):
            EventFilter.from_params({"network": value})


class TestSearchCompilation:
    def test_all_values_are_bound_never_inlined(self) -> None:
        f = EventFilter.from_params(
            {"q": 'evil" OR 1==1 //', "network": "us", "min_magnitude": "3", "sort": "depth"}
        )
        aql, binds = search_aql(f)
        assert 'evil"' not in aql
        assert binds["q"] == 'evil" OR 1==1 //'
        assert "SORT e.depth_km DESC" in aql
        assert "e.merged_into == null" in aql

    def test_alert_none_matches_null(self) -> None:
        compiled = compile_filter(EventFilter.from_params({"alert": "none,red"}))
        assert "(e.alert IN @alerts OR e.alert == null)" in compiled.filters
        assert compiled.binds["alerts"] == ["red"]

    def test_antimeridian_bbox_uses_two_polygons(self) -> None:
        compiled = compile_filter(EventFilter.from_params({"bbox": "-30,170,-10,-170"}))
        assert {"bbox0", "bbox1"} <= set(compiled.binds)


class TestFreshness:
    @pytest.mark.parametrize(
        ("minutes", "expected"),
        [(None, "unknown"), (0, "fresh"), (20, "fresh"), (21, "degraded"), (121, "stale")],
    )
    def test_classify(self, minutes: float | None, expected: str) -> None:
        assert classify(minutes, degraded=20, stale=120) == expected

    def test_open_circuit_is_explained(self) -> None:
        now = datetime(2026, 9, 25, 12, tzinfo=UTC)

        class Runs:
            def latest_run(
                self, kind: str, *, statuses: list[str] | None = None
            ) -> dict[str, Any] | None:
                finished = (now - timedelta(minutes=45)).isoformat().replace("+00:00", "Z")
                return {"finished_at": finished, "status": "failed", "started_at": finished}

        service = FreshnessService(
            Runs(),
            lambda: BreakerState("USGS", "open", 5, 0.0),
            degraded_minutes=20,
            stale_minutes=120,
            clock=lambda: now,
        )
        result = service.current()
        assert result.status == "degraded"
        assert result.minutes_since_success == 45.0
        assert "retries are paused" in result.message


class TestPresentation:
    def test_groups_source_derived_operational(self) -> None:
        doc = {
            "_key": "usgs_x",
            "source": "USGS",
            "source_event_id": "x",
            "magnitude": 5.26,
            "place": "Somewhere",
            "products": ["shakemap", "origin"],
            "derived": {"region_name": "Somewhere"},
            "revision_count": 2,
            "event_page_url": "https://earthquake.usgs.gov/x",
        }
        presented = present_event(doc)
        assert presented["title"] == "M 5.3 — Somewhere"
        assert presented["source"]["magnitude"] == 5.26
        assert "revision_count" not in presented["source"]
        assert presented["operational"]["revision_count"] == 2
        assert presented["derived"]["region_name"] == "Somewhere"
        shakemap = next(p for p in presented["products"] if p["type"] == "shakemap")
        assert shakemap["available"] is True
        assert next(p for p in presented["products"] if p["type"] == "dyfi")["available"] is False


@pytest.mark.parametrize(("raw", "expected"), [(None, 30), ("", 30), ("7", 7), ("3660", 3660)])
def test_parse_days(raw: str | None, expected: int) -> None:
    assert parse_days(raw) == expected


class TestSafeUsgsUrl:
    @pytest.mark.parametrize(
        "value",
        [
            "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abcd",
            "https://usgs.gov/x",
        ],
    )
    def test_accepts_https_usgs_hosts(self, value: str) -> None:
        assert safe_usgs_url(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "http://earthquake.usgs.gov/insecure",
            "https://earthquake.usgs.gov.evil.example/x",
            "https://evilusgs.gov/x",
            "//earthquake.usgs.gov/x",
            "data:text/html,<script>alert(1)</script>",
            "",
            None,
            42,
        ],
    )
    def test_rejects_everything_else(self, value: object) -> None:
        assert safe_usgs_url(value) is None
