"""Tasks used only by the job-queue tests (imported by the test module and the worker runner).

``record`` writes one probe document keyed by the job id: a second execution of the same job
would hit the unique ``_key`` and fail, so duplicate execution is detectable.
"""

from __future__ import annotations

import os
import time
from typing import Any

from apps.core.arango.client import get_db
from apps.jobs import Retry, SoftTimeLimitExceeded, current_job, task

PROBE = "test_job_probe"


@task(name="tests.jobs.record")
def record(tag: str, sleep: float = 0.0) -> dict[str, Any]:
    time.sleep(sleep)
    job = current_job()
    get_db().collection(PROBE).insert(
        {"_key": str(job.id), "tag": tag, "attempt": job.attempt, "pid": os.getpid()}
    )
    return {"tag": tag, "attempt": job.attempt}


@task(name="tests.jobs.flaky", max_retries=2)
def flaky(fail_times: int) -> dict[str, Any]:
    if current_job().attempt <= fail_times:
        raise Retry(0, RuntimeError(f"transient failure on attempt {current_job().attempt}"))
    return {"attempt": current_job().attempt}


@task(name="tests.jobs.boom", max_retries=5)
def boom() -> None:
    raise ValueError("permanent failure")


@task(name="tests.jobs.crash")
def crash() -> None:
    os._exit(3)


@task(name="tests.jobs.slow", time_limit=1)
def slow() -> None:
    time.sleep(30)


@task(name="tests.jobs.soft", soft_time_limit=1, time_limit=5)
def soft() -> dict[str, Any]:
    try:
        time.sleep(4)
    except SoftTimeLimitExceeded:
        return {"cleaned_up": True}
    return {"cleaned_up": False}
