"""Copy Django's SQLite accounts and live sessions into ArangoDB (ADR-015), then verify.

    manage.py migrate_auth_to_arango --sqlite /data/auth/auth.sqlite3 [--dry-run] [--no-sessions]

* The SQLite file is opened **read-only** (``mode=ro``); it is never modified or deleted. Retire
  it only after this command reports ``verified: true`` and sign-in has been checked.
* Users keep their ids (every ``user_id`` in ArangoDB stays valid), usernames, password hashes
  (users keep their passwords; hashes are not re-computed), flags and timestamps.
* Unexpired sessions are copied verbatim (Django's signed session encoding), so signed-in users
  stay signed in.
* Idempotent: re-running converges. It refuses to overwrite an ArangoDB account whose id or
  username belongs to a *different* user, and reports group/permission rows, which have no
  equivalent (the application never used them).
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.repository import SessionRepository, UserRepository
from apps.core.arango.client import get_db
from apps.core.clock import to_iso
from apps.operations import audit

_USER_SELECT = (
    "SELECT id, username, password, email, is_active, is_staff, is_superuser, date_joined, "
    "last_login, first_name, last_name FROM auth_user ORDER BY id"
)
_UNMAPPED_TABLES = ("auth_group", "auth_user_groups", "auth_user_user_permissions")


def _sqlite_time(value: str | None) -> str | None:
    """Django stores aware datetimes in SQLite as naive UTC text."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return to_iso(parsed)


def _count(conn: sqlite3.Connection, table: str) -> int | None:
    if table not in _UNMAPPED_TABLES:
        raise ValueError(table)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608
    except sqlite3.OperationalError:
        return None  # table absent


class Command(BaseCommand):
    help = "Migrate Django SQLite users/sessions to ArangoDB (read-only source) and verify."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--sqlite", required=True, type=Path, help="legacy auth.sqlite3")
        parser.add_argument("--dry-run", action="store_true", help="read and check only")
        parser.add_argument("--no-sessions", action="store_true", help="do not copy sessions")

    def handle(self, *args: Any, **options: Any) -> None:
        path: Path = options["sqlite"]
        if not path.is_file():
            raise CommandError(f"{path} does not exist")
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            report = self._migrate(
                conn, dry_run=options["dry_run"], sessions=not options["no_sessions"]
            )
        finally:
            conn.close()
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if not options["dry_run"] and not report["verified"]:
            raise CommandError("verification failed: see 'mismatches' above")

    def _migrate(
        self, conn: sqlite3.Connection, *, dry_run: bool, sessions: bool
    ) -> dict[str, Any]:
        users = UserRepository(get_db())
        rows = [dict(r) for r in conn.execute(_USER_SELECT)]
        conflicts = self._conflicts(users, rows)
        if conflicts:
            raise CommandError(f"refusing to migrate, identity conflicts: {conflicts}")
        report: dict[str, Any] = {
            "source": "sqlite (read-only)",
            "dry_run": dry_run,
            "sqlite_users": len(rows),
            "unmapped_rows": {t: _count(conn, t) for t in _UNMAPPED_TABLES},
        }
        if dry_run:
            report["verified"] = None
            return report
        for row in rows:
            users.import_user(
                {
                    "id": int(row["id"]),
                    "username": row["username"],
                    "password": row["password"],
                    "email": row["email"] or "",
                    "is_active": bool(row["is_active"]),
                    "is_staff": bool(row["is_staff"]),
                    "is_superuser": bool(row["is_superuser"]),
                    "date_joined": _sqlite_time(row["date_joined"]),
                    "last_login": _sqlite_time(row["last_login"]),
                    "first_name": row["first_name"] or "",
                    "last_name": row["last_name"] or "",
                }
            )
        report["sessions"] = self._sessions(conn) if sessions else "skipped"
        mismatches = self._verify(users, rows)
        report.update(arango_users=users.count(), mismatches=mismatches, verified=not mismatches)
        audit.record(
            "accounts.migrated_from_sqlite",
            actor_id=None,
            actor_username="manage.py",
            details={k: report[k] for k in ("sqlite_users", "arango_users", "verified")},
            outcome="ok" if not mismatches else "failed",
        )
        return report

    @staticmethod
    def _conflicts(users: UserRepository, rows: list[dict[str, Any]]) -> list[str]:
        problems = []
        for row in rows:
            by_id = users.get(int(row["id"]))
            if by_id is not None and by_id["username"] != row["username"]:
                problems.append(f"id {row['id']} is {by_id['username']!r} in ArangoDB")
            by_name = users.get_by_username(row["username"])
            if by_name is not None and int(by_name["id"]) != int(row["id"]):
                problems.append(f"username {row['username']!r} has id {by_name['id']}")
        return problems

    @staticmethod
    def _sessions(conn: sqlite3.Connection) -> dict[str, int]:
        repo = SessionRepository(get_db())
        copied = existing = expired = 0
        now = time.time()
        query = "SELECT session_key, session_data, expire_date FROM django_session"
        for row in conn.execute(query):
            expires = datetime.fromisoformat(row["expire_date"])
            expires = expires.replace(tzinfo=UTC) if expires.tzinfo is None else expires
            if expires.timestamp() <= now:
                expired += 1
            elif repo.insert(row["session_key"], row["session_data"], expires.timestamp()):
                copied += 1
            else:
                existing += 1
        return {"copied": copied, "already_present": existing, "expired_skipped": expired}

    @staticmethod
    def _verify(users: UserRepository, rows: list[dict[str, Any]]) -> list[str]:
        mismatches = []
        for row in rows:
            doc = users.get(int(row["id"]))
            if doc is None:
                mismatches.append(f"user {row['id']} missing")
                continue
            for field in ("username", "password", "is_active", "is_staff", "is_superuser"):
                expected = row[field] if field in ("username", "password") else bool(row[field])
                if doc[field] != expected:
                    mismatches.append(f"user {row['id']} {field} differs")
        return mismatches
