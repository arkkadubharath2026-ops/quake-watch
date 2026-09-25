"""Alert rule use cases (FR-10, FR-11): owner-scoped CRUD, dry-run preview, notification feed."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from apps.alerts.domain import RuleConditions, RuleInput, RulePatch
from apps.alerts.matcher import evaluate
from apps.alerts.repository import AlertRepository
from apps.core.clock import to_iso, utc_now
from apps.core.errors import NotFound, ValidationFailed, pydantic_details
from apps.earthquakes.filters import EventFilter
from apps.earthquakes.services import EventReader

PREVIEW_DAYS = 7
PREVIEW_LIMIT = 50


def _parse[M: BaseModel](model: type[M], payload: Any) -> M:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailed("Invalid alert rule.", details=pydantic_details(exc)) from exc


class AlertService:
    def __init__(self, repo: AlertRepository, events: EventReader) -> None:
        self.repo = repo
        self.events = events

    def create(self, user_id: int, username: str, payload: Any) -> dict[str, Any]:
        return self.repo.create_rule(user_id, username, _parse(RuleInput, payload))

    def list_rules(self, user_id: int) -> list[dict[str, Any]]:
        return self.repo.list_rules(user_id)

    def get(self, user_id: int, rule_id: str) -> dict[str, Any]:
        rule = self.repo.get_rule(user_id, rule_id)
        if rule is None:  # also covers rules owned by someone else: no existence leak
            raise NotFound("Alert rule not found.")
        return rule

    def update(self, user_id: int, rule_id: str, payload: Any) -> dict[str, Any]:
        current = self.get(user_id, rule_id)
        patch = _parse(RulePatch, payload)
        merged = patch.apply(
            RuleInput.model_validate({k: current[k] for k in RuleInput.model_fields})
        )
        updated = self.repo.replace_rule(user_id, rule_id, merged)
        if updated is None:
            raise NotFound("Alert rule not found.")
        return updated

    def delete(self, user_id: int, rule_id: str) -> None:
        if not self.repo.delete_rule(user_id, rule_id):
            raise NotFound("Alert rule not found.")

    def preview(self, user_id: int, rule_id: str, *, days: int = PREVIEW_DAYS) -> dict[str, Any]:
        """Which recent events would this rule have matched, and why? (no side effects)"""
        rule = self.get(user_id, rule_id)
        conditions = RuleConditions.model_validate(rule["conditions"])
        params: dict[str, Any] = {
            "start": to_iso(utc_now() - timedelta(days=days)),
            "sort": "magnitude",
        }
        if conditions.minimum_magnitude is not None:
            params["min_magnitude"] = conditions.minimum_magnitude
        if conditions.center is not None and conditions.radius_km is not None:
            params.update(
                lon=conditions.center[0], lat=conditions.center[1], radius_km=conditions.radius_km
            )
        rows, _ = self.events.search(EventFilter.from_params(params), offset=0, limit=500)
        matches = []
        for row in rows:
            result = evaluate(conditions, row)
            if result.matched:
                matches.append({"event": row, "explanation": result.as_dict()})
            if len(matches) >= PREVIEW_LIMIT:
                break
        return {"rule": rule, "window_days": days, "would_match": matches, "count": len(matches)}

    # ---- notifications ------------------------------------------------------------------------
    def feed(
        self, user_id: int, *, unread_only: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        return self.repo.feed(user_id, unread_only=unread_only, offset=offset, limit=limit)

    def unread_count(self, user_id: int) -> int:
        return self.repo.unread_count(user_id)

    def mark_read(self, user_id: int, match_id: str | None) -> int:
        return self.repo.mark_read(user_id, match_id)

    def matched_events(self, user_id: int) -> list[dict[str, Any]]:
        return self.repo.matched_events(user_id)
