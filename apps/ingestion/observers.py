"""Registry of ingestion observers (dependency inversion: ingestion never imports alerts).

Observers are configured by dotted path in ``settings.QUAKEWATCH_EVENT_OBSERVERS``; each is a
zero-argument factory/class returning an :class:`~apps.ingestion.pipeline.EventObserver`.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from apps.ingestion.pipeline import EventObserver


def configured_observers() -> list[EventObserver]:
    paths: list[str] = getattr(settings, "QUAKEWATCH_EVENT_OBSERVERS", [])
    return [import_string(path)() for path in paths]
