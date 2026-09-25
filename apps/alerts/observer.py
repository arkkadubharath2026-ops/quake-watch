"""Alert-rule evaluation inside the ingestion transaction (ESD §7 "EVALUATE ALERT RULES").

Policy (ADR-005):
* only live-feed ingestion notifies; historical backfill never does;
* only events that occurred within ``max_event_age`` of their observation (default 24 h);
* a rule only matches events that occurred after the rule existed (minus a 1 h grace), so a new
  rule does not flood its owner with past events;
* each (rule, event) pair matches at most once — revisions that newly satisfy a rule (e.g. a
  magnitude upgrade) create the match then; later revisions never duplicate it;
* a match inside the rule's cooldown is recorded but flagged ``notify: false`` (suppressed).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from apps.alerts.domain import RuleConditions
from apps.alerts.matcher import evaluate
from apps.alerts.repository import AlertRepository, match_key
from apps.core import metrics
from apps.core.arango import Database
from apps.core.arango import schema as s
from apps.core.clock import from_iso, utc_now
from apps.ingestion.pipeline import EventChange
from config.logging import get_logger

log = get_logger(__name__)

RULE_CREATION_GRACE = timedelta(hours=1)
EVENT_SNAPSHOT_FIELDS = (
    "magnitude", "magnitude_type", "place", "occurred_at", "depth_km", "latitude", "longitude",
    "alert", "tsunami", "status",
)  # fmt: skip


class AlertRuleObserver:
    write_collections: tuple[str, ...] = (s.ALERT_MATCHES, s.RULE_MATCHED_EVENT)
    read_collections: tuple[str, ...] = (s.ALERT_RULES,)

    def __init__(
        self,
        *,
        max_event_age: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.max_event_age = max_event_age
        self.clock = clock
        self._rules: list[dict[str, Any]] | None = None  # loaded once per ingestion batch

    def _enabled_rules(self, txn: Database) -> list[dict[str, Any]]:
        if self._rules is None:
            self._rules = AlertRepository(txn).enabled_rules()
        return self._rules

    def on_event(self, txn: Database, change: EventChange) -> int:
        if change.mode != "feed":
            return 0
        occurred = from_iso(change.event["occurred_at"])
        if from_iso(change.observed_at) - occurred > self.max_event_age:
            return 0
        repo = AlertRepository(txn)
        created = 0
        for rule in self._enabled_rules(txn):
            if occurred < from_iso(rule["created_at"]) - RULE_CREATION_GRACE:
                continue
            try:
                conditions = RuleConditions.model_validate(rule["conditions"])
            except ValidationError as exc:  # stored rule no longer valid: skip loudly, never crash
                log.error("alert_rule_invalid", rule_id=rule["_key"], error=str(exc))
                continue
            result = evaluate(conditions, change.event)
            if not result.matched:
                continue
            key = match_key(rule["_key"], change.event["_key"])
            last = repo.last_notified_at(rule["_key"])
            cooldown = timedelta(minutes=int(rule["cooldown_minutes"]))
            suppressed = (
                last is not None and from_iso(change.observed_at) - from_iso(last) < cooldown
            )
            inserted = repo.insert_match(
                {
                    "_key": key,
                    "rule_key": rule["_key"],
                    "user_id": rule["user_id"],
                    "event_key": change.event["_key"],
                    "matched_at": change.observed_at,
                    "trigger": change.kind,
                    "changed_fields": [c.field for c in change.changes],
                    "explanation": result.as_dict(),
                    "event_snapshot": {f: change.event.get(f) for f in EVENT_SNAPSHOT_FIELDS},
                    "rule_snapshot": {"name": rule["name"], "conditions": rule["conditions"]},
                    "notify": not suppressed,
                    "suppressed_reason": "cooldown" if suppressed else None,
                    "read_at": None,
                }
            )
            if inserted:
                created += 1
                metrics.incr("alert_matches_total")
                if suppressed:
                    metrics.incr("alert_matches_suppressed")
                log.info(
                    "alert_matched",
                    rule_id=rule["_key"],
                    source_event_id=change.event.get("source_event_id"),
                    suppressed=suppressed,
                    reason=list(result.reasons),
                )
        return created
