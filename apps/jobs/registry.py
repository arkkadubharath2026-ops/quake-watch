"""Task registration and enqueueing for the ArangoDB job queue (replaces Celery's ``shared_task``).

``@task(name=..., time_limit=..., max_retries=...)`` registers a plain function. Call sites keep
Celery's shape:

* ``fn.delay(*args, **kwargs)`` persists a queued job and returns a :class:`JobHandle` (``.id``);
* ``fn(*args)`` runs the function inline (no queue);
* ``fn.apply(args=[...])`` runs it inline *with* the job's retry semantics (tests, CLI).

Inside a running task, :func:`current_job` gives ``retries`` (completed attempts) for backoff, and a
task asks to be run again by raising :class:`~apps.jobs.domain.Retry`.

With ``settings.JOBS_EAGER`` (tests only, like ``CELERY_TASK_ALWAYS_EAGER``) ``delay`` runs the
task inline through ``apply`` instead of persisting it.
"""

from __future__ import annotations

import contextvars
import json
import traceback
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog
from django.conf import settings

from apps.core.arango.client import get_db
from apps.jobs import domain as d
from apps.jobs.repository import JobRepository
from config.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIME_LIMIT = 15 * 60  # the former CELERY_TASK_TIME_LIMIT


@dataclass(frozen=True, slots=True)
class JobContext:
    id: str | None
    task: str
    attempt: int  # 1-based

    @property
    def retries(self) -> int:
        """Attempts already made before this one (Celery's ``request.retries``)."""
        return self.attempt - 1


_current: contextvars.ContextVar[JobContext | None] = contextvars.ContextVar("qw_job", default=None)


def current_job() -> JobContext:
    ctx = _current.get()
    if ctx is None:
        return JobContext(id=None, task="inline", attempt=1)
    return ctx


@contextmanager
def job_context(ctx: JobContext, correlation_id: str | None) -> Iterator[None]:
    """Bind the job (and the correlation id of whoever enqueued it) for logs and retries."""
    from apps.core.middleware import new_correlation_id

    token = _current.set(ctx)
    saved = structlog.contextvars.get_contextvars()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id or new_correlation_id(), task=ctx.task, task_id=ctx.id
    )
    try:
        yield
    finally:
        structlog.contextvars.clear_contextvars()
        if saved:
            structlog.contextvars.bind_contextvars(**saved)
        _current.reset(token)


@dataclass(frozen=True, slots=True)
class JobHandle:
    id: str
    created: bool = True  # False when an identical queued job already existed (deduplicated)


@dataclass(slots=True)
class InlineResult:
    """Outcome of :meth:`Task.apply` (Celery ``EagerResult`` subset)."""

    id: str
    status: str
    result: Any = None
    error: BaseException | None = None
    attempts: int = 0

    def failed(self) -> bool:
        return self.status in (d.FAILED, d.DEAD)

    def get(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.result


def error_record(exc: BaseException, attempt: int) -> dict[str, Any]:
    cause = exc.exc if isinstance(exc, d.Retry) and exc.exc is not None else exc
    return {
        "type": type(cause).__name__,
        "message": str(cause)[:2000],
        "attempt": attempt,
        "trace": "".join(traceback.format_exception(cause))[-4000:],
    }


@dataclass(eq=False)
class Task:
    fn: Callable[..., Any]
    name: str
    time_limit: int = DEFAULT_TIME_LIMIT
    soft_time_limit: int | None = None
    max_retries: int = 0
    rate_limit: str | None = None
    expires: float | None = None  # queued jobs older than this are discarded, never run
    dedupe: Callable[..., str | None] | None = None  # key: at most one queued job per key
    _limit: d.RateLimit | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.soft_time_limit is not None and self.soft_time_limit >= self.time_limit:
            raise ValueError(f"{self.name}: soft_time_limit must be below time_limit")
        self._limit = d.RateLimit.parse(self.rate_limit) if self.rate_limit else None

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    @property
    def parsed_rate_limit(self) -> d.RateLimit | None:
        return self._limit

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def delay(self, *args: Any, **kwargs: Any) -> JobHandle:
        return self.enqueue(args=list(args), kwargs=dict(kwargs))

    def enqueue(
        self,
        *,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        delay: float = 0.0,
        expires: float | None = None,
        dedupe_key: str | None = None,
    ) -> JobHandle:
        args, kwargs = list(args or []), dict(kwargs or {})
        json.dumps([args, kwargs])  # arguments must survive persistence unchanged
        if getattr(settings, "JOBS_EAGER", False):
            return JobHandle(self.apply(args=args, kwargs=kwargs).id)
        key = dedupe_key or (self.dedupe(*args, **kwargs) if self.dedupe else None)
        doc: dict[str, Any] = {
            "task": self.name,
            "args": args,
            "kwargs": kwargs,
            "max_attempts": self.max_attempts,
            "time_limit": self.time_limit,
            "correlation_id": structlog.contextvars.get_contextvars().get("correlation_id"),
        }
        if key:
            doc["dedupe_key"] = f"{self.name}:{key}"
        job, created = JobRepository(get_db()).enqueue(
            doc, delay=delay, expires=expires if expires is not None else self.expires
        )
        log.info("job_enqueued", job_id=job["_key"], job_task=self.name, deduplicated=not created)
        return JobHandle(str(job["_key"]), created)

    def apply(
        self, *, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None
    ) -> InlineResult:
        """Run inline with retry semantics (no waiting between attempts), like Celery eager."""
        job_id = f"inline-{uuid.uuid4().hex[:12]}"
        correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
        for attempt in range(1, self.max_attempts + 1):
            with job_context(JobContext(job_id, self.name, attempt), correlation_id):
                try:
                    result = self.fn(*(args or []), **(kwargs or {}))
                except d.Retry as exc:
                    if attempt < self.max_attempts:
                        continue
                    return InlineResult(job_id, d.DEAD, error=exc.exc or exc, attempts=attempt)
                except Exception as exc:  # noqa: BLE001 - recorded as the job's failure
                    return InlineResult(job_id, d.FAILED, error=exc, attempts=attempt)
            return InlineResult(job_id, d.SUCCEEDED, result=result, attempts=attempt)
        raise AssertionError("unreachable")  # pragma: no cover


_REGISTRY: dict[str, Task] = {}


def task(
    *,
    name: str,
    time_limit: int = DEFAULT_TIME_LIMIT,
    soft_time_limit: int | None = None,
    max_retries: int = 0,
    rate_limit: str | None = None,
    expires: float | None = None,
    dedupe: Callable[..., str | None] | None = None,
) -> Callable[[Callable[..., Any]], Task]:
    def register(fn: Callable[..., Any]) -> Task:
        existing = _REGISTRY.get(name)
        if existing is not None and existing.fn.__qualname__ != fn.__qualname__:
            raise ValueError(f"duplicate task name {name!r}")
        t = Task(
            fn=fn,
            name=name,
            time_limit=time_limit,
            soft_time_limit=soft_time_limit,
            max_retries=max_retries,
            rate_limit=rate_limit,
            expires=expires,
            dedupe=dedupe,
        )
        _REGISTRY[name] = t
        return t

    return register


def get_task(name: str) -> Task:
    return _REGISTRY[name]


def registered() -> dict[str, Task]:
    return dict(_REGISTRY)
