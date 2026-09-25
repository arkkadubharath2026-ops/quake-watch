from __future__ import annotations

from types import SimpleNamespace

import structlog

from apps.core import task_context


def test_publisher_copies_bound_correlation_id_into_headers() -> None:
    structlog.contextvars.bind_contextvars(correlation_id="req-12345678")
    headers: dict[str, str] = {}
    task_context._propagate_correlation_id(headers=headers)
    structlog.contextvars.clear_contextvars()
    assert headers == {task_context.HEADER: "req-12345678"}


def test_worker_binds_inbound_id_and_task_identity() -> None:
    task = SimpleNamespace(
        name="ingestion.sync_feed",
        request=SimpleNamespace(**{task_context.HEADER: "req-abc", "correlation_id": "task-1"}),
    )
    task_context._bind_task_context(task_id="task-1", task=task)
    bound = structlog.contextvars.get_contextvars()
    task_context._clear_task_context()
    assert bound["correlation_id"] == "req-abc"  # not Celery's own correlation_id (the task id)
    assert bound["task"] == "ingestion.sync_feed"
    assert structlog.contextvars.get_contextvars() == {}


def test_worker_mints_id_when_none_inbound() -> None:
    task = SimpleNamespace(name="t", request=SimpleNamespace())
    task_context._bind_task_context(task_id="x", task=task)
    bound = structlog.contextvars.get_contextvars()
    task_context._clear_task_context()
    assert len(bound["correlation_id"]) == 32
