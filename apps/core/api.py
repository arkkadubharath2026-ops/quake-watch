"""Shared API plumbing: error envelope, exception mapping, pagination parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.errors import QuakeWatchError
from config.logging import get_logger

log = get_logger(__name__)

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 25
MAX_OFFSET = 50_000  # deep offset pagination is bounded; use narrower filters or exports


def error_body(
    code: str, message: str, request: Any, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "correlation_id": getattr(request, "correlation_id", None),
        }
    }


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    request = context.get("request")
    raw_request = getattr(request, "_request", request)

    if isinstance(exc, QuakeWatchError):
        if exc.http_status >= 500:
            # Internal detail (hosts, database names, driver text) goes to logs only.
            log.error("api_error", code=exc.code, error=exc.message, details=exc.details)
            return Response(
                error_body(exc.code, exc.public_message, raw_request), status=exc.http_status
            )
        return Response(
            error_body(exc.code, exc.message, raw_request, exc.details), status=exc.http_status
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        log.exception("api_unhandled_exception", exc_info=exc)
        return Response(
            error_body("internal_error", "An unexpected error occurred.", raw_request),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, drf_exceptions.ValidationError):
        code, message, details = "validation_error", "Invalid request.", {"fields": response.data}
    elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
        code, message, details = "not_authenticated", "Authentication required.", {}
    elif isinstance(exc, drf_exceptions.PermissionDenied):
        code, message, details = "permission_denied", str(exc.detail), {}
    elif isinstance(exc, (drf_exceptions.NotFound, Http404)):
        code, message, details = "not_found", "Resource not found.", {}
    elif isinstance(exc, drf_exceptions.Throttled):
        code, message = "rate_limited", "Too many requests."
        details = {"retry_after_seconds": getattr(exc, "wait", None)}  # set at runtime by DRF
    elif isinstance(exc, drf_exceptions.APIException):
        code, message, details = exc.default_code, str(exc.detail), {}
    else:  # pragma: no cover - drf only returns responses for APIException/Http404/PermissionDenied
        code, message, details = "error", "Request failed.", {}
    response.data = error_body(str(code), message, raw_request, details)
    return response


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(request: Request, *, default_size: int = DEFAULT_PAGE_SIZE) -> PageParams:
    """Parse ``page``/``page_size`` query params with strict bounds (pagination is mandatory)."""
    errors: dict[str, str] = {}
    try:
        page = int(request.query_params.get("page", "1"))
        if page < 1:
            raise ValueError
    except ValueError:
        errors["page"] = "must be a positive integer"
        page = 1
    try:
        size = int(request.query_params.get("page_size", str(default_size)))
        if not 1 <= size <= MAX_PAGE_SIZE:
            raise ValueError
    except ValueError:
        errors["page_size"] = f"must be an integer between 1 and {MAX_PAGE_SIZE}"
        size = default_size
    if not errors and (page - 1) * size > MAX_OFFSET:
        errors["page"] = f"offset beyond {MAX_OFFSET}; narrow the filters or use an export"
    if errors:
        raise drf_exceptions.ValidationError(errors)
    return PageParams(page=page, page_size=size)


def paginated(items: list[Any], total: int, params: PageParams) -> dict[str, Any]:
    total_pages = (total + params.page_size - 1) // params.page_size if total else 0
    return {
        "results": items,
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": total_pages,
    }


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: int
    username: str
    is_staff: bool


def authenticated_user(request: Request) -> AuthUser:
    """The request's user; views using it must enforce ``IsAuthenticated``."""
    user: Any = request.user
    if not getattr(user, "is_authenticated", False):
        raise drf_exceptions.NotAuthenticated()
    return AuthUser(
        id=int(user.pk), username=str(user.get_username()), is_staff=bool(user.is_staff)
    )
