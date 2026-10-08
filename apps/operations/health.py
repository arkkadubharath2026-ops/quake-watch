"""Liveness / readiness probes (ESD §15).

``/health/live``  — the process is up (no dependencies checked).
``/health/ready`` — ArangoDB (the only stateful dependency) reachable with the expected schema
version.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.core.arango.client import get_db, ping
from apps.core.arango.migrate import applied_version
from apps.core.arango.schema import SCHEMA_VERSION
from apps.core.errors import DatabaseUnavailable


@never_cache
@require_GET
def live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@never_cache
@require_GET
def ready(request: HttpRequest) -> JsonResponse:
    checks: dict[str, dict[str, object]] = {}

    arango_ok, arango_detail = ping()
    schema_version: int | None = None
    if arango_ok:
        try:
            schema_version = applied_version(get_db())
        except DatabaseUnavailable as exc:
            arango_ok, arango_detail = False, str(exc)
    checks["arangodb"] = {"ok": arango_ok, "version": arango_detail if arango_ok else None}
    if not arango_ok:
        checks["arangodb"]["error"] = "unreachable"
    schema_ok = schema_version == SCHEMA_VERSION
    checks["schema"] = {"ok": schema_ok, "applied": schema_version, "expected": SCHEMA_VERSION}

    healthy = arango_ok and schema_ok
    return JsonResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status=200 if healthy else 503,
    )
