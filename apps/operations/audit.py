"""Audit trail recording (FR-15): who did what, to what, when, from where, with what outcome."""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from apps.core.arango.client import get_db
from apps.core.clock import now_iso
from apps.operations.repository import AuditRepository
from config.env import get_settings
from config.logging import get_logger

log = get_logger(__name__)

ACTIONS = (
    "ingestion.sync_triggered",
    "ingestion.backfill_created",
    "ingestion.dead_letter_retried",
    "auth.login_succeeded",
    "auth.login_failed",
    "auth.login_locked",
    "auth.signup",
    "operations.permission_denied",
    "accounts.is_staff_changed",
    "accounts.is_active_changed",
    "accounts.password_changed",
    "accounts.deleted",
    "accounts.superuser_created",
    "accounts.migrated_from_sqlite",
)


def record(
    action: str,
    *,
    actor_id: int | None,
    actor_username: str | None,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    outcome: str = "ok",
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action {action!r}")
    entry_id = uuid.uuid4().hex
    correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
    AuditRepository(get_db()).append(
        {
            "_key": entry_id,
            "at": now_iso(),
            "action": action,
            "actor_id": actor_id,
            "actor_username": actor_username,
            "target": target,
            "details": details or {},
            "outcome": outcome,
            "ip": ip,
            "user_agent": (user_agent or "")[:200] or None,
            "correlation_id": correlation_id,
        }
    )
    log.info("audit", action=action, actor=actor_username, target=target, outcome=outcome)
    return entry_id


def client_ip(meta: dict[str, Any]) -> str | None:
    """Client address as seen by our own infrastructure (spoof-resistant).

    With ``QW_NUM_PROXIES = n`` trusted proxies, each appends the address it received the request
    from to X-Forwarded-For, so the client is the n-th entry from the right; anything further left
    is client-controlled and ignored. With no proxies the socket peer (REMOTE_ADDR) is used.
    """
    proxies = get_settings().num_proxies
    forwarded = meta.get("HTTP_X_FORWARDED_FOR")
    if proxies and forwarded:
        hops = [h.strip() for h in str(forwarded).split(",") if h.strip()]
        if len(hops) >= proxies:
            return hops[-proxies][:64]
    remote = meta.get("REMOTE_ADDR")
    return str(remote)[:64] if remote else None
