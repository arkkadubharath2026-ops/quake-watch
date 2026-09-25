"""Opt-in live contract tests: the real adapter against the real USGS API.

Run with ``pytest -m live``. These catch drift between recorded fixtures and what the adapter
actually sends/receives (e.g. metadata shape changing with query parameters).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.ingestion.adapters.usgs import build_usgs_client
from apps.ingestion.normalizer import parse_feed

pytestmark = pytest.mark.live


def test_live_summary_feed_contract() -> None:
    client = build_usgs_client()
    try:
        parsed = parse_feed(client.summary_feed("significant_month").body)
    finally:
        client.close()
    assert parsed.metadata.status == 200
    assert parsed.rejected == []


def test_live_catalog_count_and_query_contract() -> None:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=2)
    start = end - timedelta(days=1)
    client = build_usgs_client()
    try:
        count = client.catalog_count(start=start, end=end, min_magnitude=4.5)
        parsed = parse_feed(client.catalog_query(start=start, end=end, min_magnitude=4.5).body)
    finally:
        client.close()
    assert count.max_allowed == 20000
    assert len(parsed.records) + len(parsed.rejected) == count.count
    assert parsed.rejected == []


def test_live_detail_contract() -> None:
    client = build_usgs_client()
    try:
        feed = parse_feed(client.summary_feed("significant_month").body)
        if not feed.records:
            pytest.skip("no significant events this month to fetch details for")
        detail = client.detail(feed.records[0].event.source_event_id)
    finally:
        client.close()
    assert detail.feature.properties.products
