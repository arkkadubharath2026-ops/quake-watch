"""Job worker: claims jobs from ArangoDB and runs each one in a forked child process.

The parent process is single-threaded and never runs task code. Per running job it:

* **heartbeats** the job lease every ``heartbeat_seconds`` (fenced by the claim token). If the
  lease was taken over (reaped) or cannot be renewed before it lapses, the child is killed: a
  worker never keeps running a job another worker may now own (fail closed, as with job leases);
* enforces the **hard time limit** by killing the child (status ``failed``, like Celery's
  ``TimeLimitExceeded``); the soft limit raises :class:`SoftTimeLimitExceeded` inside the task;
* records the outcome: ``succeeded``, ``Retry`` -> re-queued with backoff or dead-lettered,
  other exception -> ``failed``, child died -> re-queued or dead-lettered (worker lost).

Children die with the parent (``PR_SET_PDEATHSIG``), so a crashed worker cannot leave orphan
tasks running beside the job's next owner. Every ``maintenance_seconds`` the worker also reaps jobs
whose worker vanished (lease expired) and expires stale queued jobs, so any live worker recovers
the work of a dead one.

Shutdown (SIGTERM/SIGINT): stop claiming, let running jobs finish for ``shutdown_grace`` seconds,
then kill the rest and release their jobs to the queue without consuming an attempt.
"""

from __future__ import annotations

import ctypes
import json
import multiprocessing
import os
import signal
import socket
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess
from types import FrameType
from typing import Any

from apps.core import metrics
from apps.core.arango.client import get_db
from apps.core.errors import DatabaseUnavailable
from apps.jobs import domain as d
from apps.jobs.registry import JobContext, error_record, get_task, job_context, registered
from apps.jobs.repository import JobRepository
from config.logging import get_logger

log = get_logger(__name__)

RETENTION_SECONDS = 7 * 24 * 3600
_PR_SET_PDEATHSIG = 1


def _die_with_parent() -> None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(_PR_SET_PDEATHSIG, signal.SIGKILL)
    except (OSError, AttributeError):  # not Linux: the parent's lease handling still applies
        pass


def _soft_limit_handler(signum: int, frame: FrameType | None) -> None:
    raise d.SoftTimeLimitExceeded("soft time limit exceeded")


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _child_main(conn: Connection, job: dict[str, Any]) -> None:
    """Runs in the forked child: execute the task and report one outcome over ``conn``."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # shutdown is the parent's decision
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    _die_with_parent()
    task = get_task(job["task"])
    attempt = int(job["attempts"])
    if task.soft_time_limit:
        signal.signal(signal.SIGALRM, _soft_limit_handler)
        signal.alarm(task.soft_time_limit)
    outcome: tuple[Any, ...]
    with job_context(JobContext(job["_key"], task.name, attempt), job.get("correlation_id")):
        try:
            outcome = ("ok", _jsonable(task.fn(*job["args"], **job["kwargs"])))
        except d.Retry as exc:
            outcome = ("retry", exc.countdown, error_record(exc, attempt))
        except BaseException as exc:  # noqa: BLE001 - every failure is reported to the parent
            outcome = ("error", error_record(exc, attempt))
        finally:
            signal.alarm(0)
    metrics.flush()  # multiprocessing children leave via os._exit: no atexit flush
    conn.send(outcome)
    conn.close()


@dataclass
class _Running:
    job: dict[str, Any]
    token: str
    process: BaseProcess
    conn: Connection
    started: float
    deadline: float
    next_beat: float
    last_renewed: float

    @property
    def id(self) -> str:
        return str(self.job["_key"])


@dataclass
class WorkerConfig:
    concurrency: int = 1
    lease_seconds: float = 60.0
    heartbeat_seconds: float = 15.0
    poll_seconds: float = 1.0
    maintenance_seconds: float = 15.0
    shutdown_grace: float = 25.0
    retention_seconds: float = RETENTION_SECONDS
    lost_retry_countdown: float = 5.0
    tasks: frozenset[str] | None = None  # None = every registered task

    def __post_init__(self) -> None:
        if self.heartbeat_seconds * 2 >= self.lease_seconds:
            raise ValueError("heartbeat_seconds must be well below lease_seconds")


def _default_repo() -> JobRepository:
    return JobRepository(get_db())


def _default_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


@dataclass
class Worker:
    config: WorkerConfig = field(default_factory=WorkerConfig)
    repo_factory: Callable[[], JobRepository] = _default_repo
    clock: Callable[[], float] = time.monotonic
    name: str = field(default_factory=_default_name)

    def __post_init__(self) -> None:
        self._running: dict[str, _Running] = {}
        self._stopping = False
        self._shutdown_deadline: float | None = None
        self._next_maintenance = 0.0
        self._buckets: dict[str, d.TokenBucket] = {}
        self._ctx = multiprocessing.get_context("fork")
        self.processed = 0

    # -- lifecycle ------------------------------------------------------------------------------
    def request_stop(self, *_: Any) -> None:
        if not self._stopping:
            self._stopping = True
            self._shutdown_deadline = self.clock() + self.config.shutdown_grace
            log.info("worker_stopping", worker=self.name, running=list(self._running))

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

    def run(self, *, max_jobs: int | None = None, idle_exit: float | None = None) -> int:
        """Process jobs until stopped (or ``max_jobs`` claimed / idle ``idle_exit`` seconds)."""
        log.info("worker_started", worker=self.name, concurrency=self.config.concurrency)
        idle_since = self.clock()
        claimed_total = 0
        while True:
            self._maintain()
            self._collect()
            self._supervise()
            if self._stopping:
                if not self._running:
                    break
                deadline = self._shutdown_deadline
                if deadline is not None and self.clock() >= deadline:
                    self._abandon_all()
                    break
            claimed = 0
            while (
                not self._stopping
                and len(self._running) < self.config.concurrency
                and (max_jobs is None or claimed_total < max_jobs)
            ):
                if not self._claim_and_start():
                    break
                claimed += 1
                claimed_total += 1
            if self._running or claimed:
                idle_since = self.clock()
            elif idle_exit is not None and self.clock() - idle_since >= idle_exit:
                break
            if max_jobs is not None and claimed_total >= max_jobs and not self._running:
                break
            self._wait(0 if claimed else self.config.poll_seconds)
        log.info("worker_stopped", worker=self.name, processed=self.processed)
        return self.processed

    # -- claiming -------------------------------------------------------------------------------
    def _blocked_tasks(self, now: float) -> list[str]:
        blocked = [
            name
            for name, t in registered().items()
            if t.parsed_rate_limit is not None and not self._bucket(name).available(now)
        ]
        if self.config.tasks is not None:
            blocked += [n for n in registered() if n not in self.config.tasks]
        return blocked

    def _bucket(self, task_name: str) -> d.TokenBucket:
        bucket = self._buckets.get(task_name)
        if bucket is None:
            limit = get_task(task_name).parsed_rate_limit
            assert limit is not None
            bucket = self._buckets[task_name] = d.TokenBucket(limit)
        return bucket

    def _claim_and_start(self) -> bool:
        now = self.clock()
        token = uuid.uuid4().hex
        try:
            job = self.repo_factory().claim(
                owner=self.name,
                token=token,
                lease_seconds=self.config.lease_seconds,
                blocked=self._blocked_tasks(now),
            )
        except DatabaseUnavailable as exc:
            log.warning("job_claim_failed", worker=self.name, error=str(exc))
            return False
        if job is None:
            return False
        if job["task"] not in registered():
            log.error("job_task_unknown", job_id=job["_key"], job_task=job["task"])
            self._finish_safely(job["_key"], token, d.FAILED, error={
                "type": "UnknownTask", "message": f"no task {job['task']!r} in this worker",
                "attempt": job["attempts"],
            })  # fmt: skip
            return True
        if get_task(job["task"]).parsed_rate_limit is not None:
            self._bucket(job["task"]).take(now)
        parent, child = self._ctx.Pipe(duplex=False)
        process = self._ctx.Process(
            target=_child_main, args=(child, job), name=f"job-{job['_key']}", daemon=True
        )
        process.start()
        child.close()
        self._running[job["_key"]] = _Running(
            job=job,
            token=token,
            process=process,
            conn=parent,
            started=now,
            deadline=now + float(job["time_limit"]),
            next_beat=now + self.config.heartbeat_seconds,
            last_renewed=now,
        )
        log.info(
            "job_started",
            job_id=job["_key"],
            job_task=job["task"],
            attempt=job["attempts"],
            worker=self.name,
            pid=process.pid,
        )
        return True

    # -- supervision ----------------------------------------------------------------------------
    def _wait(self, timeout: float) -> None:
        conns = [r.conn for r in self._running.values()]
        if conns:
            wait(conns, timeout=timeout)
        elif timeout > 0:
            time.sleep(timeout)

    def _collect(self) -> None:
        for run in list(self._running.values()):
            outcome: tuple[Any, ...] | None = None
            if run.conn.poll():
                try:
                    outcome = run.conn.recv()
                except (EOFError, OSError):
                    outcome = None
            elif run.process.is_alive():
                continue
            run.process.join(timeout=10)
            run.conn.close()
            del self._running[run.id]
            self.processed += 1
            self._record(run, outcome)

    def _supervise(self) -> None:
        now = self.clock()
        for run in list(self._running.values()):
            if now >= run.deadline:
                self._kill(run)
                log.error("job_time_limit_exceeded", job_id=run.id, job_task=run.job["task"])
                self._finish_safely(run.id, run.token, d.FAILED, error={
                    "type": "TimeLimitExceeded",
                    "message": f"hard time limit ({run.job['time_limit']} s) exceeded",
                    "attempt": run.job["attempts"],
                })  # fmt: skip
                self._count(run, d.FAILED)
                continue
            if now < run.next_beat:
                continue
            run.next_beat = now + self.config.heartbeat_seconds
            try:
                renewed = self.repo_factory().heartbeat(
                    run.id, run.token, self.config.lease_seconds
                )
            except DatabaseUnavailable as exc:
                lapsed = now - run.last_renewed >= self.config.lease_seconds
                log.warning("job_heartbeat_failed", job_id=run.id, error=str(exc), lapsed=lapsed)
                if lapsed:  # the lease is gone by now: another worker may run this job
                    self._kill(run)
                    log.error("job_abandoned_lease_lapsed", job_id=run.id)
                continue
            if renewed:
                run.last_renewed = now
            else:
                self._kill(run)
                log.error("job_lease_lost", job_id=run.id, job_task=run.job["task"])

    def _kill(self, run: _Running) -> None:
        if run.process.is_alive():
            run.process.kill()
        run.process.join(timeout=10)
        run.conn.close()
        self._running.pop(run.id, None)
        self.processed += 1

    def _abandon_all(self) -> None:
        """Shutdown grace over: stop the remaining jobs and hand them back to the queue."""
        for run in list(self._running.values()):
            self._kill(run)
            try:
                released = self.repo_factory().release(run.id, run.token)
            except DatabaseUnavailable as exc:
                released = False
                log.error("job_release_failed", job_id=run.id, error=str(exc))
            log.warning("job_released_on_shutdown", job_id=run.id, released=released)

    # -- outcomes -------------------------------------------------------------------------------
    def _record(self, run: _Running, outcome: tuple[Any, ...] | None) -> None:
        task_name = run.job["task"]
        ms = round((self.clock() - run.started) * 1000, 1)
        metrics.observe(f"job_duration_ms:{task_name}", ms)
        retention = self.config.retention_seconds
        if outcome is None:
            error = {
                "type": "WorkerLost",
                "message": f"job process exited with code {run.process.exitcode} without a result",
                "attempt": run.job["attempts"],
            }
            log.error("job_process_lost", job_id=run.id, job_task=task_name, **error)
            job = self._call(
                lambda: self.repo_factory().lost(
                    run.id,
                    run.token,
                    error=error,
                    countdown=self.config.lost_retry_countdown,
                    retention=retention,
                )
            )
            self._count(run, str(job["status"]) if job else "unknown")
        elif outcome[0] == "ok":
            self._finish_safely(run.id, run.token, d.SUCCEEDED, result=outcome[1])
            log.info("job_succeeded", job_id=run.id, job_task=task_name, duration_ms=ms)
            self._count(run, d.SUCCEEDED)
        elif outcome[0] == "retry":
            countdown, error = float(outcome[1]), outcome[2]
            job = self._call(
                lambda: self.repo_factory().retry(
                    run.id, run.token, countdown=countdown, error=error, retention=retention
                )
            )
            status = str(job["status"]) if job else "unknown"
            event = "job_dead_lettered" if status == d.DEAD else "job_retry_scheduled"
            log.warning(event, job_id=run.id, job_task=task_name, countdown_s=countdown,
                        attempt=run.job["attempts"], error=error["message"])  # fmt: skip
            self._count(run, status)
        else:
            error = outcome[1]
            self._finish_safely(run.id, run.token, d.FAILED, error=error)
            log.error("job_failed", job_id=run.id, job_task=task_name,
                      error_type=error["type"], error=error["message"])  # fmt: skip
            self._count(run, d.FAILED)

    def _count(self, run: _Running, status: str) -> None:
        metrics.incr(f"jobs_{status}:{run.job['task']}")

    def _finish_safely(
        self,
        job_id: str,
        token: str,
        status: str,
        *,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        self._call(
            lambda: self.repo_factory().finish(
                job_id,
                token,
                status=status,
                result=result,
                error=error,
                retention=self.config.retention_seconds,
            )
        )

    def _call(self, op: Callable[[], dict[str, Any] | None]) -> dict[str, Any] | None:
        """Record an outcome, retrying briefly. If the store stays down the lease lapses and the
        job is re-run by whichever worker reaps it (at-least-once; tasks are idempotent)."""
        for attempt in range(1, 4):
            try:
                return op()
            except DatabaseUnavailable as exc:
                log.warning("job_outcome_write_failed", attempt=attempt, error=str(exc))
                time.sleep(0.5 * attempt)
        return None

    def _maintain(self) -> None:
        now = self.clock()
        if now < self._next_maintenance or self._stopping:
            return
        self._next_maintenance = now + self.config.maintenance_seconds
        try:
            repo = self.repo_factory()
            reaped = repo.reap(self.config.retention_seconds)
            expired = repo.expire_stale(self.config.retention_seconds)
        except DatabaseUnavailable as exc:
            log.warning("job_maintenance_failed", error=str(exc))
            return
        if reaped:
            log.warning("jobs_reaped", jobs=reaped)
            metrics.incr("jobs_reaped", len(reaped))
        if expired:
            log.info("jobs_expired", jobs=expired)
            metrics.incr("jobs_expired", len(expired))
