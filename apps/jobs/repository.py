"""ArangoDB persistence for the durable job queue (``jobs``, ``job_schedules``).

Every state transition is ONE AQL statement, so its read and write commit atomically:

* **claim** picks the oldest due job and marks it running in the same statement. Two workers that
  pick the same job conflict (1200); :func:`run_atomic` re-runs the loser, which then claims the
  next job — a job is never handed to two workers.
* **finish / retry / release / heartbeat** match on the claim ``token`` (fencing): a worker whose
  lease was reaped can no longer change the job another worker now owns.
* **reap** turns running jobs whose lease expired (worker lost) back into queued jobs — or dead
  letters once the crash allowance is used — and expires stale queued jobs.

All times are ArangoDB server time (``DATE_NOW()/1000``), like the job leases (decision P4).
"""

from __future__ import annotations

from typing import Any

from arango.database import Database
from arango.exceptions import ArangoError

from apps.core.arango import schema as s
from apps.core.arango.atomic import run_atomic
from apps.core.arango.catalog import NamedQuery, register
from apps.core.errors import DatabaseUnavailable
from apps.jobs import domain as d

_J = {"@jobs": s.JOBS}

_ENQUEUE = """
LET now = DATE_NOW() / 1000
INSERT MERGE(@doc, { status: "queued", created_at: now, run_at: now + @delay, attempts: 0,
                     expires_at: @expires == null ? null : now + @expires })
  INTO @@jobs
RETURN { job: NEW, created: true }
"""
_ENQUEUE_DEDUPED = """
LET now = DATE_NOW() / 1000
UPSERT { dedupe_key: @doc.dedupe_key }
  INSERT MERGE(@doc, { status: "queued", created_at: now, run_at: now + @delay, attempts: 0,
                       expires_at: @expires == null ? null : now + @expires })
  UPDATE {}
  IN @@jobs
RETURN { job: NEW, created: OLD == null }
"""

CLAIM = register(
    NamedQuery(
        name="jobs_claim",
        category="jobs",
        question="Which due job should this worker run next (claimed atomically)?",
        aql="""
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j.status == "queued" AND j.run_at <= now
  FILTER j.expires_at == null OR j.expires_at > now
  FILTER j.task NOT IN @blocked
  SORT j.run_at
  LIMIT 1
  UPDATE j WITH {
    status: "running", dedupe_key: null, owner: @owner, token: @token,
    attempts: j.attempts + 1, started_at: now, heartbeat_at: now,
    lease_expires_at: now + @lease
  } IN @@jobs
  RETURN NEW
""",
        sample_binds=lambda: {
            "@jobs": s.JOBS,
            "blocked": [],
            "owner": "w",
            "token": "t" * 32,
            "lease": 60,
        },
        expected_indexes=("qw_jobs_claim",),
        read_only=False,
    )
)

_HEARTBEAT = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status == "running" AND j.token == @token
  UPDATE j WITH { heartbeat_at: now, lease_expires_at: now + @lease } IN @@jobs
  RETURN NEW.lease_expires_at
"""
_FINISH = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status == "running" AND j.token == @token
  UPDATE j WITH {
    status: @status, finished_at: now, result: @result,
    last_error: @error, errors: @error == null ? j.errors : SLICE(APPEND(j.errors, [@error]), -5),
    owner: null, token: null, lease_expires_at: null, purge_at: now + @retention
  } IN @@jobs
  RETURN NEW
"""
_RETRY = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status == "running" AND j.token == @token
  LET dead = j.attempts >= j.max_attempts
  UPDATE j WITH {
    status: dead ? "dead" : "queued",
    run_at: dead ? j.run_at : now + @countdown,
    finished_at: dead ? now : null,
    purge_at: dead ? now + @retention : null,
    last_error: @error, errors: SLICE(APPEND(j.errors, [@error]), -5),
    owner: null, token: null, lease_expires_at: null
  } IN @@jobs
  RETURN NEW
"""
_RELEASE = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status == "running" AND j.token == @token
  UPDATE j WITH {
    status: "queued", run_at: now, attempts: MAX([j.attempts - 1, 0]),
    owner: null, token: null, lease_expires_at: null
  } IN @@jobs
  RETURN NEW
"""
REAP = register(
    NamedQuery(
        name="jobs_reap_lost",
        category="jobs",
        question="Which running jobs lost their worker (lease expired), and where do they go?",
        aql="""
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j.status == "running" AND j.lease_expires_at <= now
  LET dead = j.attempts >= MAX([j.max_attempts, @min_crash])
  LET error = { type: "WorkerLost", message: CONCAT("lease expired; owner ", j.owner),
                at: now, attempt: j.attempts }
  UPDATE j WITH {
    status: dead ? "dead" : "queued",
    run_at: now, finished_at: dead ? now : null, purge_at: dead ? now + @retention : null,
    last_error: error, errors: SLICE(APPEND(j.errors, [error]), -5),
    owner: null, token: null, lease_expires_at: null
  } IN @@jobs
  RETURN { id: NEW._key, task: NEW.task, status: NEW.status, previous_owner: j.owner }
""",
        sample_binds=lambda: {"@jobs": s.JOBS, "min_crash": 3, "retention": 60},
        # Running jobs are few (workers x concurrency): the status prefix of the claim index
        # narrows the scan to them; a dedicated lease index only cost writes.
        expected_indexes=("qw_jobs_claim",),
        read_only=False,
    )
)
_LOST = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status == "running" AND j.token == @token
  LET dead = j.attempts >= MAX([j.max_attempts, @min_crash])
  UPDATE j WITH {
    status: dead ? "dead" : "queued",
    run_at: now + (dead ? 0 : @countdown), finished_at: dead ? now : null,
    purge_at: dead ? now + @retention : null,
    last_error: @error, errors: SLICE(APPEND(j.errors, [@error]), -5),
    owner: null, token: null, lease_expires_at: null
  } IN @@jobs
  RETURN NEW
"""
_EXPIRE = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j.status == "queued" AND j.expires_at != null AND j.expires_at <= now
  UPDATE j WITH {
    status: "expired", dedupe_key: null, finished_at: now, purge_at: now + @retention
  } IN @@jobs
  RETURN NEW._key
"""
_REQUEUE_DEAD = """
LET now = DATE_NOW() / 1000
FOR j IN @@jobs
  FILTER j._key == @id AND j.status IN ["dead", "failed"]
  UPDATE j WITH {
    status: "queued", run_at: now, attempts: 0, finished_at: null, purge_at: null,
    requeued_at: now
  } IN @@jobs
  RETURN NEW
"""
_STATS = """
FOR j IN @@jobs
  COLLECT task = j.task, status = j.status WITH COUNT INTO n
  RETURN { task, status, n }
"""
_LIST = """
FOR j IN @@jobs
  FILTER @status == null OR j.status == @status
  SORT j.created_at DESC
  LIMIT @limit
  RETURN UNSET(j, "_id", "_rev", "token")
"""
_SCHEDULE_TICK = """
LET now = DATE_NOW() / 1000
LET tick = FLOOR(now / @interval)
LET cur = DOCUMENT(@@schedules, @name)
FILTER cur == null OR cur.last_tick < tick
UPSERT { _key: @name }
  INSERT { _key: @name, task: @task, interval: @interval, last_tick: tick, last_enqueued_at: now }
  UPDATE { task: @task, interval: @interval, last_tick: tick, last_enqueued_at: now }
  IN @@schedules
RETURN tick
"""


class JobRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _run(self, name: str, aql: str, binds: dict[str, Any]) -> list[Any]:
        collections = {} if "@schedules" in binds else _J  # AQL rejects undeclared bind vars
        try:
            return run_atomic(self.db, name, aql, {**collections, **binds}, record_metrics=True)
        except ArangoError as exc:
            raise DatabaseUnavailable(f"{name}: {exc}") from exc

    def enqueue(
        self,
        doc: dict[str, Any],
        *,
        delay: float = 0.0,
        expires: float | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Insert a queued job; with ``doc['dedupe_key']`` return the queued twin if one exists."""
        binds = {"doc": {"errors": [], **doc}, "delay": float(delay), "expires": expires}
        if doc.get("dedupe_key"):
            row = self._run("jobs_enqueue_deduped", _ENQUEUE_DEDUPED, binds)[0]
        else:
            row = self._run("jobs_enqueue", _ENQUEUE, binds)[0]
        return row["job"], bool(row["created"])

    def claim(
        self, *, owner: str, token: str, lease_seconds: float, blocked: list[str]
    ) -> dict[str, Any] | None:
        binds = {"owner": owner, "token": token, "lease": lease_seconds, "blocked": blocked}
        rows = self._run(CLAIM.name, CLAIM.aql, binds)
        return rows[0] if rows else None

    def heartbeat(self, job_id: str, token: str, lease_seconds: float) -> bool:
        binds = {"id": job_id, "token": token, "lease": lease_seconds}
        return bool(self._run("jobs_heartbeat", _HEARTBEAT, binds))

    def finish(
        self,
        job_id: str,
        token: str,
        *,
        status: str,
        result: Any = None,
        error: dict[str, Any] | None = None,
        retention: float,
    ) -> dict[str, Any] | None:
        if status not in (d.SUCCEEDED, d.FAILED, d.DEAD):
            raise ValueError(f"not a finishing status: {status}")
        binds = {
            "id": job_id, "token": token, "status": status, "result": result, "error": error,
            "retention": retention,
        }  # fmt: skip
        rows = self._run("jobs_finish", _FINISH, binds)
        return rows[0] if rows else None

    def retry(
        self, job_id: str, token: str, *, countdown: float, error: dict[str, Any], retention: float
    ) -> dict[str, Any] | None:
        """Re-queue after ``countdown``; dead-letter when the job has no attempts left."""
        binds = {
            "id": job_id, "token": token, "countdown": countdown, "error": error,
            "retention": retention,
        }  # fmt: skip
        rows = self._run("jobs_retry", _RETRY, binds)
        return rows[0] if rows else None

    def release(self, job_id: str, token: str) -> bool:
        """Give a running job back to the queue without consuming an attempt (shutdown)."""
        return bool(self._run("jobs_release", _RELEASE, {"id": job_id, "token": token}))

    def lost(
        self, job_id: str, token: str, *, error: dict[str, Any], countdown: float, retention: float
    ) -> dict[str, Any] | None:
        """The process running this job died: re-queue it, or dead-letter past the allowance."""
        binds = {
            "id": job_id, "token": token, "error": error, "countdown": countdown,
            "min_crash": d.MIN_CRASH_ATTEMPTS, "retention": retention,
        }  # fmt: skip
        rows = self._run("jobs_lost", _LOST, binds)
        return rows[0] if rows else None

    def reap(self, retention: float) -> list[dict[str, Any]]:
        binds = {"min_crash": d.MIN_CRASH_ATTEMPTS, "retention": retention}
        return self._run(REAP.name, REAP.aql, binds)

    def expire_stale(self, retention: float) -> list[str]:
        return [str(k) for k in self._run("jobs_expire", _EXPIRE, {"retention": retention})]

    def requeue(self, job_id: str) -> dict[str, Any] | None:
        """Operator action: give a dead or failed job a fresh set of attempts."""
        rows = self._run("jobs_requeue", _REQUEUE_DEAD, {"id": job_id})
        return rows[0] if rows else None

    def get(self, job_id: str) -> dict[str, Any] | None:
        rows = self._run("jobs_get", "RETURN DOCUMENT(@@jobs, @id)", {"id": job_id})
        return rows[0] if rows and rows[0] else None

    def stats(self) -> list[dict[str, Any]]:
        return self._run("jobs_stats", _STATS, {})

    def recent(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self._run("jobs_recent", _LIST, {"status": status, "limit": limit})

    def schedule_tick(self, name: str, task: str, interval: float) -> int | None:
        """Claim the current tick of a periodic entry; None if this tick was already enqueued."""
        binds = {"@schedules": s.JOB_SCHEDULES, "name": name, "task": task, "interval": interval}
        rows = self._run("jobs_schedule_tick", _SCHEDULE_TICK, binds)
        return int(rows[0]) if rows else None
