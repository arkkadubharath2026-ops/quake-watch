"""Removal of a user's ArangoDB data when their Django account is deleted."""

from __future__ import annotations

from arango.database import Database, StandardDatabase

from apps.core.arango import schema as s
from apps.core.arango.query import run_query
from apps.core.arango.transactions import run_in_transaction

_USER_OWNED = (s.ALERT_MATCHES, s.SAVED_SEARCHES, s.RESEARCH_SNAPSHOTS)


def delete_user_data(db: StandardDatabase, user_id: int) -> dict[str, int]:
    """Atomically delete rules (+ edges), matches, saved searches, snapshots, user vertex."""

    def work(txn: Database) -> dict[str, int]:
        removed: dict[str, int] = {}
        rule_ids = run_query(
            txn,
            "accounts_delete_rules",
            "FOR r IN alert_rules FILTER r.user_id == @uid REMOVE r IN alert_rules RETURN OLD._id",
            {"uid": user_id},
        ).rows
        removed[s.ALERT_RULES] = len(rule_ids)
        edge_queries = (
            (
                s.USER_OWNS_RULE,
                "FOR e IN @@edges FILTER e._to IN @ids REMOVE e IN @@edges RETURN 1",
            ),
            (
                s.RULE_MATCHED_EVENT,
                "FOR e IN @@edges FILTER e._from IN @ids REMOVE e IN @@edges RETURN 1",
            ),
        )
        for edges, query in edge_queries:
            binds = {"@edges": edges, "ids": rule_ids}
            removed[edges] = len(run_query(txn, "accounts_delete_edges", query, binds).rows)
        for collection in _USER_OWNED:
            removed[collection] = len(
                run_query(
                    txn,
                    "accounts_delete_owned",
                    "FOR d IN @@c FILTER d.user_id == @uid REMOVE d IN @@c RETURN 1",
                    {"@c": collection, "uid": user_id},
                ).rows
            )
        run_query(
            txn,
            "accounts_delete_vertex",
            "REMOVE {_key: @key} IN users OPTIONS {ignoreErrors: true}",
            {"key": str(user_id)},
        )
        return removed

    collections = [
        s.ALERT_RULES, s.USER_OWNS_RULE, s.RULE_MATCHED_EVENT, s.USERS, *_USER_OWNED,
    ]  # fmt: skip
    return run_in_transaction(db, work, write=collections)
