"""Durable ArangoDB job queue (apps.jobs) on the real test database.

Worker tests run the real worker loop (forked child per job). Multi-worker and crash tests start
workers as separate OS processes (tests/integration/jobs_worker_proc.py) and kill them with real
signals. Short leases/heartbeats keep the suite fast; production defaults are 60 s / 15 s.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from arango.database import StandardDatabase
from django.core.management import call_command
from pytest_django.fixtures import Settings as SettingsWrapper

from apps.core.arango import schema as s
from apps.jobs import domain as d
from apps.jobs.registry import get_task
from apps.jobs.repository import JobRepository
from apps.jobs.scheduler import ScheduleEntry, Scheduler
from apps.jobs.worker import Worker, WorkerConfig
from tests.integration import jobs_testtasks as tt

ROOT = Path(__file__).resolve().parents[2]
FAST = {
    "lease_seconds": 3.0,
    "heartbeat_seconds": 1.0,
    "poll_seconds": 0.2,
    "maintenance_seconds": 0.5,
    "shutdown_grace": 10.0,
    "lost_retry_countdown": 0.0,
}


@pytest.fixture
def queue(arango_db: StandardDatabase, settings: SettingsWrapper) -> Iterator[JobRepository]:
    settings.JOBS_EAGER = False  # these tests exercise the real queue
    if not arango_db.has_collection(tt.PROBE):
        arango_db.create_collection(tt.PROBE)
    arango_db.collection(tt.PROBE).truncate()
    yield JobRepository(arango_db)
    arango_db.collection(tt.PROBE).truncate()


def _worker(**overrides: Any) -> Worker:
    return Worker(WorkerConfig(**{**FAST, **overrides}))


def _job(repo: JobRepository, job_id: str) -> dict[str, Any]:
    job = repo.get(job_id)
    assert job is not None
    return job


def _wait_for(predicate: Callable[[], bool], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("condition not reached in time")


def _spawn_worker(**options: Any) -> subprocess.Popen[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT), "DJANGO_SETTINGS_MODULE": "config.settings_test"}
    args = [
        sys.executable,
        "-m",
        "tests.integration.jobs_worker_proc",
        json.dumps({**FAST, **options}),
    ]
    return subprocess.Popen(  # noqa: S603 - fixed interpreter and module, JSON argument
        args, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
    )


class TestEnqueue:
    def test_delay_persists_a_queued_job(self, queue: JobRepository) -> None:
        handle = tt.record.delay("a", sleep=0)
        job = _job(queue, handle.id)
        assert (job["status"], job["task"], job["args"], job["kwargs"]) == (
            d.QUEUED, "tests.jobs.record", ["a"], {"sleep": 0},
        )  # fmt: skip
        assert (job["attempts"], job["max_attempts"]) == (0, 1)

    def test_arguments_must_be_json(self, queue: JobRepository) -> None:
        with pytest.raises(TypeError):
            tt.record.delay(object())

    def test_dedupe_returns_the_queued_twin_until_claimed(self, queue: JobRepository) -> None:
        first = tt.record.enqueue(args=["x"], dedupe_key="k")
        twin = tt.record.enqueue(args=["x"], dedupe_key="k")
        assert (twin.id, twin.created) == (first.id, False)
        assert queue.claim(owner="w", token=uuid.uuid4().hex, lease_seconds=30, blocked=[])
        later = tt.record.enqueue(args=["x"], dedupe_key="k")
        assert later.created is True
        assert later.id != first.id

    def test_concurrent_deduped_enqueues_create_one_job(self, queue: JobRepository) -> None:
        barrier = threading.Barrier(10)
        ids: list[str] = []

        def enqueue() -> None:
            barrier.wait()
            ids.append(tt.record.enqueue(args=["x"], dedupe_key="race").id)

        threads = [threading.Thread(target=enqueue) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(ids) == 10
        assert len(set(ids)) == 1
        assert queue.db.collection(s.JOBS).count() == 1


class TestClaim:
    def test_each_job_is_claimed_exactly_once_under_contention(self, queue: JobRepository) -> None:
        ids = {tt.record.delay(f"j{i}").id for i in range(30)}
        barrier = threading.Barrier(10)
        claimed: list[str] = []
        lock = threading.Lock()

        def claimer(n: int) -> None:
            barrier.wait()
            while True:
                job = queue.claim(
                    owner=f"w{n}", token=uuid.uuid4().hex, lease_seconds=30, blocked=[]
                )
                if job is None:
                    return
                with lock:
                    claimed.append(job["_key"])

        threads = [threading.Thread(target=claimer, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert sorted(claimed) == sorted(ids)  # every job once, none twice

    def test_future_expired_and_blocked_jobs_are_not_claimed(self, queue: JobRepository) -> None:
        tt.record.enqueue(args=["later"], delay=60)
        tt.record.enqueue(args=["stale"], expires=0.5)
        tt.flaky.delay(0)
        time.sleep(0.8)
        claim = queue.claim(
            owner="w", token=uuid.uuid4().hex, lease_seconds=30, blocked=["tests.jobs.flaky"]
        )
        assert claim is None
        assert len(queue.expire_stale(60)) == 1

    def test_completion_is_fenced_by_the_claim_token(self, queue: JobRepository) -> None:
        handle = tt.record.delay("f")
        job = queue.claim(owner="w1", token="a" * 32, lease_seconds=30, blocked=[])
        assert job is not None
        assert queue.finish(handle.id, "b" * 32, status=d.SUCCEEDED, retention=60) is None
        assert queue.heartbeat(handle.id, "b" * 32, 30) is False
        assert queue.finish(handle.id, "a" * 32, status=d.SUCCEEDED, retention=60) is not None


class TestWorkerOutcomes:
    def test_success_records_result_and_runs_once(self, queue: JobRepository) -> None:
        handle = tt.record.delay("ok")
        assert _worker().run(max_jobs=1) == 1
        job = _job(queue, handle.id)
        assert (job["status"], job["result"], job["attempts"]) == (
            d.SUCCEEDED, {"tag": "ok", "attempt": 1}, 1,
        )  # fmt: skip
        assert job["token"] is None
        assert job["purge_at"] > job["finished_at"]
        assert queue.db.collection(tt.PROBE).count() == 1

    def test_retry_then_success(self, queue: JobRepository) -> None:
        handle = tt.flaky.delay(2)
        _worker().run(idle_exit=1.5)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"], job["result"]) == (d.SUCCEEDED, 3, {"attempt": 3})
        assert [e["type"] for e in job["errors"]] == ["RuntimeError", "RuntimeError"]

    def test_retries_exhausted_go_to_dead_letter(self, queue: JobRepository) -> None:
        handle = tt.flaky.delay(10)
        _worker().run(idle_exit=1.5)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.DEAD, 3)
        assert job["last_error"]["message"] == "transient failure on attempt 3"

    def test_permanent_failure_is_not_retried(self, queue: JobRepository) -> None:
        handle = tt.boom.delay()
        _worker().run(idle_exit=1.0)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.FAILED, 1)
        assert job["last_error"]["type"] == "ValueError"
        assert "permanent failure" in job["last_error"]["trace"]

    def test_crashing_job_is_retried_then_dead_lettered(self, queue: JobRepository) -> None:
        handle = tt.crash.delay()
        _worker().run(idle_exit=1.5)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.DEAD, d.MIN_CRASH_ATTEMPTS)
        assert {e["type"] for e in job["errors"]} == {"WorkerLost"}

    def test_hard_time_limit_kills_the_job(self, queue: JobRepository) -> None:
        handle = tt.slow.delay()
        started = time.monotonic()
        _worker().run(idle_exit=0.5)
        assert time.monotonic() - started < 10
        job = _job(queue, handle.id)
        assert (job["status"], job["last_error"]["type"]) == (d.FAILED, "TimeLimitExceeded")

    def test_soft_time_limit_lets_the_task_clean_up(self, queue: JobRepository) -> None:
        handle = tt.soft.delay()
        _worker().run(idle_exit=0.5)
        job = _job(queue, handle.id)
        assert (job["status"], job["result"]) == (d.SUCCEEDED, {"cleaned_up": True})

    def test_unknown_task_fails_without_running(self, queue: JobRepository) -> None:
        job, _ = queue.enqueue(
            {"task": "tests.jobs.nope", "args": [], "kwargs": {}, "max_attempts": 1,
             "time_limit": 10}
        )  # fmt: skip
        _worker().run(idle_exit=0.5)
        assert _job(queue, job["_key"])["last_error"]["type"] == "UnknownTask"

    def test_rate_limited_task_is_blocked_when_bucket_is_empty(self, queue: JobRepository) -> None:
        enrich = get_task("ingestion.enrich_event")
        assert enrich.parsed_rate_limit == d.RateLimit(30, 60.0)
        worker = _worker()
        bucket = worker._bucket("ingestion.enrich_event")
        for _ in range(30):
            assert bucket.take(time.monotonic())
        assert "ingestion.enrich_event" in worker._blocked_tasks(time.monotonic())


class TestRecovery:
    def test_stale_lease_is_reaped_and_rerun(self, queue: JobRepository) -> None:
        handle = tt.record.delay("orphan")
        lost = queue.claim(owner="dead-worker", token="d" * 32, lease_seconds=0.5, blocked=[])
        assert lost is not None
        time.sleep(0.8)
        _worker().run(idle_exit=1.0)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.SUCCEEDED, 2)
        assert job["errors"][0]["type"] == "WorkerLost"
        assert "dead-worker" in job["errors"][0]["message"]
        # the old owner can no longer touch the job
        assert queue.finish(handle.id, "d" * 32, status=d.FAILED, retention=60) is None

    def test_killed_worker_job_recovered_by_another_worker(self, queue: JobRepository) -> None:
        handle = tt.record.delay("survivor", sleep=4)
        proc = _spawn_worker(concurrency=1)
        try:
            _wait_for(lambda: _job(queue, handle.id)["status"] == d.RUNNING)
            first_owner = _job(queue, handle.id)["owner"]
            proc.kill()  # crash: no cleanup, no release
            proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
        time.sleep(4.5)  # the child died with its parent: nothing may have been recorded
        assert queue.db.collection(tt.PROBE).count() == 0
        _worker().run(idle_exit=6.0)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.SUCCEEDED, 2)
        assert job["owner"] is None
        assert first_owner in job["errors"][0]["message"]
        assert queue.db.collection(tt.PROBE).count() == 1  # executed to completion exactly once

    def test_lost_lease_stops_the_running_job(self, queue: JobRepository) -> None:
        handle = tt.record.delay("usurped", sleep=5)
        proc = _spawn_worker(idle_exit=1.0)
        _wait_for(lambda: _job(queue, handle.id)["status"] == d.RUNNING)
        queue.db.collection(s.JOBS).update({"_key": handle.id, "token": "x" * 32})  # takeover
        assert proc.wait(timeout=20) == 0  # heartbeat saw the takeover, killed the job, went idle
        assert queue.db.collection(tt.PROBE).count() == 0  # the usurped run was stopped
        assert _job(queue, handle.id)["token"] == "x" * 32  # and did not touch the new owner's job

    def test_graceful_shutdown_finishes_running_job(self, queue: JobRepository) -> None:
        handle = tt.record.delay("finish-me", sleep=2)
        proc = _spawn_worker()
        _wait_for(lambda: _job(queue, handle.id)["status"] == d.RUNNING)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == 0
        assert _job(queue, handle.id)["status"] == d.SUCCEEDED

    def test_shutdown_grace_exceeded_releases_job_without_using_an_attempt(
        self, queue: JobRepository
    ) -> None:
        handle = tt.record.delay("release-me", sleep=30)
        proc = _spawn_worker(shutdown_grace=0.5)
        _wait_for(lambda: _job(queue, handle.id)["status"] == d.RUNNING)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == 0
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"], job["token"]) == (d.QUEUED, 0, None)

    def test_requeue_dead_job_command(self, queue: JobRepository) -> None:
        handle = tt.flaky.delay(10)
        _worker().run(idle_exit=1.5)
        assert _job(queue, handle.id)["status"] == d.DEAD
        call_command("jobs", "requeue", handle.id)
        job = _job(queue, handle.id)
        assert (job["status"], job["attempts"]) == (d.QUEUED, 0)


class TestMultipleWorkers:
    def test_competing_workers_run_every_job_exactly_once(self, queue: JobRepository) -> None:
        ids = [tt.record.delay(f"m{i}", sleep=0.05).id for i in range(40)]
        procs = [_spawn_worker(concurrency=2, idle_exit=3.0) for _ in range(3)]
        for proc in procs:
            assert proc.wait(timeout=120) == 0
        jobs = [_job(queue, i) for i in ids]
        assert {j["status"] for j in jobs} == {d.SUCCEEDED}
        assert {j["attempts"] for j in jobs} == {1}
        assert queue.db.collection(tt.PROBE).count() == 40  # no duplicate execution
        pids = {doc["pid"] for doc in queue.db.collection(tt.PROBE).all()}
        assert len(pids) == 40  # one child process per job


class TestScheduler:
    def test_concurrent_schedulers_enqueue_one_job_per_tick(self, queue: JobRepository) -> None:
        entry = ScheduleEntry("probe", "tests.jobs.record", interval=3600, args=("tick",))
        barrier = threading.Barrier(5)
        results: list[list[str]] = []

        def tick() -> None:
            scheduler = Scheduler(entries=[entry])
            barrier.wait()
            results.append(scheduler.tick())

        threads = [threading.Thread(target=tick) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(len(r) for r in results) == 1
        assert Scheduler(entries=[entry]).tick() == []  # same tick: nothing new
        assert queue.db.collection(s.JOBS).count() == 1

    def test_new_tick_while_previous_still_queued_does_not_pile_up(
        self, queue: JobRepository
    ) -> None:
        entry = ScheduleEntry("pile", "tests.jobs.record", interval=1, args=("p",))
        scheduler = Scheduler(entries=[entry], poll_seconds=0.4)
        scheduler.run(iterations=8)  # ~3 s: several ticks, no worker running
        assert queue.db.collection(s.JOBS).count() == 1

    def test_configured_schedule_matches_the_former_beat_schedule(self) -> None:
        entries = {e.name: e for e in Scheduler().entries}
        assert entries["sync-usgs-feed"].task == "ingestion.sync_feed"
        assert entries["sync-usgs-feed"].expires == entries["sync-usgs-feed"].interval
        assert (entries["ingestion-recovery"].task, entries["ingestion-recovery"].interval) == (
            "ingestion.recover", 600.0,
        )  # fmt: skip

    def test_scheduled_job_expires_if_not_run_in_time(self, queue: JobRepository) -> None:
        entry = ScheduleEntry("exp", "tests.jobs.record", interval=3600, expires=0.5, args=("e",))
        (job_id,) = Scheduler(entries=[entry]).tick()
        time.sleep(0.8)
        _worker().run(idle_exit=0.5)
        assert _job(queue, job_id)["status"] == d.EXPIRED
        assert queue.db.collection(tt.PROBE).count() == 0


class TestOperations:
    def test_stats_and_list_commands(
        self, queue: JobRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tt.record.delay("s")
        call_command("jobs", "stats")
        call_command("jobs", "list", "--status", "queued")
        out = capsys.readouterr().out
        assert "tests.jobs.record" in out
        assert '"status": "queued"' in out

    def test_jobs_collection_is_migrated_with_indexes(self, arango_db: StandardDatabase) -> None:
        names = {i["name"] for i in arango_db.collection(s.JOBS).indexes()}
        assert {"qw_jobs_claim", "qw_jobs_dedupe", "qw_jobs_purge"} <= names
