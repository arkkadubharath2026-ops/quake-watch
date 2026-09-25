"""Application error hierarchy.

Domain and service code raise these; the API layer maps them to HTTP responses with a
stable error envelope (see :mod:`apps.core.api`). Infrastructure errors are translated
at the boundary so callers never depend on driver-specific exceptions.
"""

from __future__ import annotations

from typing import Any


class QuakeWatchError(Exception):
    code = "internal_error"
    http_status = 500
    # Shown to clients for 5xx errors instead of ``message`` (which may carry internal detail).
    public_message = "An unexpected error occurred."

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationFailed(QuakeWatchError):
    code = "validation_error"
    http_status = 400


class NotFound(QuakeWatchError):
    code = "not_found"
    http_status = 404


class PermissionDenied(QuakeWatchError):
    code = "permission_denied"
    http_status = 403


class Conflict(QuakeWatchError):
    code = "conflict"
    http_status = 409


class DatabaseUnavailable(QuakeWatchError):
    code = "database_unavailable"
    http_status = 503
    public_message = "The database is temporarily unavailable. Please retry shortly."


class UpstreamError(QuakeWatchError):
    """An upstream source (e.g. USGS) failed. ``transient`` drives retry decisions."""

    code = "upstream_error"
    http_status = 502
    public_message = "The upstream data source is unavailable. Please retry later."

    def __init__(
        self,
        message: str,
        *,
        transient: bool,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.transient = transient
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class CircuitOpen(UpstreamError):
    code = "upstream_circuit_open"
    http_status = 503

    def __init__(self, source: str, retry_in_seconds: float) -> None:
        super().__init__(
            f"circuit open for {source}; retry in {retry_in_seconds:.0f}s",
            transient=True,
            retry_after_seconds=retry_in_seconds,
            details={"source": source},
        )


class SourceSchemaError(QuakeWatchError):
    """Upstream payload does not match the expected contract."""

    code = "source_schema_error"
    http_status = 502


def pydantic_details(exc: Any) -> dict[str, Any]:
    """Map a pydantic ValidationError to ``{"fields": {"a.b": "message"}}`` for the API envelope."""
    fields: dict[str, str] = {}
    for err in exc.errors(include_url=False):
        loc = ".".join(str(part) for part in err["loc"]) or "__all__"
        message = str(err["msg"]).removeprefix("Value error, ")
        fields.setdefault(loc, message)
    return {"fields": fields}
