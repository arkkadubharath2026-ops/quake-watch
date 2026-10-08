"""Feed sync, backfill and enrichment services on real ArangoDB with a simulated USGS upstream."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from arango.database import StandardDatabase

from apps.core.arango import schema as s
from apps.core.clock import from_epoch_ms, to_iso
from apps.core.errors import SourceSchemaError, ValidationFailed
from apps.core.locks import job_lock
from apps.core.resilience import CircuitBreaker
from apps.ingestion.adapters.http import ResilientHttpClient, UpstreamRequestFailed
from apps.ingestion.adapters.usgs import UsgsClient
from apps.ingestion.repository import RunRepository
from apps.ingestion.services import (
    BackfillInterrupted,
    BackfillRequest,
    BackfillService,
    EnrichmentService,
    FeedSyncService,
)
from tests.conftest import load_fixture

BASE = "https://usgs.test"
DAY_START = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture
def breaker() -> Iterator[CircuitBreaker]:
    cb = CircuitBreaker("USGS-TEST", failure_threshold=50, reset_seconds=60)
    cb.reset()
    yield cb
    cb.reset()


def usgs(handler: Callable[[httpx.Request], httpx.Response], cb: CircuitBreaker) -> UsgsClient:
    http = ResilientHttpClient(
        source="USGS",
        breaker=cb,
        connect_timeout=1,
        read_timeout=1,
        max_retries=1,
        user_agent="tests",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    return UsgsClient(http, BASE)


class FakeCatalog:
    """Serves count/query for arbitrary windows from the recorded catalog fixture.

    ``split_above``: windows longer than this report a count above ``maxAllowed`` (forces splits).
    ``fail_after_queries``: query calls beyond this number return HTTP 503.
    """

    def __init__(
        self,
        *,
        split_above: timedelta | None = None,
        fail_after_queries: int | None = None,
        undercount: bool = False,
    ) -> None:
        self.doc = json.loads(load_fixture("usgs/catalog_window.geojson"))
        self.undercount = undercount  # count endpoint lags behind the query (events added)
        self.split_above = split_above
        self.fail_after_queries = fail_after_queries
        self.queries: list[tuple[str, str]] = []

    @staticmethod
    def _bounds(request: httpx.Request) -> tuple[datetime, datetime]:
        start = datetime.fromisoformat(request.url.params["starttime"]).replace(tzinfo=UTC)
        end = datetime.fromisoformat(request.url.params["endtime"]).replace(tzinfo=UTC)
        return start, end

    def __call__(self, request: httpx.Request) -> httpx.Response:
        start, end = self._bounds(request)
        features = [
            f for f in self.doc["features"] if start <= from_epoch_ms(f["properties"]["time"]) < end
        ]
        if request.url.path.endswith("/count"):
            too_big = self.split_above is not None and end - start > self.split_above
            count = 10**6 if too_big else len(features)
            if self.undercount:
                count = min(count, 1)
            return httpx.Response(200, json={"count": count, "maxAllowed": 20000})
        self.queries.append((request.url.params["starttime"], request.url.params["endtime"]))
        if self.fail_after_queries is not None and len(self.queries) > self.fail_after_queries:
            return httpx.Response(503)
        body = {**self.doc, "features": features}
        body["metadata"] = {**self.doc["metadata"], "count": len(features)}
        return httpx.Response(200, json=body)


class TestFeedSync:
    def test_successful_sync_records_run_and_provenance(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        body = load_fixture("usgs/all_day.geojson")
        client = usgs(lambda r: httpx.Response(200, content=body), breaker)
        result = FeedSyncService(arango_db, client).run("all_day")

        assert result.status == "succeeded"
        n = json.loads(body)["metadata"]["count"]
        assert result.counts["inserted"] == n
        run = RunRepository(arango_db).get_run(result.run_id)
        assert run is not None
        assert run["status"] == "succeeded"
        assert run["kind"] == "feed_sync"
        (request,) = run["requests"]
        assert request["url"].endswith("/summary/all_day.geojson")
        assert request["response_sha256"]
        assert request["response_bytes"] == len(body)
        assert run["source_generated_at"].endswith("Z")
        assert arango_db.collection(s.EVENTS).count() == n

    def test_upstream_outage_marks_run_failed_and_keeps_data(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        result = FeedSyncService(arango_db, usgs(lambda r: httpx.Response(503), breaker)).run(
            "all_day"
        )
        assert result.status == "failed"
        run = RunRepository(arango_db).get_run(result.run_id)
        assert run is not None
        assert run["error"]["transient"] is True
        assert run["requests"][0]["attempts"] == 2
        assert arango_db.collection(s.EVENTS).count() == 0

    def test_malformed_payload_is_schema_failure(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        client = usgs(lambda r: httpx.Response(200, content=b"<html>oops</html>"), breaker)
        result = FeedSyncService(arango_db, client).run("all_day")
        run = RunRepository(arango_db).get_run(result.run_id)
        assert result.status == "failed"
        assert run is not None
        assert run["error"]["type"] == "SourceSchemaError"

    def test_open_circuit_skips_without_calling_upstream(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200)

        result = FeedSyncService(arango_db, usgs(handler, breaker)).run("all_day")
        assert result.status == "skipped"
        assert calls == []


class TestBackfill:
    def request(self, **overrides: Any) -> BackfillRequest:
        values: dict[str, Any] = {
            "start": DAY_START,
            "end": DAY_START + timedelta(days=1),
            "min_magnitude": 4.5,
            "window_days": 1,
            "requested_by": "test",
        }
        values.update(overrides)
        return BackfillRequest(**values)

    def test_job_runs_to_completion_with_checkpoints(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        catalog = FakeCatalog()
        service = BackfillService(arango_db, usgs(catalog, breaker))
        job_id = service.create_job(self.request(end=DAY_START + timedelta(days=3), window_days=1))
        job = service.run_job(job_id)

        assert job["status"] == "completed"
        assert job["windows_completed"] == 3
        assert job["next_window_start"] == to_iso(DAY_START + timedelta(days=3))
        expected = len(catalog.doc["features"])
        assert job["counts"]["inserted"] == expected
        assert arango_db.collection(s.EVENTS).count() == expected
        events = list(arango_db.collection(s.EVENTS).all())
        assert {e["derived"]["first_seen_via"] for e in events} == {"backfill"}

    def test_oversized_windows_are_split(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        catalog = FakeCatalog(split_above=timedelta(hours=6))
        service = BackfillService(arango_db, usgs(catalog, breaker))
        job = service.run_job(service.create_job(self.request()))
        assert job["status"] == "completed"
        assert len(catalog.queries) == 4  # 24 h split into 4 windows of 6 h
        assert arango_db.collection(s.EVENTS).count() == len(catalog.doc["features"])

    def test_window_that_fills_the_query_limit_is_split_not_truncated(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.ingestion.services.CATALOG_MAX_LIMIT", 8)
        catalog = FakeCatalog(undercount=True)
        service = BackfillService(arango_db, usgs(catalog, breaker))
        job = service.run_job(service.create_job(self.request()))
        assert job["status"] == "completed"
        assert arango_db.collection(s.EVENTS).count() == len(catalog.doc["features"])
        split_runs = list(
            arango_db.aql.execute("FOR r IN ingestion_runs FILTER r.status == 'split' RETURN r")
        )
        assert split_runs, "truncated windows must be recorded as split, not ingested"

    def test_transient_failure_checkpoints_and_resumes_without_duplicates(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        failing = FakeCatalog(fail_after_queries=0)  # Aug 31 has no events: no query
        service = BackfillService(arango_db, usgs(failing, breaker))
        job_id = service.create_job(
            self.request(start=DAY_START - timedelta(days=1), window_days=1)
        )
        with pytest.raises(BackfillInterrupted):
            service.run_job(job_id)
        job = RunRepository(arango_db).get_backfill_job(job_id)
        assert job is not None
        assert job["status"] == "pending"
        assert job["next_window_start"] == to_iso(DAY_START)  # first window committed
        assert job["last_error"]["transient"] is True

        healthy = BackfillService(arango_db, usgs(FakeCatalog(), breaker))
        done = healthy.run_job(job_id)
        assert done["status"] == "completed"
        assert arango_db.collection(s.EVENTS).count() == len(failing.doc["features"])
        assert arango_db.collection(s.EVENT_REVISIONS).count() == len(failing.doc["features"])

    @pytest.mark.parametrize(
        "overrides",
        [
            {"end": DAY_START - timedelta(days=1)},
            {"end": datetime.now(UTC) + timedelta(days=2)},
            {"start": DAY_START - timedelta(days=5000)},
            {"window_days": 0},
            {"min_magnitude": 42.0},
        ],
    )
    def test_invalid_requests_rejected(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker, overrides: dict[str, Any]
    ) -> None:
        service = BackfillService(arango_db, usgs(FakeCatalog(), breaker))
        with pytest.raises(ValidationFailed):
            service.create_job(self.request(**overrides))

    def test_stalled_running_job_is_recovered(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        service = BackfillService(arango_db, usgs(FakeCatalog(), breaker))
        job_id = service.create_job(self.request())
        RunRepository(arango_db).update_backfill_job(
            job_id, {"status": "running", "heartbeat_at": "2020-01-01T00:00:00.000Z"}
        )
        assert service.recover_stalled() == [job_id]
        job = RunRepository(arango_db).get_backfill_job(job_id)
        assert job is not None
        assert job["status"] == "pending"


class TestEnrichment:
    def seed(self, db: StandardDatabase, breaker: CircuitBreaker) -> str:
        body = load_fixture("usgs/catalog_window.geojson")
        FeedSyncService(db, usgs(lambda r: httpx.Response(200, content=body), breaker)).run(
            "all_day"
        )
        detail = json.loads(load_fixture("usgs/detail_event.geojson"))
        return f"usgs_{detail['id']}"

    def test_enrichment_adds_products_without_touching_source_fields(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        key = self.seed(arango_db, breaker)
        before = arango_db.collection(s.EVENTS).get(key)
        detail = load_fixture("usgs/detail_event.geojson")
        service = EnrichmentService(
            arango_db, usgs(lambda r: httpx.Response(200, content=detail), breaker)
        )
        enrichment = service.enrich(key)

        assert {"shakemap", "losspager", "origin"} <= set(enrichment["products"])
        assert "maxmmi" in enrichment["products"]["shakemap"]["properties"]
        after = arango_db.collection(s.EVENTS).get(key)
        for field in ("magnitude", "place", "status", "payload_hash", "revision_count"):
            assert after[field] == before[field]
        assert after["enrichment"]["last_error"] is None

    def test_enrichment_failure_is_recorded_and_isolated(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        key = self.seed(arango_db, breaker)
        service = EnrichmentService(arango_db, usgs(lambda r: httpx.Response(500), breaker))
        with pytest.raises(UpstreamRequestFailed):
            service.enrich(key)
        event = arango_db.collection(s.EVENTS).get(key)
        assert "HTTP 500" in event["enrichment"]["last_error"]
        assert event["magnitude"] is not None

    def test_detail_schema_violation(
        self, arango_db: StandardDatabase, breaker: CircuitBreaker
    ) -> None:
        key = self.seed(arango_db, breaker)
        service = EnrichmentService(
            arango_db, usgs(lambda r: httpx.Response(200, json={"type": "nope"}), breaker)
        )
        with pytest.raises(SourceSchemaError):
            service.enrich(key)


class TestOperationalRecovery:
    def test_stale_running_runs_are_abandoned(self, arango_db: StandardDatabase) -> None:
        runs = RunRepository(arango_db)
        run_id = runs.start_run(kind="feed_sync", source="USGS", params={}, correlation_id=None)
        arango_db.collection(s.INGESTION_RUNS).update(
            {"_key": run_id, "started_at": "2020-01-01T00:00:00.000Z"}
        )
        assert runs.abandon_stale_runs(older_than=timedelta(hours=1)) == 1
        run = runs.get_run(run_id)
        assert run is not None
        assert run["status"] == "abandoned"

    def test_job_lock_is_exclusive(self, arango_db: StandardDatabase) -> None:
        # Leases live in ArangoDB (job_leases) since Phase 1a, so the test needs the database.
        with (
            job_lock("test-exclusive", ttl_seconds=30) as first,
            job_lock("test-exclusive", ttl_seconds=30) as second,
        ):
            assert first is True
            assert second is False
        with job_lock("test-exclusive", ttl_seconds=30) as again:
            assert again is True
