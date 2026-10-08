"""HTTP API integration tests: Django test client → DRF → services → real ArangoDB (test DB)."""

from __future__ import annotations

import copy
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from arango.database import StandardDatabase
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from freezegun import freeze_time

from apps.accounts.identity import create_user
from apps.core.arango import catalog
from apps.core.arango import schema as s
from apps.core.arango.query import explain, indexes_used
from apps.core.resilience import CircuitBreaker
from apps.earthquakes.filters import EventFilter
from apps.earthquakes.repository import EventRepository, search_page_aql
from apps.ingestion.adapters.http import ResilientHttpClient
from apps.ingestion.adapters.usgs import UsgsClient
from apps.ingestion.normalizer import NormalizedRecord, normalize_feature, parse_feed
from apps.ingestion.pipeline import IngestionPipeline
from apps.ingestion.repository import RunRepository
from tests.conftest import load_fixture

API = "/api/v1"


SEED_MARKER = "api-test-seed"


def _seed(db: StandardDatabase) -> None:
    for name in ("usgs/all_day.geojson", "usgs/catalog_window.geojson"):
        IngestionPipeline(db).ingest(parse_feed(load_fixture(name)).records)
    db.collection(s.AUDIT_LOG).insert({"_key": SEED_MARKER, "at": "seed"})


@pytest.fixture
def api_db(arango_session_db: StandardDatabase) -> Iterator[StandardDatabase]:
    """Shared read-only dataset: seeded once, re-seeded only if a mutating test wiped it."""
    db = arango_session_db
    if not db.collection(s.AUDIT_LOG).has(SEED_MARKER):
        for spec in s.COLLECTIONS:
            if spec.name != s.SCHEMA_META:
                db.collection(spec.name).truncate()
        _seed(db)
    cache.clear()
    yield db
    cache.clear()


@pytest.fixture
def seeded(arango_db: StandardDatabase) -> Iterator[StandardDatabase]:
    """Fresh seeded dataset for tests that mutate data."""
    cache.clear()
    _seed(arango_db)
    arango_db.collection(s.AUDIT_LOG).delete(SEED_MARKER)  # never reused by read-only tests
    yield arango_db
    cache.clear()


def body(response: Any) -> dict[str, Any]:
    return json.loads(response.content)  # type: ignore[no-any-return]


class TestEventSearch:
    def test_list_paginates_and_describes_query(
        self, client: Client, api_db: StandardDatabase
    ) -> None:
        r = client.get(f"{API}/events", {"min_magnitude": "4.5", "page_size": "5"})
        data = body(r)
        assert r.status_code == 200
        assert len(data["results"]) == 5
        assert data["total"] >= 24
        assert data["total_pages"] == -(-data["total"] // 5)
        assert all(row["magnitude"] >= 4.5 for row in data["results"])
        times = [row["occurred_at"] for row in data["results"]]
        assert times == sorted(times, reverse=True)
        assert data["query"]["filters"]["min_magnitude"] == 4.5
        assert "magnitude 4.5 to any" in data["query"]["summary"]

    def test_second_page_is_disjoint(self, client: Client, api_db: StandardDatabase) -> None:
        p1 = body(client.get(f"{API}/events", {"page_size": "10", "page": "1"}))["results"]
        p2 = body(client.get(f"{API}/events", {"page_size": "10", "page": "2"}))["results"]
        assert not {r["key"] for r in p1} & {r["key"] for r in p2}

    def test_radius_filter(self, client: Client, api_db: StandardDatabase) -> None:
        params = {"lat": "36.5", "lon": "-121.1", "radius_km": "50", "page_size": "100"}
        rows = body(client.get(f"{API}/events", params))["results"]
        assert rows
        assert all(abs(r["latitude"] - 36.5) < 0.5 for r in rows)

    def test_bbox_filter_and_antimeridian(self, client: Client, api_db: StandardDatabase) -> None:
        rows = body(client.get(f"{API}/events", {"bbox": "-30,170,-10,-170", "page_size": "100"}))[
            "results"
        ]
        assert rows
        assert all(r["longitude"] >= 170 or r["longitude"] <= -170 for r in rows)

    def test_text_search_matches_place(self, client: Client, api_db: StandardDatabase) -> None:
        rows = body(client.get(f"{API}/events", {"q": "california", "page_size": "50"}))["results"]
        assert rows
        assert all(r["region_name"] == "California" or "CA" in r["place"] for r in rows)

    def test_sort_by_magnitude(self, client: Client, api_db: StandardDatabase) -> None:
        rows = body(client.get(f"{API}/events", {"sort": "magnitude", "page_size": "10"}))[
            "results"
        ]
        mags = [r["magnitude"] for r in rows]
        assert mags == sorted(mags, reverse=True)

    def test_alert_none_and_status(self, client: Client, api_db: StandardDatabase) -> None:
        rows = body(
            client.get(f"{API}/events", {"alert": "none", "status": "reviewed", "page_size": "50"})
        )["results"]
        assert rows
        assert all(r["alert"] is None and r["status"] == "reviewed" for r in rows)

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"min_magnitude": "abc"}, "min_magnitude"),
            ({"min_magnitude": "7", "max_magnitude": "2"}, "max_magnitude"),
            ({"start": "2026-09-10", "end": "2026-09-01"}, "end"),
            ({"bbox": "1,2,3"}, "bbox"),
            ({"lat": "10", "lon": "20"}, "radius_km"),
            ({"sort": "_key; REMOVE"}, "sort"),
            ({"alert": "purple"}, "alert"),
            ({"page_size": "5000"}, "page_size"),
            ({"page": "0"}, "page"),
            ({"q": "x" * 101}, "q"),
        ],
    )
    def test_validation_errors_use_envelope(
        self, client: Client, api_db: StandardDatabase, params: dict[str, str], field: str
    ) -> None:
        r = client.get(f"{API}/events", params)
        assert r.status_code == 400
        error = body(r)["error"]
        assert error["code"] == "validation_error"
        assert field in error["details"]["fields"]
        assert error["correlation_id"] == r["X-Request-ID"]


class TestMap:
    def test_points_mode_for_small_viewport(self, client: Client, api_db: StandardDatabase) -> None:
        data = body(client.get(f"{API}/events/map", {"bbox": "30,-130,45,-110"}))
        assert data["mode"] == "points"
        key, lat, lon, *_ = data["points"][0]
        assert key.startswith("usgs_")
        assert 30 <= lat <= 45
        assert -130 <= lon <= -110

    def test_clusters_mode_when_dense(
        self, client: Client, api_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.earthquakes.repository.MAP_POINT_LIMIT", 10)
        data = body(client.get(f"{API}/events/map", {"bbox": "-90,-180,90,180"}))
        assert data["mode"] == "clusters"
        assert data["count"] == api_db.collection(s.EVENTS).count()
        assert all(c["count"] >= 1 for c in data["clusters"])

    def test_bbox_required(self, client: Client, api_db: StandardDatabase) -> None:
        assert client.get(f"{API}/events/map").status_code == 400


class TestEventDetail:
    def sample(self, db: StandardDatabase) -> dict[str, Any]:
        return next(iter(db.aql.execute("FOR e IN events SORT e._key LIMIT 1 RETURN e")))  # type: ignore[arg-type]

    def test_detail_by_key_and_raw_id(self, client: Client, api_db: StandardDatabase) -> None:
        event = self.sample(api_db)
        by_key = body(client.get(f"{API}/events/{event['_key']}"))
        by_id = body(client.get(f"{API}/events/{event['source_event_id']}"))
        assert by_key["key"] == by_id["key"] == event["_key"]
        assert set(by_key) >= {"source", "derived", "operational", "products", "links"}
        assert by_key["source"]["magnitude"] == event["magnitude"]
        assert "region_name" in by_key["derived"]
        assert by_key["operational"]["revision_count"] == 1

    def test_historical_id_resolves_to_live_event(
        self, client: Client, seeded: StandardDatabase
    ) -> None:
        feed = json.loads(load_fixture("usgs/all_day.geojson"))
        raw = copy.deepcopy(feed["features"][0])
        old_id = raw["id"]
        raw["id"] = "us7000rekey"
        raw["properties"]["ids"] = f",{old_id},us7000rekey,"
        raw["properties"]["updated"] += 1
        rec = normalize_feature(raw)
        assert isinstance(rec, NormalizedRecord)
        IngestionPipeline(seeded).ingest([rec])

        data = body(client.get(f"{API}/events/{old_id}"))
        assert data["key"] == f"usgs_{old_id}"
        assert data["source"]["source_event_id"] == "us7000rekey"
        assert data["resolved_from"] == old_id

    def test_missing_event_is_404(self, client: Client, api_db: StandardDatabase) -> None:
        r = client.get(f"{API}/events/nope123")
        assert r.status_code == 404
        assert body(r)["error"]["code"] == "not_found"

    def test_revisions_timeline(self, client: Client, seeded: StandardDatabase) -> None:
        feed = json.loads(load_fixture("usgs/all_day.geojson"))
        raw = copy.deepcopy(feed["features"][0])
        raw["properties"].update(mag=raw["properties"]["mag"] + 1, status="reviewed")
        raw["properties"]["updated"] += 5000
        rec = normalize_feature(raw)
        assert isinstance(rec, NormalizedRecord)
        IngestionPipeline(seeded).ingest([rec])

        data = body(client.get(f"{API}/events/{raw['id']}/revisions"))
        assert data["revision_count"] == 2
        assert [t["kind"] for t in data["timeline"]] == ["created", "updated"]
        changed = {c["field"] for c in data["timeline"][1]["changes"]}
        assert changed == {"magnitude", "status"}
        assert {c["field"] for c in data["initial_vs_current"]} == {"magnitude", "status"}
        assert "magnitude" in data["tracked_fields"]

    def test_provenance(self, client: Client, api_db: StandardDatabase) -> None:
        event = self.sample(api_db)
        data = body(client.get(f"{API}/events/{event['_key']}/provenance"))
        assert data["current_payload"]["retained"] is True
        assert data["current_payload"]["payload"]["id"] in event["associated_ids"]
        assert data["payload_hashes"][0]["payload_hash"] == event["payload_hash"]
        assert "USGS" in data["attribution"]

    def test_relationships_graph_and_nearby(self, client: Client, api_db: StandardDatabase) -> None:
        key = next(
            iter(
                api_db.aql.execute(
                    "FOR e IN events FILTER e.derived.region_name == 'California' LIMIT 1 "
                    "RETURN e._key"
                )
            )
        )
        data = body(client.get(f"{API}/events/{key}/relationships"))
        assert data["region"]["name"] == "California"
        assert data["network"]["code"]
        assert data["region_event_count"] > 1
        assert all(e["key"] != key for e in data["same_region"])
        assert "not an aftershock" in data["nearby"]["note"]


class TestEnrichEndpoint:
    def test_requires_authentication(self, client: Client, api_db: StandardDatabase) -> None:
        key = next(iter(api_db.aql.execute("FOR e IN events LIMIT 1 RETURN e._key")))
        assert client.post(f"{API}/events/{key}/enrich").status_code == 403

    def test_requires_csrf_for_session_auth(self, api_db: StandardDatabase) -> None:
        create_user("csrf-user", password="a-long-password-123")
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="csrf-user", password="a-long-password-123")
        key = next(iter(api_db.aql.execute("FOR e IN events LIMIT 1 RETURN e._key")))
        response = strict.post(f"{API}/events/{key}/enrich")
        assert response.status_code == 403
        assert "CSRF" in body(response)["error"]["message"]

    def test_authenticated_request_queues_enrichment(
        self,
        client: Client,
        seeded: StandardDatabase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        detail = load_fixture("usgs/detail_event.geojson")
        breaker = CircuitBreaker("USGS-API", failure_threshold=50, reset_seconds=60)

        def build() -> UsgsClient:
            http = ResilientHttpClient(
                source="USGS",
                breaker=breaker,
                connect_timeout=1,
                read_timeout=1,
                max_retries=0,
                user_agent="t",
                transport=httpx.MockTransport(lambda r: httpx.Response(200, content=detail)),
            )
            return UsgsClient(http, "https://usgs.test")

        monkeypatch.setattr("apps.ingestion.tasks.build_usgs_client", build)
        user = create_user("enricher", password="a-long-password-123")
        client.force_login(user)
        key = "usgs_" + json.loads(detail)["id"]
        response = client.post(f"{API}/events/{key}/enrich")
        assert response.status_code == 202
        assert body(response)["status"] == "queued"
        assert "shakemap" in seeded.collection(s.EVENTS).get(key)["enrichment"]["products"]


class TestAnalytics:
    @pytest.mark.parametrize(
        "path",
        ["summary", "timeseries", "distributions", "breakdowns", "revisions", "latency"],
    )
    def test_endpoints(self, client: Client, api_db: StandardDatabase, path: str) -> None:
        r = client.get(f"{API}/analytics/{path}", {"days": "3650"} if path != "summary" else {})
        assert r.status_code == 200, body(r)

    def test_breakdowns_content(self, client: Client, api_db: StandardDatabase) -> None:
        data = body(client.get(f"{API}/analytics/breakdowns", {"days": "3650"}))
        total = api_db.collection(s.EVENTS).count()
        assert sum(r["count"] for r in data["networks"]) == total
        assert data["regions"][0]["count"] >= data["regions"][-1]["count"]

    def test_significant_by_week_uses_iso_week_year(
        self, client: Client, api_db: StandardDatabase
    ) -> None:
        data = body(client.get(f"{API}/analytics/timeseries", {"days": "3650"}))
        expected: dict[str, int] = {}
        for e in api_db.collection(s.EVENTS).all():
            significant = (e.get("significance") or 0) >= 600 or e.get("alert") or e.get("tsunami")
            if e.get("merged_into") is None and significant:
                iso = datetime.fromisoformat(e["occurred_at"]).isocalendar()
                label = f"{iso.year}-W{iso.week:02d}"
                expected[label] = expected.get(label, 0) + 1
        assert expected, "fixture must contain significant events"
        assert {w["week"]: w["count"] for w in data["significant_by_week"]} == expected

    def test_time_to_reviewed_uses_usgs_clock_not_polling_time(
        self, client: Client, arango_db: StandardDatabase
    ) -> None:
        """A polling gap (reviewed version observed 6 h late) must not inflate the metric."""
        feed = json.loads(load_fixture("usgs/all_day.geojson"))
        raw = copy.deepcopy(
            next(f for f in feed["features"] if f["properties"]["status"] == "automatic")
        )
        updated_ms = raw["properties"]["updated"]
        first_seen = datetime.fromtimestamp(updated_ms / 1000, UTC) + timedelta(minutes=1)
        with freeze_time(first_seen):
            IngestionPipeline(arango_db).ingest([normalize_feature(raw)])  # type: ignore[list-item]
        raw["properties"].update(status="reviewed", updated=updated_ms + 2 * 3600 * 1000)
        with freeze_time(first_seen + timedelta(hours=6)):
            IngestionPipeline(arango_db).ingest([normalize_feature(raw)])  # type: ignore[list-item]
        cache.clear()

        # no frozen clock for the request: DRF throttling needs a real timer
        ttr = body(client.get(f"{API}/analytics/revisions", {"days": "3650"}))["time_to_reviewed"]
        assert ttr["count"] == 1
        assert ttr["first_seen_p50_hours"] == pytest.approx(2 - 1 / 60, abs=1e-6)
        origin = datetime.fromtimestamp(raw["properties"]["time"] / 1000, UTC)
        expected_origin_h = first_seen + timedelta(hours=2) - timedelta(minutes=1) - origin
        assert ttr["origin_p50_hours"] == pytest.approx(
            expected_origin_h.total_seconds() / 3600, abs=1e-6
        )

    @pytest.mark.parametrize("days", ["0", "abc", "99999"])
    def test_invalid_window(self, client: Client, api_db: StandardDatabase, days: str) -> None:
        assert client.get(f"{API}/analytics/timeseries", {"days": days}).status_code == 400


class TestSystemAndOperations:
    def test_freshness_unknown_then_fresh_then_stale(
        self, client: Client, arango_db: StandardDatabase
    ) -> None:
        assert body(client.get(f"{API}/system/freshness"))["status"] == "unknown"
        runs = RunRepository(arango_db)
        run_id = runs.start_run(kind="feed_sync", source="USGS", params={}, correlation_id=None)
        runs.finish_run(run_id, status="succeeded", counts={}, requests=[], duration_ms=1.0)
        assert body(client.get(f"{API}/system/freshness"))["status"] == "fresh"
        arango_db.collection(s.INGESTION_RUNS).update(
            {"_key": run_id, "finished_at": "2020-01-01T00:00:00.000Z"}
        )
        data = body(client.get(f"{API}/system/freshness"))
        assert data["status"] == "stale"
        assert "outdated" in data["message"]

    def test_public_health(self, client: Client, arango_db: StandardDatabase) -> None:
        data = body(client.get(f"{API}/system/health"))
        assert data["database"] == "up"

    @pytest.mark.parametrize("path", ["overview", "runs", "dead-letters", "diagnostics"])
    def test_operations_are_staff_only(
        self, client: Client, arango_db: StandardDatabase, path: str
    ) -> None:
        assert client.get(f"{API}/operations/{path}").status_code == 403
        client.force_login(create_user("plain", password="a-long-password-123"))
        assert client.get(f"{API}/operations/{path}").status_code == 403

    def test_staff_overview_and_diagnostics(self, client: Client, api_db: StandardDatabase) -> None:
        staff = create_user("ops", password="a-long-password-123", is_staff=True)
        client.force_login(staff)
        overview = body(client.get(f"{API}/operations/overview"))
        assert overview["collections"]["events"] == api_db.collection(s.EVENTS).count()
        diagnostics = body(client.get(f"{API}/operations/diagnostics"))
        names = {q["name"] for q in diagnostics["queries"]}
        assert len(names) >= 15
        assert all(q["uses_expected"] for q in diagnostics["queries"]), [
            q for q in diagnostics["queries"] if not q["uses_expected"]
        ]

    def test_runs_filter_validation(self, client: Client, arango_db: StandardDatabase) -> None:
        client.force_login(create_user("o2", password="x-long-password-1", is_staff=True))
        assert client.get(f"{API}/operations/runs", {"kind": "bogus"}).status_code == 400


class TestQueryCatalog:
    def test_every_named_query_runs_and_uses_expected_indexes(
        self, api_db: StandardDatabase
    ) -> None:
        queries = catalog.all_queries()
        assert len(queries) >= 15
        for query in queries:
            binds = query.sample_binds()
            if query.read_only:
                list(api_db.aql.execute(query.aql, bind_vars=binds))  # executes without error
            used = indexes_used(explain(api_db, query.aql, binds))
            assert query.plan_ok(used), (query.name, query.expected_indexes, used)

    def test_list_total_matches_an_independent_count(self, api_db: StandardDatabase) -> None:
        f = EventFilter(min_magnitude=2.5)
        rows, total = EventRepository(api_db).search(f, offset=0, limit=5)
        expected = next(
            api_db.aql.execute(
                "RETURN LENGTH(FOR e IN events FILTER e.merged_into == null "
                "AND e.magnitude >= 2.5 RETURN 1)"
            )
        )
        assert total == expected > 5
        assert len(rows) == 5
        assert [r["occurred_at"] for r in rows] == sorted(
            (r["occurred_at"] for r in rows), reverse=True
        )

    def test_newest_first_list_is_served_in_index_order(self, api_db: StandardDatabase) -> None:
        # Regression (docs/BENCHMARKS.md, tuning history): with the (occurred_at, _key) index the
        # page needs no SORT node, and the total is not computed with fullCount.
        aql, binds = search_page_aql(EventFilter())
        plan = explain(api_db, aql, {**binds, "offset": 0, "limit": 25})
        types = [node["type"] for node in plan["nodes"]]
        assert "SortNode" not in types
        assert "qw_events_occurred_at" in indexes_used(plan)

    def test_catalog_command_passes_on_populated_data_without_warning(
        self, api_db: StandardDatabase
    ) -> None:
        out, err = io.StringIO(), io.StringIO()
        call_command("aql_catalog", stdout=out, stderr=err)
        assert "BAD" not in out.getvalue()
        assert "events collection is empty" not in err.getvalue()

    def test_catalog_command_flags_an_empty_database_instead_of_blaming_queries(
        self, arango_db: StandardDatabase
    ) -> None:
        # On empty collections plan choice is not meaningful (no selectivity statistics); the
        # command must say so, whether or not the optimizer happens to pick the expected index.
        err = io.StringIO()
        failure: CommandError | None = None
        try:
            call_command("aql_catalog", stdout=io.StringIO(), stderr=err)
        except CommandError as exc:
            failure = exc
        assert "events collection is empty" in err.getvalue()
        assert failure is None or "events collection is empty" in str(failure)
