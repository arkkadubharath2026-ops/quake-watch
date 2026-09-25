"""Request middleware: correlation IDs and request timing/outcome logging + metrics."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse

from apps.core import metrics
from config.logging import get_logger

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
REQUEST_ID_HEADER = "X-Request-ID"

log = get_logger(__name__)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


class CorrelationIdMiddleware:
    """Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        correlation_id = inbound if _REQUEST_ID_RE.match(inbound) else new_correlation_id()
        request.correlation_id = correlation_id  # type: ignore[attr-defined]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = self.get_response(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response[REQUEST_ID_HEADER] = correlation_id
        return response


class RequestTimingMiddleware:
    """Log endpoint/duration/outcome for every request and feed API latency metrics."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        match = getattr(request, "resolver_match", None)
        endpoint = match.view_name if match and match.view_name else "unresolved"
        outcome = "error" if response.status_code >= 500 else "ok"
        if request.path.startswith("/api/"):
            metrics.observe(f"api_latency_ms:{endpoint}", duration_ms)
            metrics.observe("api_latency_ms", duration_ms)
            metrics.incr("api_requests_total")
            if response.status_code >= 500:
                metrics.incr("api_errors_total")
        log_method = log.warning if response.status_code >= 500 else log.info
        if not request.path.startswith("/static/"):
            log_method(
                "http_request",
                method=request.method,
                endpoint=endpoint,
                path=request.path,
                status=response.status_code,
                duration_ms=duration_ms,
                outcome=outcome,
            )
        response["Server-Timing"] = f"app;dur={duration_ms}"
        return response
