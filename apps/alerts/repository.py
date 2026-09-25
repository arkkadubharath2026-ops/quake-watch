"""Alert rules, matches and their graph edges. Every user-facing query is scoped by ``user_id``.

Graph: ``users/<id> -user_owns_rule-> alert_rules/<rule> -rule_matched_event-> events/<event>``.
Match keys are deterministic (rule + event), so replays and later revisions never duplicate a match.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from arango.database import Database

from apps.alerts.domain import MAX_RULES_PER_USER, RuleInput
from apps.core.arango import catalog
from apps.core.arango import schema as s
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.query import run_query
from apps.core.arango.transactions import exclusive_query as _exclusive
from apps.core.clock import now_iso
from apps.core.errors import Conflict

RULE_FIELDS = ("name", "enabled", "conditions", "cooldown_minutes", "created_at", "updated_at")


def match_key(rule_key: str, event_key: str) -> str:
    return hashlib.sha256(f"{rule_key}|{event_key}".encode()).hexdigest()[:32]


USER_RULES = catalog.register(
    NamedQuery(
        name="alerts_user_rules",
        category="alerts",
        question="A user's alert rules with match counts (CRUD list).",
        aql="""
        FOR r IN alert_rules
          FILTER r.user_id == @user_id
          SORT r.created_at DESC
          LET matches = LENGTH(FOR v IN 1..1 OUTBOUND r rule_matched_event RETURN 1)
          RETURN MERGE(UNSET(r, "_id", "_rev", "_key"), {id: r._key, match_count: matches})
        """,
        sample_binds=lambda: {"user_id": 1},
        expected_indexes=("qw_rules_user",),
        features=("persistent index", "graph traversal"),
    )
)

ENABLED_RULES = catalog.register(
    NamedQuery(
        name="alerts_enabled_rules",
        category="alerts",
        question="All enabled rules, evaluated against each newly ingested or revised event.",
        aql="FOR r IN alert_rules FILTER r.enabled == true RETURN r",
        sample_binds=lambda: {},
        expected_indexes=("qw_rules_enabled",),
        features=("persistent index",),
    )
)

LAST_NOTIFIED = catalog.register(
    NamedQuery(
        name="alerts_last_notified",
        category="alerts",
        question="Most recent notified match of a rule (cooldown enforcement).",
        aql="""
        FOR m IN alert_matches
          FILTER m.rule_key == @rule AND m.notify == true
          SORT m.rule_key DESC, m.matched_at DESC
          LIMIT 1
          RETURN m.matched_at
        """,
        sample_binds=lambda: {"rule": "x"},
        expected_indexes=("qw_matches_rule_event",),
        features=("persistent index",),
    )
)

USER_FEED = catalog.register(
    NamedQuery(
        name="alerts_user_feed",
        category="alerts",
        question="A user's notification feed (newest first), optionally unread only.",
        aql="""
        FOR m IN alert_matches
          FILTER m.user_id == @user_id
          FILTER @unread == false OR m.read_at == null
          SORT m.user_id DESC, m.matched_at DESC
          LIMIT @offset, @limit
          RETURN MERGE(UNSET(m, "_id", "_rev", "_key"), {id: m._key})
        """,
        sample_binds=lambda: {"user_id": 1, "unread": False, "offset": 0, "limit": 25},
        expected_indexes=("qw_matches_user_time",),
        features=("composite index", "pagination"),
    )
)

MATCHED_EVENTS_GRAPH = catalog.register(
    NamedQuery(
        name="alerts_matched_events_graph",
        category="graph",
        question="Events matched by any of a user's watch rules via 2-hop traversal "
        "users → rules → events (README Q13).",
        aql="""
        FOR rule IN 1..1 OUTBOUND CONCAT("users/", @user_id) user_owns_rule
          FOR ev, edge IN 1..1 OUTBOUND rule rule_matched_event
            FILTER ev.merged_into == null
            SORT edge.matched_at DESC
            LIMIT @limit
            RETURN {rule: rule.name, rule_id: rule._key, event_key: ev._key,
                    magnitude: ev.magnitude, place: ev.place, occurred_at: ev.occurred_at,
                    matched_at: edge.matched_at}
        """,
        sample_binds=lambda: {"user_id": 1, "limit": 20},
        expected_indexes=("edge",),
        features=("graph traversal", "2 hops"),
    )
)


class AlertRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---- rules --------------------------------------------------------------------------------
    def create_rule(self, user_id: int, username: str, rule: RuleInput) -> dict[str, Any]:
        key = uuid.uuid4().hex
        now = now_iso()
        doc = {
            "_key": key,
            "user_id": user_id,
            **rule.model_dump(mode="json"),
            "created_at": now,
            "updated_at": now,
        }
        # Exclusive lock on alert_rules serialises concurrent creates, so the per-user
        # count-then-insert cap cannot be exceeded by parallel requests.
        rows = _exclusive(
            self.db,
            "alerts_create_rule",
            """
            LET existing = LENGTH(FOR r IN alert_rules FILTER r.user_id == @uid RETURN 1)
            FILTER existing < @max
            LET user = FIRST(UPSERT {_key: @ukey} INSERT {_key: @ukey, username: @username}
                             UPDATE {username: @username} IN users RETURN NEW)
            LET rule = FIRST(INSERT @doc INTO alert_rules RETURN NEW)
            INSERT {_from: user._id, _to: rule._id, created_at: @now} INTO user_owns_rule
            RETURN rule
            """,
            {
                "uid": user_id,
                "ukey": str(user_id),
                "username": username,
                "doc": doc,
                "max": MAX_RULES_PER_USER,
                "now": now,
            },
            exclusive=[s.ALERT_RULES],
            write=[s.USERS, s.USER_OWNS_RULE],
        )
        if not rows:
            raise Conflict(f"Rule limit reached ({MAX_RULES_PER_USER} rules per user).")
        return self._present(rows[0])

    def list_rules(self, user_id: int) -> list[dict[str, Any]]:
        return run_query(self.db, USER_RULES.name, USER_RULES.aql, {"user_id": user_id}).rows

    def get_rule(self, user_id: int, rule_id: str) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            "alerts_get_rule",
            """
            LET r = DOCUMENT("alert_rules", @id)
            FILTER r != null AND r.user_id == @uid
            RETURN r
            """,
            {"id": rule_id, "uid": user_id},
        ).rows
        return self._present(rows[0]) if rows else None

    def replace_rule(self, user_id: int, rule_id: str, rule: RuleInput) -> dict[str, Any] | None:
        rows = run_query(
            self.db,
            "alerts_replace_rule",
            """
            LET r = DOCUMENT("alert_rules", @id)
            FILTER r != null AND r.user_id == @uid
            UPDATE r WITH MERGE(@fields, {updated_at: @now}) IN alert_rules
              OPTIONS {mergeObjects: false}
            RETURN NEW
            """,
            {
                "id": rule_id,
                "uid": user_id,
                "fields": rule.model_dump(mode="json"),
                "now": now_iso(),
            },
        ).rows
        return self._present(rows[0]) if rows else None

    def delete_rule(self, user_id: int, rule_id: str) -> bool:
        """Delete a rule and its graph edges. Match history is kept (it snapshots the rule)."""
        rows = run_query(
            self.db,
            "alerts_delete_rule",
            """
            LET r = DOCUMENT("alert_rules", @id)
            FILTER r != null AND r.user_id == @uid
            REMOVE r IN alert_rules
            RETURN OLD._id
            """,
            {"id": rule_id, "uid": user_id},
        ).rows
        if not rows:
            return False
        rule_id_full = rows[0]
        run_query(
            self.db,
            "alerts_delete_owner_edge",
            "FOR e IN user_owns_rule FILTER e._to == @rid REMOVE e IN user_owns_rule",
            {"rid": rule_id_full},
        )
        run_query(
            self.db,
            "alerts_delete_match_edges",
            "FOR e IN rule_matched_event FILTER e._from == @rid REMOVE e IN rule_matched_event",
            {"rid": rule_id_full},
        )
        return True

    def enabled_rules(self) -> list[dict[str, Any]]:
        return run_query(self.db, ENABLED_RULES.name, ENABLED_RULES.aql, {}).rows

    # ---- matches ------------------------------------------------------------------------------
    def last_notified_at(self, rule_key: str) -> str | None:
        rows = run_query(self.db, LAST_NOTIFIED.name, LAST_NOTIFIED.aql, {"rule": rule_key}).rows
        return rows[0] if rows else None

    def insert_match(self, match: dict[str, Any]) -> bool:
        """Insert once (deterministic key); returns False if this rule already matched the event."""
        rows = run_query(
            self.db,
            "alerts_insert_match",
            """
            LET existing = DOCUMENT("alert_matches", @match._key)
            FILTER existing == null
            LET match = (INSERT @match INTO alert_matches)
            LET edge = (
              INSERT {_key: @match._key, _from: CONCAT("alert_rules/", @match.rule_key),
                      _to: CONCAT("events/", @match.event_key), matched_at: @match.matched_at}
              INTO rule_matched_event
            )
            RETURN 1
            """,
            {"match": match},
        ).rows
        return bool(rows)

    def feed(
        self, user_id: int, *, unread_only: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        result = run_query(
            self.db,
            USER_FEED.name,
            USER_FEED.aql,
            {"user_id": user_id, "unread": unread_only, "offset": offset, "limit": limit},
            full_count=True,
        )
        return result.rows, int(result.full_count or 0)

    def unread_count(self, user_id: int) -> int:
        rows = run_query(
            self.db,
            "alerts_unread_count",
            """
            RETURN LENGTH(FOR m IN alert_matches
                            FILTER m.user_id == @uid AND m.read_at == null RETURN 1)
            """,
            {"uid": user_id},
        ).rows
        return int(rows[0]) if rows else 0

    def mark_read(self, user_id: int, match_id: str | None) -> int:
        rows = run_query(
            self.db,
            "alerts_mark_read",
            """
            FOR m IN alert_matches
              FILTER m.user_id == @uid AND m.read_at == null
              FILTER @id == null OR m._key == @id
              UPDATE m WITH {read_at: @now} IN alert_matches
              RETURN 1
            """,
            {"uid": user_id, "id": match_id, "now": now_iso()},
        ).rows
        return len(rows)

    def matched_events(self, user_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        return run_query(
            self.db,
            MATCHED_EVENTS_GRAPH.name,
            MATCHED_EVENTS_GRAPH.aql,
            {"user_id": user_id, "limit": limit},
        ).rows

    @staticmethod
    def _present(doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": doc["_key"],
            "user_id": doc["user_id"],
            **{f: doc.get(f) for f in RULE_FIELDS},
        }
