"""Periodic scheduler (replaces Celery beat), safe to run in several processes at once.

Time is divided into ticks of each entry's ``interval`` (ArangoDB server time). For every tick,
:meth:`JobRepository.schedule_tick` atomically records that the tick was taken, so however many
schedulers run, each tick enqueues at most one job. A tick missed while no scheduler ran is not
replayed (like beat). Each scheduled job carries ``expires`` (a tick that waited too long in the
queue is discarded) and a dedupe key, so a slow queue never piles up duplicate runs.
"""

from __future__ import annotations

import signal
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from apps.core.arango.client import get_db
from apps.core.errors import DatabaseUnavailable
from apps.jobs.registry import get_task
from apps.jobs.repository import JobRepository
from config.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    name: str
    task: str
    interval: float
    expires: float | None = None
    args: tuple[Any, ...] = ()

    @classmethod
    def from_setting(cls, name: str, spec: Mapping[str, Any]) -> ScheduleEntry:
        interval = float(spec["interval"])
        if interval < 1:
            raise ValueError(f"schedule {name!r}: interval must be at least 1 second")
        expires = spec.get("expires")
        return cls(
            name=name,
            task=str(spec["task"]),
            interval=interval,
            expires=None if expires is None else float(expires),
            args=tuple(spec.get("args", ())),
        )


def configured_entries() -> list[ScheduleEntry]:
    schedule: Mapping[str, Mapping[str, Any]] = getattr(settings, "JOBS_SCHEDULE", {})
    return [ScheduleEntry.from_setting(name, spec) for name, spec in schedule.items()]


def _default_repo() -> JobRepository:
    return JobRepository(get_db())


@dataclass
class Scheduler:
    entries: list[ScheduleEntry] = field(default_factory=configured_entries)
    repo_factory: Callable[[], JobRepository] = _default_repo
    poll_seconds: float = 1.0

    def __post_init__(self) -> None:
        self._stopping = False
        for entry in self.entries:
            get_task(entry.task)  # fail fast on a typo in the schedule

    def request_stop(self, *_: Any) -> None:
        self._stopping = True

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

    def tick(self) -> list[str]:
        """Enqueue every entry whose current tick is not yet taken; return the job ids."""
        enqueued: list[str] = []
        repo = self.repo_factory()
        for entry in self.entries:
            try:
                tick = repo.schedule_tick(entry.name, entry.task, entry.interval)
                if tick is None:
                    continue
                handle = get_task(entry.task).enqueue(
                    args=list(entry.args),
                    expires=entry.expires,
                    dedupe_key=f"schedule:{entry.name}",
                )
            except DatabaseUnavailable as exc:
                log.warning("schedule_tick_failed", schedule=entry.name, error=str(exc))
                continue
            log.info(
                "schedule_enqueued",
                schedule=entry.name,
                tick=tick,
                job_id=handle.id,
                deduplicated=not handle.created,
            )
            enqueued.append(handle.id)
        return enqueued

    def run(self, *, iterations: int | None = None) -> None:
        log.info("scheduler_started", entries=[e.name for e in self.entries])
        done = 0
        while not self._stopping and (iterations is None or done < iterations):
            self.tick()
            done += 1
            if iterations is None or done < iterations:
                time.sleep(self.poll_seconds)
        log.info("scheduler_stopped")
