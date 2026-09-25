from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from apps.alerts.domain import RuleConditions, RuleInput, RulePatch
from apps.alerts.matcher import evaluate

HYDERABAD = (78.4867, 17.3850)  # [lon, lat] as in ESD §11


def event(**overrides: Any) -> dict[str, Any]:
    base = {
        "event_type": "earthquake",
        "magnitude": 5.9,
        "depth_km": 42.0,
        "latitude": 16.0,
        "longitude": 80.0,
        "alert": None,
        "tsunami": False,
    }
    return {**base, **overrides}


class TestConditionsValidation:
    def test_esd_example_is_valid(self) -> None:
        conditions = RuleConditions(
            minimum_magnitude=5.5, center=HYDERABAD, radius_km=300, maximum_depth_km=100
        )
        assert conditions.event_types == ("earthquake",)

    def test_rule_must_have_a_condition(self) -> None:
        with pytest.raises(ValidationError, match="at least one condition"):
            RuleConditions()

    def test_center_and_radius_together(self) -> None:
        with pytest.raises(ValidationError, match="together"):
            RuleConditions(center=HYDERABAD)

    @pytest.mark.parametrize("center", [(200.0, 0.0), (0.0, 95.0)])
    def test_center_range(self, center: tuple[float, float]) -> None:
        with pytest.raises(ValidationError):
            RuleConditions(center=center, radius_km=10)

    def test_depth_bounds_ordered(self) -> None:
        with pytest.raises(ValidationError, match="minimum_depth_km"):
            RuleConditions(minimum_depth_km=100, maximum_depth_km=10)

    def test_unknown_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RuleConditions.model_validate({"minimum_magnitude": 5, "__import__": "os"})

    def test_blank_name_rejected_and_whitespace_normalised(self) -> None:
        with pytest.raises(ValidationError):
            RuleInput(name="   ", conditions=RuleConditions(tsunami_only=True))
        rule = RuleInput(name="  Near   home ", conditions=RuleConditions(tsunami_only=True))
        assert rule.name == "Near home"

    def test_patch_revalidates(self) -> None:
        current = RuleInput(name="r", conditions=RuleConditions(minimum_magnitude=5))
        patched = RulePatch(enabled=False, cooldown_minutes=5).apply(current)
        assert (patched.enabled, patched.cooldown_minutes, patched.name) == (False, 5, "r")
        with pytest.raises(ValidationError):
            RulePatch(cooldown_minutes=-1)


class TestEvaluation:
    def test_esd_example_explanation(self) -> None:
        conditions = RuleConditions(
            minimum_magnitude=5.5, center=HYDERABAD, radius_km=300, maximum_depth_km=100
        )
        result = evaluate(conditions, event(latitude=15.6, longitude=79.2))
        assert result.matched
        assert result.reasons[1] == "magnitude 5.9 >= 5.5"
        assert result.reasons[2] == "depth 42 km <= 100 km"
        assert result.reasons[3].startswith("distance ")
        assert result.reasons[3].endswith(" km <= 300 km")
        assert result.distance_km is not None
        assert result.distance_km < 300

    def test_non_match_lists_failures_and_no_reasons(self) -> None:
        conditions = RuleConditions(minimum_magnitude=6.5, maximum_depth_km=10)
        result = evaluate(conditions, event())
        assert not result.matched
        assert result.reasons == ()
        assert result.failed == ("magnitude 5.9 < 6.5", "depth 42 km > 10 km")

    @pytest.mark.parametrize(
        ("field", "value", "conditions", "expected"),
        [
            ("magnitude", 5.45, {"minimum_magnitude": 5.5}, "magnitude 5.45 < 5.5"),
            ("depth_km", 100.4, {"maximum_depth_km": 100}, "depth 100.4 km > 100 km"),
            ("magnitude", 6.0, {"minimum_magnitude": 6.0}, "magnitude 6 >= 6"),
        ],
    )
    def test_explanations_never_look_contradictory(
        self, field: str, value: float, conditions: dict[str, Any], expected: str
    ) -> None:
        result = evaluate(RuleConditions(**conditions), event(**{field: value}))
        assert expected in (result.reasons + result.failed)

    def test_missing_magnitude_never_matches(self) -> None:
        result = evaluate(RuleConditions(minimum_magnitude=1), event(magnitude=None))
        assert not result.matched
        assert result.failed == ("magnitude unknown",)

    def test_alert_levels_and_tsunami(self) -> None:
        conditions = RuleConditions(alert_levels=("orange", "red"), tsunami_only=True)
        assert evaluate(conditions, event(alert="red", tsunami=True)).matched
        miss = evaluate(conditions, event(alert="green", tsunami=False))
        assert "PAGER alert green in ['orange', 'red']" in miss.failed
        assert "tsunami flag not set" in miss.failed

    def test_event_type_filter(self) -> None:
        conditions = RuleConditions(minimum_magnitude=1)
        assert not evaluate(conditions, event(event_type="quarry blast")).matched

    def test_deterministic(self) -> None:
        conditions = RuleConditions(minimum_magnitude=5, center=HYDERABAD, radius_km=500)
        assert evaluate(conditions, event()) == evaluate(conditions, event())
