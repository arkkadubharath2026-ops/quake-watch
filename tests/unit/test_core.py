from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import ClassVar

import pytest
from pydantic import ValidationError

from apps.core.clock import from_epoch_ms, from_iso, to_iso
from apps.core.metrics import percentile
from config.env import AppSettings, Environment


class TestClock:
    def test_iso_is_fixed_width_utc_millis(self) -> None:
        value = datetime(2026, 9, 21, 0, 4, 5, 123456, tzinfo=UTC)
        assert to_iso(value) == "2026-09-21T00:04:05.123Z"

    def test_iso_converts_offsets_to_utc(self) -> None:
        ist = timezone(timedelta(hours=5, minutes=30))
        assert to_iso(datetime(2026, 1, 1, 5, 30, tzinfo=ist)) == "2026-01-01T00:00:00.000Z"

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="naive"):
            to_iso(datetime(2026, 1, 1))  # noqa: DTZ001

    def test_iso_roundtrip_and_ordering(self) -> None:
        a = to_iso(from_epoch_ms(1_700_000_000_000))
        b = to_iso(from_epoch_ms(1_700_000_000_001))
        assert from_iso(a) == from_epoch_ms(1_700_000_000_000)
        assert a < b  # lexicographic order == chronological order

    def test_from_iso_requires_timezone(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            from_iso("2026-01-01T00:00:00")


class TestPercentile:
    def test_nearest_rank(self) -> None:
        values = [float(v) for v in range(1, 101)]
        assert percentile(values, 50) == 50
        assert percentile(values, 95) == 95
        assert percentile(values, 100) == 100

    def test_empty(self) -> None:
        assert percentile([], 95) is None

    def test_single(self) -> None:
        assert percentile([7.0], 99) == 7.0


class TestSettingsValidation:
    base: ClassVar[dict[str, str]] = {"secret_key": "x" * 60, "arango_password": "pw"}

    def test_production_rejects_debug(self) -> None:
        with pytest.raises(ValidationError, match="QW_DEBUG"):
            AppSettings(env=Environment.PRODUCTION, debug=True, _env_file=None, **self.base)

    def test_production_requires_long_secret(self) -> None:
        with pytest.raises(ValidationError, match="at least 50"):
            AppSettings(
                env=Environment.PRODUCTION,
                secret_key="short",
                arango_password="pw",
                _env_file=None,
            )

    def test_csv_hosts_parsed(self) -> None:
        cfg = AppSettings(allowed_hosts="a.com, b.com", _env_file=None, **self.base)
        assert cfg.allowed_hosts == ["a.com", "b.com"]

    def test_invalid_feed_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sync_feed"):
            AppSettings(sync_feed="everything_forever", _env_file=None, **self.base)

    def test_test_env_isolates_database(self) -> None:
        cfg = AppSettings(env=Environment.TEST, arango_db="quakewatch", _env_file=None, **self.base)
        assert cfg.arango_database_name == "quakewatch_test"

    def test_freshness_thresholds_ordered(self) -> None:
        with pytest.raises(ValidationError, match="freshness_stale_minutes"):
            AppSettings(
                freshness_degraded_minutes=30,
                freshness_stale_minutes=10,
                _env_file=None,
                **self.base,
            )
