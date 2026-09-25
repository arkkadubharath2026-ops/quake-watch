"""Propagate correlation IDs from the enqueuing request/job into Celery tasks.

The publishing side copies the bound ``correlation_id`` into the task message headers; the worker
binds it (or a fresh one) to structlog contextvars for the task's duration, together with the
task name and id, so a web request and the jobs it triggers share one correlation id.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery.signals import before_task_publish, task_postrun, task_prerun

from apps.core.middleware import new_correlation_id

# Celery's own request already has a ``correlation_id`` attribute (the task id), so ours travels
# under a distinct header name.
HEADER = "qw_correlation_id"

# Context of the code that was running before each task started. With eager execution (tests,
# local dev) tasks run inline inside a request, whose log context must survive the task.
_saved_contexts: dict[str, dict[str, Any]] = {}


@before_task_publish.connect
def _propagate_correlation_id(headers: dict[str, Any] | None = None, **_: Any) -> None:
    correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
    if headers is not None and correlation_id:
        headers.setdefault(HEADER, correlation_id)


@task_prerun.connect
def _bind_task_context(task_id: str | None = None, task: Any = None, **_: Any) -> None:
    inbound = getattr(getattr(task, "request", None), HEADER, None)
    if task_id is not None:
        _saved_contexts[task_id] = structlog.contextvars.get_contextvars()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=inbound or new_correlation_id(),
        task=getattr(task, "name", None),
        task_id=task_id,
    )


@task_postrun.connect
def _clear_task_context(task_id: str | None = None, **_: Any) -> None:
    structlog.contextvars.clear_contextvars()
    previous = _saved_contexts.pop(task_id, None) if task_id is not None else None
    if previous:
        structlog.contextvars.bind_contextvars(**previous)
