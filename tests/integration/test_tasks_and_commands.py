"""Job tasks (eager) and management commands on real ArangoDB, simulated USGS upstream."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import httpx
import pytest
from arango.database import StandardDatabase
from django.core.management import CommandError, call_command

from apps.core.arango import schema as s
from apps.core.locks import job_lock
from apps.core.resilience import CircuitBreaker
from apps.ingestion import tasks
from apps.ingestion.adapters.http import ResilientHttpClient
from apps.ingestion.adapters.usgs import UsgsClient
from apps.ingestion.repository import RunRepository
from apps.ingestion.services import BackfillRequest, BackfillService
from tests.conftest import load_fixture
from tests.integration.test_ingestion_services import FakeCatalog

Handler = Callable[[httpx.Request], httpx.Response]


def upstream(extra: Handler | None = None) -> Handler:
    feed = load_fixture("usgs/catalog_window.geojson")
    detail = load_fixture("usgs/detail_event.geojson")
    catalog = FakeCatalog()

    def handler(request: httpx.Request) -> httpx.Response:
        if extra is not None:
            response = extra(request)
            if response is not None:
                return response
        path = request.url.path
        if "/summary/" in path:
            return httpx.Response(200, content=feed)
        if "/detail/" in path:
            return httpx.Response(200, content=detail)
        return catalog(request)

    return handler


@pytest.fixture
def fake_usgs(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Handler], None]]:
    breaker = CircuitBreaker("USGS-TASKS", failure_threshold=100, reset_seconds=60)
    breaker.reset()

    def install(handler: Handler) -> None:
        def build() -> UsgsClient:
            http = ResilientHttpClient(
                source="USGS",
                breaker=breaker,
                connect_timeout=1,
                read_timeout=1,
                max_retries=0,
                user_agent="tests",
                transport=httpx.MockTransport(handler),
                sleep=lambda _: None,
            )
            return UsgsClient(http, "https://usgs.test")

        for module in (
            "apps.ingestion.tasks",
            "apps.ingestion.management.commands.sync_feed",
            "apps.ingestion.management.commands.backfill",
            "apps.ingestion.management.commands.enrich_event",
        ):
            monkeypatch.setattr(f"{module}.build_usgs_client", build)

    install(upstream())
    yield install
    breaker.reset()


DETAIL_KEY = "usgs_" + json.loads(load_fixture("usgs/detail_event.geojson"))["id"]


class TestSyncTask:
    def test_sync_ingests_and_enriches_important_events(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        result = tasks.sync_feed("all_day")
        assert result["status"] == "succeeded"
        assert result["counts"]["inserted"] > 0
        enrichment_runs = list(
            arango_db.aql.execute(
                "FOR r IN ingestion_runs FILTER r.kind == 'detail_enrichment' RETURN r"
            )
        )
        assert enrichment_runs, "important events should be enriched after sync"

    def test_overlapping_sync_is_skipped(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        with job_lock("sync:all_day", ttl_seconds=30):
            assert tasks.sync_feed("all_day") == {"status": "skipped_locked"}
        assert arango_db.collection(s.INGESTION_RUNS).count() == 0


class TestBackfillTask:
    def test_backfill_task_completes_job(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        job_id = BackfillService(arango_db, UsgsClient.__new__(UsgsClient)).create_job(
            BackfillRequest(start, start + timedelta(days=1), 4.5, 1, "test")
        )
        result = tasks.run_backfill.apply(args=[job_id]).get()
        assert result["status"] == "completed"
        assert arango_db.collection(s.EVENTS).count() > 0

    def test_backfill_task_retries_transient_failure_and_keeps_checkpoint(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        fake_usgs(upstream(lambda r: httpx.Response(503) if "/query" in r.url.path else None))
        start = datetime(2026, 9, 1, tzinfo=UTC)
        job_id = BackfillService(arango_db, UsgsClient.__new__(UsgsClient)).create_job(
            BackfillRequest(start, start + timedelta(days=1), 4.5, 1, "test")
        )
        outcome = tasks.run_backfill.apply(args=[job_id])
        assert outcome.failed()  # retries exhausted in eager mode
        job = RunRepository(arango_db).get_backfill_job(job_id)
        assert job is not None
        assert job["status"] == "pending"
        assert job["next_window_start"] == "2026-09-01T00:00:00.000Z"
        assert job["last_error"]["transient"] is True


class TestEnrichTask:
    def test_enrich_fresh_skip_and_force(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        tasks.sync_feed("all_day")
        assert tasks.enrich_event(DETAIL_KEY) == {"status": "fresh"}
        assert tasks.enrich_event(DETAIL_KEY, force=True) == {"status": "enriched"}
        assert tasks.enrich_event("usgs_doesnotexist") == {"status": "not_found"}

    def test_non_transient_failure_reports_failed(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        tasks.sync_feed("all_day")
        fake_usgs(upstream(lambda r: httpx.Response(404) if "/detail/" in r.url.path else None))
        result = tasks.enrich_event(DETAIL_KEY, force=True)
        assert result["status"] == "failed"


class TestRecoverTask:
    def test_recover_abandons_runs_and_resumes_jobs(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        runs = RunRepository(arango_db)
        run_id = runs.start_run(kind="feed_sync", source="USGS", params={}, correlation_id=None)
        arango_db.collection(s.INGESTION_RUNS).update(
            {"_key": run_id, "started_at": "2020-01-01T00:00:00.000Z"}
        )
        start = datetime(2026, 9, 1, tzinfo=UTC)
        job_id = BackfillService(arango_db, UsgsClient.__new__(UsgsClient)).create_job(
            BackfillRequest(start, start + timedelta(days=1), 4.5, 1, "test")
        )
        runs.update_backfill_job(
            job_id, {"status": "running", "heartbeat_at": "2020-01-01T00:00:00.000Z"}
        )
        result = tasks.recover()
        assert result["abandoned_runs"] == 1
        assert result["requeued_jobs"] == [job_id]
        job = runs.get_backfill_job(job_id)
        assert job is not None
        assert job["status"] == "completed"  # eager re-queue ran the job


class TestCommands:
    def test_arango_migrate_is_idempotent(self, arango_db: StandardDatabase) -> None:
        out = StringIO()
        call_command("arango_migrate", stdout=out)
        assert "up to date" in out.getvalue()

    def test_sync_feed_command(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        out = StringIO()
        call_command("sync_feed", "--feed", "all_day", stdout=out)
        assert "sync succeeded" in out.getvalue()

    def test_sync_feed_command_fails_loudly(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        fake_usgs(lambda r: httpx.Response(500))
        with pytest.raises(CommandError, match="sync failed"):
            call_command("sync_feed", "--feed", "all_day", stdout=StringIO())

    def test_backfill_command_and_resume(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        out = StringIO()
        call_command(
            "backfill",
            "--start=2026-09-01",
            "--end=2026-09-02",
            "--min-magnitude=4.5",
            "--window-days=1",
            stdout=out,
        )
        assert "completed" in out.getvalue()
        with pytest.raises(CommandError, match="required"):
            call_command("backfill", stdout=StringIO())
        with pytest.raises(CommandError, match="invalid date"):
            call_command("backfill", "--start=yesterday", "--end=2026-09-02", stdout=StringIO())

    def test_enrich_event_command(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        call_command("sync_feed", "--feed", "all_day", stdout=StringIO())
        out = StringIO()
        call_command("enrich_event", DETAIL_KEY, stdout=out)
        assert "shakemap" in out.getvalue()
        with pytest.raises(CommandError, match="not found"):
            call_command("enrich_event", "usgs_nope", stdout=StringIO())


class TestCommandLeases:
    """P2: the CLI commands share the scheduled jobs' leases (real ArangoDB, fake upstream)."""

    def test_cli_sync_holds_the_lease_scheduled_runs_use(
        self,
        arango_db: StandardDatabase,
        fake_usgs: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from apps.ingestion.management.commands import sync_feed as command

        seen: dict[str, Any] = {}

        class Probe(command.FeedSyncService):  # type: ignore[misc,name-defined]
            def run(self, feed: str) -> Any:
                # While the CLI runs, the scheduled task and a second CLI must both be refused.
                seen["task"] = tasks.sync_feed(feed)
                with job_lock(tasks.sync_lease_name(feed), ttl_seconds=60) as other:
                    seen["other"] = other
                return super().run(feed)

        monkeypatch.setattr(command, "FeedSyncService", Probe)
        call_command("sync_feed", "--feed", "all_day", stdout=StringIO())
        assert seen == {"task": {"status": "skipped_locked"}, "other": False}
        assert arango_db.collection(s.JOB_LEASES).count() == 0  # released afterwards

    def test_cli_sync_refuses_while_a_scheduled_sync_holds_the_lease(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        with (
            job_lock(tasks.sync_lease_name("all_day"), ttl_seconds=60),
            pytest.raises(CommandError, match="already running"),
        ):
            call_command("sync_feed", "--feed", "all_day", stdout=StringIO())
        assert arango_db.collection(s.INGESTION_RUNS).count() == 0  # nothing ran

    def test_cli_backfill_refuses_while_the_task_holds_the_job(
        self, arango_db: StandardDatabase, fake_usgs: Callable[[Handler], None]
    ) -> None:
        start = datetime(2026, 9, 1, tzinfo=UTC)
        job_id = BackfillService(arango_db, UsgsClient.__new__(UsgsClient)).create_job(
            BackfillRequest(start, start + timedelta(days=2), 4.5, 1, "test")
        )
        with (
            job_lock(tasks.backfill_lease_name(job_id), ttl_seconds=60),
            pytest.raises(CommandError, match=f"already running.*--resume {job_id}"),
        ):
            call_command("backfill", f"--resume={job_id}", stdout=StringIO())
        job = RunRepository(arango_db).get_backfill_job(job_id)
        assert job is not None
        assert job["windows_completed"] == 0  # no window processed

    def test_cli_backfill_holds_the_job_lease_during_each_window(
        self,
        arango_db: StandardDatabase,
        fake_usgs: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from apps.ingestion.management.commands import backfill as command

        refused: list[Any] = []

        class Probe(command.BackfillService):  # type: ignore[misc,name-defined]
            def run_job(self, job_id: str, *, max_windows: int | None = None) -> Any:
                refused.append(tasks.run_backfill.apply(args=[job_id]).get())
                return super().run_job(job_id, max_windows=max_windows)

        monkeypatch.setattr(command, "BackfillService", Probe)
        out = StringIO()
        call_command(
            "backfill", "--start=2026-09-01", "--end=2026-09-03", "--window-days=1", stdout=out
        )
        assert "completed" in out.getvalue()
        assert refused == [{"status": "skipped_locked"}] * 2  # one per window, task refused
        assert arango_db.collection(s.JOB_LEASES).count() == 0

    def test_cli_commands_fail_closed_when_the_lock_store_is_unavailable(
        self,
        arango_db: StandardDatabase,
        fake_usgs: Callable[[Handler], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from apps.core import locks
        from apps.core.errors import DatabaseUnavailable

        class Dead:
            def acquire(self, *args: Any, **kwargs: Any) -> Any:
                raise DatabaseUnavailable("ArangoDB unreachable")

        monkeypatch.setattr(locks, "_repository", Dead)
        monkeypatch.setattr(locks, "_sleep", lambda s: None)
        with pytest.raises(CommandError, match="was not run"):
            call_command("sync_feed", "--feed", "all_day", stdout=StringIO())
        with pytest.raises(CommandError, match="was not run"):
            call_command(
                "backfill",
                "--start=2026-09-01",
                "--end=2026-09-02",
                "--window-days=1",
                stdout=StringIO(),
            )
        assert arango_db.collection(s.INGESTION_RUNS).count() == 0
