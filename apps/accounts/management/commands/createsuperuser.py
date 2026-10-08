"""Create a staff superuser in ArangoDB (replaces django.contrib.auth's ORM command, ADR-015).

Interactive by default. ``--noinput`` reads ``DJANGO_SUPERUSER_USERNAME``,
``DJANGO_SUPERUSER_PASSWORD`` and optional ``DJANGO_SUPERUSER_EMAIL`` (Django's convention).
"""

from __future__ import annotations

import getpass
import os
from typing import Any

from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.identity import create_superuser
from apps.core.errors import Conflict
from apps.operations import audit


class Command(BaseCommand):
    help = "Create a superuser (staff) account in ArangoDB."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username")
        parser.add_argument("--email", default="")
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["interactive"]:
            username = options["username"] or input("Username: ").strip()
            email = options["email"] or input("Email address (optional): ").strip()
            password = getpass.getpass()
            if password != getpass.getpass("Password (again): "):
                raise CommandError("Passwords do not match.")
        else:
            username = options["username"] or os.environ.get("DJANGO_SUPERUSER_USERNAME", "")
            email = options["email"] or os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
            if not username or not password:
                raise CommandError(
                    "--noinput needs --username (or DJANGO_SUPERUSER_USERNAME) and "
                    "DJANGO_SUPERUSER_PASSWORD."
                )
        try:
            UnicodeUsernameValidator()(username)
            password_validation.validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        try:
            user = create_superuser(username, password, email=email)
        except Conflict as exc:
            raise CommandError(str(exc)) from exc
        audit.record(
            "accounts.superuser_created",
            actor_id=None,
            actor_username="manage.py",
            target=user.username,
        )
        self.stdout.write(f"Superuser {user.username!r} created (id {user.id}).")
