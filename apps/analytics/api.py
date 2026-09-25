"""Analytics API (FR-09). All windows are ``?days=N`` (1..3660, default 30)."""

from __future__ import annotations

from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.analytics.repository import AnalyticsRepository
from apps.analytics.services import AnalyticsService, parse_days
from apps.core.arango.client import get_db
from apps.core.errors import ValidationFailed


def _service() -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(get_db()))


@api_view(["GET"])
def summary(request: Request) -> Response:
    return Response(_service().summary())


@api_view(["GET"])
def timeseries(request: Request) -> Response:
    return Response(_service().timeseries(parse_days(request.query_params.get("days"))))


@api_view(["GET"])
def distributions(request: Request) -> Response:
    return Response(_service().distributions(parse_days(request.query_params.get("days"))))


@api_view(["GET"])
def breakdowns(request: Request) -> Response:
    return Response(_service().breakdowns(parse_days(request.query_params.get("days"))))


@api_view(["GET"])
def revisions(request: Request) -> Response:
    raw = request.query_params.get("magnitude_threshold", "0.3")
    try:
        threshold = float(raw)
        if not 0 < threshold <= 5:
            raise ValueError
    except ValueError as exc:
        raise ValidationFailed(
            "Invalid threshold.", details={"fields": {"magnitude_threshold": "must be in (0, 5]"}}
        ) from exc
    days = parse_days(request.query_params.get("days"), default=365)
    return Response(_service().revisions(days, magnitude_threshold=threshold))


@api_view(["GET"])
def latency(request: Request) -> Response:
    return Response(_service().latency(parse_days(request.query_params.get("days"))))
