"""Authentication backend: ArangoDB users, login throttling before password verification.

The class keeps its historical name: sessions record the backend's dotted path, and Django rejects
sessions whose path is not in ``AUTHENTICATION_BACKENDS`` - so sessions issued before the move
from SQLite (ADR-015) stay valid.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts import security
from apps.accounts.identity import ArangoUser, get_by_username, get_user
from apps.operations.audit import client_ip


class ThrottledModelBackend(BaseBackend):
    def authenticate(  # type: ignore[override]  # stubs bind backends to the ORM User
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> ArangoUser | None:
        if not username or password is None:
            return None
        decision = security.register_attempt(username, _ip(request))
        if not decision.allowed:
            # PermissionDenied stops the backend chain and fires user_login_failed.
            raise PermissionDenied(f"Login temporarily blocked: {decision.reason}.")
        user = get_by_username(username)
        if user is None:
            make_password(password)  # same hashing cost as a real check: no username oracle
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def user_can_authenticate(user: ArangoUser) -> bool:
        return user.is_active

    def get_user(self, user_id: Any) -> ArangoUser | None:  # type: ignore[override]
        try:
            user = get_user(int(user_id))
        except (TypeError, ValueError):
            return None
        return user if user is not None and self.user_can_authenticate(user) else None


def _ip(request: HttpRequest | None) -> str | None:
    return client_ip(request.META) if request is not None else None
