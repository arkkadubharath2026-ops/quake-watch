"""Structured logging configuration (structlog on top of stdlib logging).

Every log line carries timestamp, level, logger and any context bound through
``structlog.contextvars`` (correlation_id, ingestion_run_id, source, source_event_id,
endpoint, duration_ms, outcome — ESD §15).
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def build_logging_config(*, level: str, json_output: bool) -> dict[str, Any]:
    # JSON needs exceptions pre-formatted into a field; the console renderer formats them itself.
    renderer: list[Any] = (
        [structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
        if json_output
        else [structlog.dev.ConsoleRenderer(colors=False)]
    )
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    *renderer,
                ],
                "foreign_pre_chain": _SHARED_PROCESSORS,
            }
        },
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structured"}},
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "django.server": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
        },
    }


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


__all__ = ["build_logging_config", "get_logger", "logging"]
