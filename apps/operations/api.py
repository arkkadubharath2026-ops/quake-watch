"""System status API (public freshness/health) and operations API (staff only, FR-14)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core import metrics
from apps.core.api import page_params, paginated
from apps.core.arango import catalog
from apps.core.arango.client import get_db, ping
from apps.core.arango.query import explain, indexes_used
from apps.core.clock import to_iso, utc_now
from apps.core.errors import ValidationFailed
from apps.ingestion.adapters.usgs import usgs_breaker
from apps.operations.freshness import FreshnessService
from apps.operations.repository import OperationsRepository
from config.env import get_settings

RUN_KINDS = ("feed_sync", "backfill_window", "detail_enrichment")
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
