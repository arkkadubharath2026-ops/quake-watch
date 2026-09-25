"""Contract tests against *recorded* real USGS payloads (tests/fixtures/usgs).

If USGS changes its GeoJSON schema, re-record the fixtures (scripts/record_usgs_fixtures.py) and
these tests show exactly which assumptions broke.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from apps.core.errors import SourceSchemaError
from apps.ingestion.adapters.usgs_models import UsgsCatalogCount, UsgsDetailFeature
from apps.ingestion.normalizer import (
    NormalizedRecord,
    RecordRejected,
    normalize_feature,
    parse_feed,
    payload_hash,
)
from tests.conftest import load_fixture


@pytest.fixture(scope="module")
def summary_feed() -> bytes:
    return load_fixture("usgs/all_day.geojson")


@pytest.fixture(scope="module")
def sample_feature(summary_feed: bytes) -> dict[str, Any]:
    return json.loads(summary_feed)["features"][0]  # type: ignore[no-any-return]


class TestSummaryFeed:
    def test_every_recorded_feature_normalises(self, summary_feed: bytes) -> None:
        parsed = parse_feed(summary_feed)
        assert parsed.rejected == []
        assert len(parsed.records) == parsed.metadata.count

    def test_field_mapping(self, sample_feature: dict[str, Any]) -> None:
        result = normalize_feature(sample_feature)
        assert isinstance(result, NormalizedRecord)
        event, props = result.event, sample_feature["properties"]
        lon, lat, depth = sample_feature["geometry"]["coordinates"]
        assert event.source == "USGS"
        assert event.source_event_id == sample_feature["id"]
        assert (event.longitude, event.latitude, event.depth_km) == (lon, lat, depth)
        assert event.magnitude == props["mag"]
        assert event.magnitude_type == props["magType"]
        assert event.status == props["status"]
        assert event.tsunami is bool(props["tsunami"])
        assert int(event.occurred_at.timestamp() * 1000) == props["time"]
        assert set(event.products) == {t for t in props["types"].split(",") if t}
        assert event.key == f"usgs_{sample_feature['id']}"

    def test_hash_is_stable_and_order_independent(self, sample_feature: dict[str, Any]) -> None:
        reordered = dict(reversed(list(sample_feature.items())))
        assert payload_hash(sample_feature) == payload_hash(reordered)

    def test_missing_values_stay_none(self, sample_feature: dict[str, Any]) -> None:
        raw = copy.deepcopy(sample_feature)
        raw["properties"].update({"mag": None, "felt": None, "sig": None})
        result = normalize_feature(raw)
        assert isinstance(result, NormalizedRecord)
        assert result.event.magnitude is None  # never invented


class TestCatalogAndDetail:
    def test_catalog_window_normalises(self) -> None:
        raw = json.loads(load_fixture("usgs/catalog_window.geojson"))
        parsed = parse_feed(load_fixture("usgs/catalog_window.geojson"))
        assert parsed.rejected == []
        assert len(parsed.records) == len(raw["features"])
        # recorded with the adapter's own parameters: limit/offset replace count
        assert parsed.metadata.limit == 20000
        assert parsed.metadata.count is None
        times = [r.event.occurred_at for r in parsed.records]
        assert times == sorted(times)  # orderby=time-asc was requested

    def test_count_contract(self) -> None:
        count = UsgsCatalogCount.model_validate_json(load_fixture("usgs/catalog_count.json"))
        assert count.maxAllowed == 20000

    def test_detail_contract_exposes_products(self) -> None:
        detail = UsgsDetailFeature.model_validate_json(load_fixture("usgs/detail_event.geojson"))
        assert "shakemap" in detail.properties.products
        shakemap = detail.properties.products["shakemap"][0]
        assert shakemap.updateTime > 0
        assert "maxmmi" in shakemap.properties


class TestMalformedRecords:
    @pytest.mark.parametrize(
        ("mutate", "reason"),
        [
            (lambda f: f.update(geometry=None), "missing_geometry"),
            (lambda f: f["geometry"].update(coordinates=[None, None, 1]), "missing_coordinates"),
            (lambda f: f["properties"].pop("time"), "contract_violation"),
            (lambda f: f["properties"].update(status="superseded"), "unknown_status"),
            (lambda f: f["properties"].update(alert="purple"), "unknown_alert"),
            (lambda f: f["geometry"].update(coordinates=[500, 10, 1]), "value_out_of_range"),
            (lambda f: f["properties"].update(mag=42), "value_out_of_range"),
            (lambda f: f.update(id="bad id!"), "value_out_of_range"),
            (lambda f: f["properties"].update(time="yesterday"), "contract_violation"),
        ],
    )
    def test_rejected_with_reason(
        self, sample_feature: dict[str, Any], mutate: Any, reason: str
    ) -> None:
        raw = copy.deepcopy(sample_feature)
        mutate(raw)
        result = normalize_feature(raw)
        assert isinstance(result, RecordRejected)
        assert result.reason == reason
        assert result.payload_hash == payload_hash(raw)

    def test_one_bad_record_does_not_sink_the_feed(self, summary_feed: bytes) -> None:
        document = json.loads(summary_feed)
        document["features"][3]["geometry"] = None
        parsed = parse_feed(json.dumps(document).encode())
        assert len(parsed.rejected) == 1
        assert len(parsed.records) == len(document["features"]) - 1

    @pytest.mark.parametrize(
        "body",
        [b"<html>503 Service Unavailable</html>", b'{"type": "Feature"}', b"", b'{"type":1}'],
    )
    def test_bad_envelope_is_schema_error(self, body: bytes) -> None:
        with pytest.raises(SourceSchemaError):
            parse_feed(body)
