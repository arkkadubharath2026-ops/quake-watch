"""Account administration (replaces the Django admin's user pages, ADR-015).

manage.py users list
manage.py users set-staff USERNAME --on|--off
manage.py users set-active USERNAME --on|--off
manage.py users set-password USERNAME            (prompts; --noinput reads QW_NEW_PASSWORD)
manage.py users delete USERNAME --yes            (account + all its ArangoDB data)
"""

from __future__ import annotations

import getpass
import os
from typing import Any, cast

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.identity import ArangoUser, delete_user, get_by_username
from apps.accounts.repository import UserRepository
from apps.core.arango.client import get_db
from apps.operations import audit


def _flag(parser: CommandParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true")
    group.add_argument("--off", action="store_true")


class Command(BaseCommand):
    help = "List and administer ArangoDB user accounts."

    def add_arguments(self, parser: CommandParser) -> None:
        sub = parser.add_subparsers(dest="action", required=True)
        sub.add_parser("list")
        for name in ("set-staff", "set-active"):
            flag_parser = sub.add_parser(name)
            flag_parser.add_argument("username")
            _flag(flag_parser)
        pw = sub.add_parser("set-password")
        pw.add_argument("username")
        pw.add_argument("--noinput", "--no-input", action="store_false", dest="interactive")
        delete = sub.add_parser("delete")
        delete.add_argument("username")
        delete.add_argument("--yes", action="store_true", help="confirm deletion")

    def _user(self, username: str) -> ArangoUser:
        user = get_by_username(username)
        if user is None:
            raise CommandError(f"No user {username!r}.")
        return user

    @staticmethod
    def _audit(action: str, user: ArangoUser, details: dict[str, Any]) -> None:
        audit.record(
            action,
            actor_id=None,
            actor_username="manage.py",
            target=user.username,
            details=details,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        action = options["action"]
        if action == "list":
            for row in UserRepository(get_db()).list():
                flags = [f for f in ("is_staff", "is_superuser") if row.get(f)]
                flags += [] if row.get("is_active") else ["inactive"]
                self.stdout.write(f"{row['id']:>6}  {row['username']:<30} {' '.join(flags)}")
            return
        user = self._user(options["username"])
        if action in ("set-staff", "set-active"):
            field = "is_staff" if action == "set-staff" else "is_active"
            value = bool(options["on"])
            setattr(user, field, value)
            user.save(update_fields=[field])
            self._audit(f"accounts.{field}_changed", user, {field: value})
            self.stdout.write(f"{user.username}: {field} = {value}")
        elif action == "set-password":
            if options["interactive"]:
                password = getpass.getpass()
                if password != getpass.getpass("Password (again): "):
                    raise CommandError("Passwords do not match.")
            else:
                password = os.environ.get("QW_NEW_PASSWORD", "")
            try:
                password_validation.validate_password(password, cast(Any, user))
            except ValidationError as exc:
                raise CommandError("; ".join(exc.messages)) from exc
            user.set_password(password)
            user.save(update_fields=["password"])  # also ends the user's other sessions
            self._audit("accounts.password_changed", user, {})
            self.stdout.write(f"Password changed for {user.username}.")
        elif action == "delete":
            if not options["yes"]:
                raise CommandError("Refusing to delete without --yes.")
            removed = delete_user(user.id)
            self._audit("accounts.deleted", user, {"removed": removed})
            self.stdout.write(f"Deleted {user.username} and their data: {removed}")
