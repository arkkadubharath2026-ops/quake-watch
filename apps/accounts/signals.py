"""Audit authentication events and maintain the login failure counters."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.http import HttpRequest

from apps.accounts import security
from apps.operations import audit


def _meta(request: HttpRequest | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    return audit.client_ip(request.META), request.META.get("HTTP_USER_AGENT")


@receiver(user_logged_in)
def _on_login(sender: Any, request: HttpRequest | None, user: Any, **_: Any) -> None:
    ip, agent = _meta(request)
    security.reset(user.get_username(), ip)
    audit.record(
        "auth.login_succeeded",
        actor_id=user.pk,
        actor_username=user.get_username(),
        ip=ip,
        user_agent=agent,
    )


@receiver(user_login_failed)
def _on_login_failed(
    sender: Any, credentials: dict[str, Any], request: HttpRequest | None = None, **_: Any
) -> None:
    username = str(credentials.get("username") or "")[:150]
    ip, agent = _meta(request)
    if not username:
        return
    locked_before = security.is_locked(username, ip)
    failures = security.register_failure(username, ip)
    action = "auth.login_locked" if locked_before else "auth.login_failed"
    audit.record(
        action,
        actor_id=None,
        actor_username=username,
        details={"failures_in_window": failures},
        outcome="denied",
        ip=ip,
        user_agent=agent,
    )
