"""Time utilities.

Timestamps are persisted as fixed-width ISO-8601 UTC strings with millisecond precision
(``YYYY-MM-DDTHH:MM:SS.sssZ``). Fixed width keeps them lexicographically sortable, so a
persistent index on the string supports range filters and sorting, and AQL date functions
accept them natively.
"""

from __future__ import annotations

from datetime import UTC, datetime

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("naive datetimes are not allowed; use timezone-aware UTC values")
    utc = value.astimezone(UTC)
    return utc.strftime(ISO_FORMAT)[:-3] + "Z"


def now_iso() -> str:
    return to_iso(utc_now())


def from_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return parsed.astimezone(UTC)


def from_epoch_ms(value: int | float) -> datetime:
    return datetime.fromtimestamp(value / 1000.0, tz=UTC)
