from __future__ import annotations

from typing import Any

import pytest

from apps.earthquakes.domain import SOURCE_STATE_FIELDS
from apps.ingestion import revision_policy as policy

BASE: dict[str, Any] = {
    "source_event_id": "us1",
    "event_type": "earthquake",
    "magnitude": 5.0,
    "magnitude_type": "mb",
    "depth_km": 10.0,
    "latitude": 10.0,
    "longitude": 20.0,
    "occurred_at": "2026-09-21T00:00:00.000Z",
    "place": "Somewhere",
    "status": "automatic",
    "alert": None,
    "tsunami": False,
    "mmi": None,
    "cdi": None,
    "products": ["origin", "phase-data"],
    "felt": None,
    "significance": 400,
}


def changed(**overrides: Any) -> list[str]:
    return [c.field for c in policy.diff(BASE, {**BASE, **overrides})]


def test_every_source_field_is_classified() -> None:
    """Policy completeness: a new source field must be consciously tracked or untracked."""
    classified = set(policy.TRACKED_FIELDS) | set(policy.UNTRACKED_FIELDS) | {"source"}
    assert set(SOURCE_STATE_FIELDS) == classified
    assert not set(policy.TRACKED_FIELDS) & set(policy.UNTRACKED_FIELDS)


def test_identical_state_has_no_changes() -> None:
    assert policy.diff(BASE, dict(BASE)) == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"magnitude": 5.1}, ["magnitude"]),
        ({"magnitude": 5.004}, []),  # below tolerance
        ({"magnitude": None}, ["magnitude"]),
        ({"depth_km": 10.05}, []),
        ({"depth_km": 10.2}, ["depth_km"]),
        ({"latitude": 10.0005}, []),
        ({"latitude": 10.01, "longitude": 20.01}, ["latitude", "longitude"]),
        ({"occurred_at": "2026-09-21T00:00:00.050Z"}, []),
        ({"occurred_at": "2026-09-21T00:00:01.000Z"}, ["occurred_at"]),
        ({"status": "reviewed"}, ["status"]),
        ({"alert": "yellow"}, ["alert"]),
        ({"tsunami": True}, ["tsunami"]),
        ({"products": ["phase-data", "origin"]}, []),  # order-insensitive
        ({"products": ["origin", "phase-data", "shakemap"]}, ["products"]),
        ({"source_event_id": "ci9"}, ["source_event_id"]),
        ({"felt": 12, "significance": 500}, []),  # untracked
    ],
)
def test_diff(overrides: dict[str, Any], expected: list[str]) -> None:
    assert changed(**overrides) == expected


def test_change_carries_before_and_after() -> None:
    (change,) = policy.diff(BASE, {**BASE, "magnitude": 5.4})
    assert (change.field, change.before, change.after) == ("magnitude", 5.0, 5.4)


def test_untracked_changes_detected_separately() -> None:
    assert policy.untracked_changed(BASE, {**BASE, "felt": 3}) == ["felt"]
