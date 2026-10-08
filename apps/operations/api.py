"""System status API (public freshness/health) and operations API (staff only, FR-14)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, NoReturn

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import metrics
from apps.core.api import authenticated_user, page_params, paginated
from apps.core.arango import catalog
from apps.core.arango.client import get_db, ping
from apps.core.arango.query import explain, indexes_used
from apps.core.clock import to_iso, utc_now
from apps.core.errors import ValidationFailed
from apps.core.throttling import ScopedRateThrottle
from apps.ingestion.adapters.usgs import build_usgs_client, usgs_breaker
from apps.ingestion.services import BackfillService
from apps.ingestion.tasks import run_backfill, sync_feed
from apps.operations import actions, audit
from apps.operations.freshness import FreshnessService
from apps.operations.repository import AuditRepository, OperationsRepository
from config.env import get_settings

RUN_KINDS = ("feed_sync", "backfill_window", "detail_enrichment")
VALID_FEEDS = frozenset(
    f"{level}_{period}"
    for level in ("significant", "4.5", "2.5", "1.0", "all")
    for period in ("hour", "day", "week", "month")
)
RUN_STATUSES = ("running", "succeeded", "partial", "failed", "skipped", "split", "abandoned")


def freshness_service() -> FreshnessService:
    cfg = get_settings()
    return FreshnessService(
        OperationsRepository(get_db()),
        usgs_breaker().state,
        degraded_minutes=cfg.freshness_degraded_minutes,
        stale_minutes=cfg.freshness_stale_minutes,
    )


@api_view(["GET"])
def freshness(request: Request) -> Response:
    return Response(freshness_service().current().as_dict())


@api_view(["GET"])
def health(request: Request) -> Response:
    """Public system health summary (no internals beyond up/down + freshness)."""
    arango_ok, _ = ping()
    fresh = freshness_service().current() if arango_ok else None
    body = {
        "status": "ok" if arango_ok and metrics.ping() else "degraded",
        "database": "up" if arango_ok else "down",
        "cache": "up" if metrics.ping() else "down",
        "freshness": fresh.status if fresh else "unknown",
        "checked_at": to_iso(utc_now()),
    }
    return Response(body, status=200 if arango_ok else 503)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def runs(request: Request) -> Response:
    kind = request.query_params.get("kind") or None
    status = request.query_params.get("status") or None
    errors: dict[str, str] = {}
    if kind and kind not in RUN_KINDS:
        errors["kind"] = f"must be one of {list(RUN_KINDS)}"
    if status and status not in RUN_STATUSES:
        errors["status"] = f"must be one of {list(RUN_STATUSES)}"
    if errors:
        raise ValidationFailed("Invalid filters.", details={"fields": errors})
    params = page_params(request)
    rows, total = OperationsRepository(get_db()).recent_runs(
        kind=kind, status=status, offset=params.offset, limit=params.page_size
    )
    return Response(paginated(rows, total, params))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dead_letters(request: Request) -> Response:
    params = page_params(request)
    unresolved = request.query_params.get("unresolved", "true").lower() != "false"
    rows, total = OperationsRepository(get_db()).dead_letters(
        unresolved_only=unresolved, offset=params.offset, limit=params.page_size
    )
    return Response(paginated(rows, total, params))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def overview(request: Request) -> Response:
    """Ops dashboard data: run stats (24 h / 7 d), collection counts, API/AQL/source metrics."""
    repo = OperationsRepository(get_db())
    now = utc_now()
    series = metrics.series_names()
    return Response(
        {
            "freshness": freshness_service().current().as_dict(),
            "runs_24h": repo.run_stats(to_iso(now - timedelta(days=1))),
            "runs_7d": repo.run_stats(to_iso(now - timedelta(days=7))),
            "collections": repo.collection_counts(),
            "counters": metrics.counters(),
            "latency": [_summary(name) for name in series],
            "generated_at": to_iso(now),
        }
    )


def _summary(name: str) -> dict[str, Any]:
    s = metrics.summarize(name)
    return {
        "name": s.name,
        "count": s.count,
        "p50": s.p50,
        "p95": s.p95,
        "p99": s.p99,
        "max": s.max,
    }


class DiagnosticsView(APIView):
    """EXPLAIN every registered named query: which indexes the optimizer actually uses."""

    permission_classes = (IsAdminUser,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "expensive"

    def get(self, request: Request) -> Response:
        cached = cache.get("ops:diagnostics")
        if cached is not None:
            return Response(cached)
        db = get_db()
        results = []
        for query in catalog.all_queries():
            plan = explain(db, query.aql, query.sample_binds())
            used = sorted(set(indexes_used(plan)))
            results.append(
                {
                    "name": query.name,
                    "category": query.category,
                    "question": query.question,
                    "indexes_used": used,
                    "expected_indexes": list(query.expected_indexes),
                    "uses_expected": query.plan_ok(used),
                    "estimated_cost": plan.get("estimatedCost"),
                    "node_types": [n["type"] for n in plan.get("nodes", [])],
                }
            )
        body = {"generated_at": to_iso(utc_now()), "queries": results}
        cache.set("ops:diagnostics", body, 300)
        return Response(body)


class _AdminAction(APIView):
    """Staff-only, throttled, audited. Each action writes a ``requested`` entry *before* acting
    and an ``ok`` / ``failed`` entry after, so no privileged action can happen unaudited; staff
    permission denials are audited too."""

    permission_classes = (IsAdminUser,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "admin_action"
    action = ""

    def _audit(
        self, request: Request, target: str | None, details: dict[str, Any], outcome: str
    ) -> None:
        user: Any = request.user
        authenticated = bool(getattr(user, "is_authenticated", False))
        audit.record(
            self.action if outcome != "denied" else "operations.permission_denied",
            actor_id=int(user.pk) if authenticated else None,
            actor_username=str(user.get_username()) if authenticated else None,
            target=target if outcome != "denied" else request.path,
            details=details,
            outcome=outcome,
            ip=audit.client_ip(request.META),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )

    def permission_denied(
        self, request: Request, message: str | None = None, code: str | None = None
    ) -> NoReturn:
        self._audit(request, None, {"method": request.method}, "denied")
        super().permission_denied(request, message=message, code=code)

    def _perform[T](
        self, request: Request, target: str | None, details: dict[str, Any], work: Callable[[], T]
    ) -> T:
        self._audit(request, target, details, "requested")
        try:
            result = work()
        except Exception as exc:
            self._audit(request, target, {**details, "error": type(exc).__name__}, "failed")
            raise
        return result


class TriggerSyncView(_AdminAction):
    action = "ingestion.sync_triggered"

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        feed = data.get("feed") or get_settings().sync_feed
        if not isinstance(feed, str) or feed not in VALID_FEEDS:
            raise ValidationFailed(
                "Invalid feed.", details={"fields": {"feed": sorted(VALID_FEEDS)}}
            )
        task = self._perform(request, feed, {}, lambda: sync_feed.delay(feed))
        self._audit(request, feed, {"task_id": task.id}, "ok")
        return Response({"status": "queued", "feed": feed, "task_id": task.id}, status=202)


class BackfillView(_AdminAction):
    action = "ingestion.backfill_created"

    def get(self, request: Request) -> Response:
        return Response({"results": AuditRepository(get_db()).backfill_jobs()})

    def post(self, request: Request) -> Response:
        backfill = actions.parse_backfill(
            request.data, requested_by=authenticated_user(request).username
        )
        summary = actions.describe_backfill(backfill)  # validated fields only

        def create() -> str:
            client = build_usgs_client()
            try:
                return BackfillService(get_db(), client).create_job(backfill)
            finally:
                client.close()

        job_id = self._perform(request, None, summary, create)
        task = run_backfill.delay(job_id)
        self._audit(request, job_id, {**summary, "task_id": task.id}, "ok")
        return Response({"status": "queued", "job_id": job_id, "task_id": task.id}, status=202)


class RetryDeadLetterView(_AdminAction):
    action = "ingestion.dead_letter_retried"

    def post(self, request: Request, key: str) -> Response:
        result = self._perform(request, key, {}, lambda: actions.retry_dead_letter(get_db(), key))
        self._audit(request, key, {"result": result["outcome"]}, "ok")
        return Response(result)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def audit_log(request: Request) -> Response:
    params = page_params(request)
    action = request.query_params.get("action") or None
    if action is not None and action not in audit.ACTIONS:
        raise ValidationFailed(
            "Invalid action.", details={"fields": {"action": list(audit.ACTIONS)}}
        )
    rows, total = AuditRepository(get_db()).recent(
        action=action, offset=params.offset, limit=params.page_size
    )
    return Response(paginated(rows, total, params))
