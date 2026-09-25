"""Authentication backend that refuses attempts for locked (username, IP) pairs."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts import security
from apps.operations.audit import client_ip


class ThrottledModelBackend(ModelBackend):
    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if username and security.is_locked(username, _ip(request)):
            # PermissionDenied stops the backend chain and fires user_login_failed.
            raise PermissionDenied("Too many failed login attempts; try again later.")
        return super().authenticate(request, username=username, password=password, **kwargs)


def _ip(request: HttpRequest | None) -> str | None:
    return client_ip(request.META) if request is not None else None
