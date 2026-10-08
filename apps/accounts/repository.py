"""Accounts in ArangoDB (``auth_users``, ADR-015) and removal of a user's data.

Users keep Django's integer ids (``_key`` = str(id)) so every ``user_id`` reference in domain
documents stays valid. New ids come from ``id_sequences`` in the same AQL statement as the insert:
if the username is taken the statement fails as a whole and no id is consumed.
"""

from __future__ import annotations

from typing import Any

from arango.collection import StandardCollection
from arango.database import Database, StandardDatabase
from arango.exceptions import (
    AQLQueryExecuteError,
    ArangoError,
    DocumentInsertError,
    DocumentUpdateError,
    ServerConnectionError,
)

from apps.core.arango import schema as s
from apps.core.arango.atomic import run_atomic
from apps.core.arango.client import sync_optional
from apps.core.arango.query import (
    ERR_CONFLICT,
    ERR_DOCUMENT_NOT_FOUND,
    ERR_UNIQUE_CONSTRAINT,
    run_query,
)
from apps.core.arango.transactions import run_in_transaction
from apps.core.errors import Conflict, DatabaseUnavailable

_USER_OWNED = (s.ALERT_MATCHES, s.SAVED_SEARCHES, s.RESEARCH_SNAPSHOTS)


def delete_user_data(db: StandardDatabase, user_id: int) -> dict[str, int]:
    """Atomically delete rules (+ edges), matches, saved searches, snapshots, user vertex and
    the account itself."""

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
        removed[s.AUTH_USERS] = len(
            run_query(
                txn,
                "accounts_delete_account",
                "FOR u IN @@c FILTER u._key == @key REMOVE u IN @@c RETURN 1",
                {"@c": s.AUTH_USERS, "key": str(user_id)},
            ).rows
        )
        return removed

    collections = [
        s.ALERT_RULES, s.USER_OWNS_RULE, s.RULE_MATCHED_EVENT, s.USERS, s.AUTH_USERS,
        *_USER_OWNED,
    ]  # fmt: skip
    return run_in_transaction(db, work, write=collections)


USER_FIELDS = (
    "username", "email", "password", "is_active", "is_staff", "is_superuser", "date_joined",
    "last_login",
)  # fmt: skip

_CREATE = """
LET id = FIRST(
  UPSERT { _key: @seq }
    INSERT { _key: @seq, value: 1 }
    UPDATE { value: OLD.value + 1 }
    IN @@sequences
  RETURN NEW.value
)
INSERT MERGE(@doc, { _key: TO_STRING(id), id: id }) INTO @@users
RETURN NEW
"""
_IMPORT = """
UPSERT { _key: TO_STRING(@doc.id) }
  INSERT MERGE(@doc, { _key: TO_STRING(@doc.id) })
  REPLACE MERGE(@doc, { _key: TO_STRING(@doc.id) })
  IN @@users
UPSERT { _key: @seq }
  INSERT { _key: @seq, value: @doc.id }
  UPDATE { value: MAX([OLD.value, @doc.id]) }
  IN @@sequences
RETURN NEW
"""
_BY_USERNAME = "FOR u IN @@users FILTER u.username == @username LIMIT 1 RETURN u"
_CI_TAKEN = "FOR u IN @@users FILTER u.username_ci == @ci LIMIT 1 RETURN u.username"
_UPDATE = """
FOR u IN @@users FILTER u._key == @key
  UPDATE u WITH @fields IN @@users
  RETURN NEW
"""
_LIST = "FOR u IN @@users SORT u.id RETURN UNSET(u, '_id', '_rev', 'password')"
_SEQ = "users"
_FAILURES = (ArangoError, ServerConnectionError, OSError)
_IMPORT_EXTRAS = ("first_name", "last_name")
_CREATE_ATTEMPTS = 8


class UserRepository:
    def __init__(self, db: StandardDatabase) -> None:
        self.db = db

    def _run(self, name: str, aql: str, binds: dict[str, Any]) -> list[Any]:
        binds = {"@users": s.AUTH_USERS, **binds}
        try:
            return run_atomic(self.db, name, aql, binds, record_metrics=True)
        except ArangoError as exc:
            raise DatabaseUnavailable(f"{name}: {exc}") from exc

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Insert with the next id; Conflict if the username exists (exact match).

        A unique-constraint error is either the username (permanent: Conflict) or two first-ever
        inserts of the sequence document racing (transient: re-run), so it is told apart here
        instead of being retried blindly.
        """
        doc = {k: fields[k] for k in USER_FIELDS}
        doc["username_ci"] = doc["username"].casefold()
        binds = {"@users": s.AUTH_USERS, "@sequences": s.ID_SEQUENCES, "seq": _SEQ, "doc": doc}
        for _ in range(_CREATE_ATTEMPTS):
            try:
                rows = run_query(self.db, "accounts_create_user", _CREATE, binds).rows
                return dict(rows[0])
            except AQLQueryExecuteError as exc:
                if exc.error_code == ERR_UNIQUE_CONSTRAINT and self.get_by_username(
                    doc["username"]
                ):
                    raise Conflict("A user with that username already exists.") from exc
                if exc.error_code not in (ERR_CONFLICT, ERR_UNIQUE_CONSTRAINT):
                    raise DatabaseUnavailable(f"accounts_create_user: {exc}") from exc
            except (ServerConnectionError, OSError) as exc:
                raise DatabaseUnavailable(f"accounts_create_user: {exc}") from exc
        raise DatabaseUnavailable("accounts_create_user: contention persisted")

    def import_user(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Upsert a user with a given id (migration); advances the id sequence past it."""
        doc = {"id": int(fields["id"]), **{k: fields[k] for k in USER_FIELDS}}
        doc.update({k: fields[k] for k in _IMPORT_EXTRAS if k in fields})  # keep, never drop
        doc["username_ci"] = doc["username"].casefold()
        binds = {"@sequences": s.ID_SEQUENCES, "seq": _SEQ, "doc": doc}
        self._run("accounts_import_user", _IMPORT, binds)
        user = self.get(doc["id"])
        assert user is not None
        return user

    def get(self, user_id: int) -> dict[str, Any] | None:
        """By id - every authenticated request: one document read, no AQL."""
        try:
            doc = sync_optional(self.db.collection(s.AUTH_USERS).get(str(int(user_id))))
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"accounts_get_user: {exc}") from exc
        return dict(doc) if doc else None

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self._run("accounts_user_by_username", _BY_USERNAME, {"username": username})
        return dict(rows[0]) if rows else None

    def username_taken_ci(self, username: str) -> bool:
        return bool(self._run("accounts_username_ci", _CI_TAKEN, {"ci": username.casefold()}))

    def update(self, user_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        unknown = set(fields) - set(USER_FIELDS)
        if unknown:
            raise ValueError(f"unknown user fields: {sorted(unknown)}")
        if "username" in fields:
            fields = {**fields, "username_ci": str(fields["username"]).casefold()}
        rows = self._run("accounts_update_user", _UPDATE, {"key": str(user_id), "fields": fields})
        return dict(rows[0]) if rows else None

    def list(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._run("accounts_list_users", _LIST, {})]

    def count(self) -> int:
        return int(self._run("accounts_count_users", "RETURN LENGTH(@@users)", {})[0])

    def delete(self, user_id: int) -> dict[str, int]:
        """Delete the account and all the user's ArangoDB data (one transaction)."""
        return delete_user_data(self.db, user_id)


_SESSION_EXPIRED = """
FOR d IN @@sessions FILTER d.expire_at <= @now
  REMOVE d IN @@sessions
  COLLECT WITH COUNT INTO n
  RETURN n
"""


class SessionRepository:
    """Storage for :mod:`apps.accounts.sessions` (``sessions``: ``_key`` = session key).

    Every request with a session cookie loads its session, so reads and writes use the document
    API (one key operation, no AQL); only the periodic purge is a query.
    """

    def __init__(self, db: StandardDatabase) -> None:
        self.db = db

    def _col(self) -> StandardCollection:
        return self.db.collection(s.SESSIONS)

    def load(self, key: str, now: float) -> str | None:
        try:
            doc = sync_optional(self._col().get(key))
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"sessions_load: {exc}") from exc
        if doc is None or float(doc["expire_at"]) <= now:
            return None
        return str(doc["data"])

    def insert(self, key: str, data: str, expire_at: float) -> bool:
        """Create a new session; False if the key already exists (Django's CreateError)."""
        try:
            self._col().insert({"_key": key, "data": data, "expire_at": expire_at}, silent=True)
        except DocumentInsertError as exc:
            if exc.error_code == ERR_UNIQUE_CONSTRAINT:
                return False
            raise DatabaseUnavailable(f"sessions_insert: {exc}") from exc
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"sessions_insert: {exc}") from exc
        return True

    def update(self, key: str, data: str, expire_at: float) -> bool:
        """Rewrite an existing session; False if it no longer exists (Django's UpdateError)."""
        doc = {"_key": key, "data": data, "expire_at": expire_at}
        try:
            self._col().update(doc, silent=True)
        except DocumentUpdateError as exc:
            if exc.error_code == ERR_DOCUMENT_NOT_FOUND:
                return False
            raise DatabaseUnavailable(f"sessions_update: {exc}") from exc
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"sessions_update: {exc}") from exc
        return True

    def exists(self, key: str) -> bool:
        try:
            return bool(self._col().has(key))
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"sessions_exists: {exc}") from exc

    def delete(self, key: str) -> bool:
        try:
            return bool(self._col().delete(key, ignore_missing=True, silent=True))
        except _FAILURES as exc:
            raise DatabaseUnavailable(f"sessions_delete: {exc}") from exc

    def clear_expired(self, now: float) -> int:
        try:
            rows = run_atomic(
                self.db,
                "sessions_clear_expired",
                _SESSION_EXPIRED,
                {"@sessions": s.SESSIONS, "now": now},
            )
        except ArangoError as exc:
            raise DatabaseUnavailable(f"sessions_clear_expired: {exc}") from exc
        return int(rows[0]) if rows else 0
