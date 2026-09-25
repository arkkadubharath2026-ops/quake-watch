"""Privileged operational actions (FR-14). Every action is audited (FR-15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apps.core.arango import StandardDatabase
from apps.core.clock import to_iso
from apps.core.errors import NotFound, ValidationFailed
from apps.ingestion.normalizer import NormalizedRecord, normalize_feature
from apps.ingestion.pipeline import IngestionPipeline
from apps.ingestion.services import BackfillRequest
from apps.operations.repository import AuditRepository


def _date(raw: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            "Invalid backfill request.", details={"fields": {field: "ISO-8601 date required"}}
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_backfill(payload: Any, *, requested_by: str) -> BackfillRequest:
    """Validate an admin backfill request (bounds are checked again by the service)."""
    if not isinstance(payload, dict):
        raise ValidationFailed("Invalid backfill request.", details={"fields": {"body": "object"}})
    try:
        min_magnitude = (
            float(payload["min_magnitude"]) if payload.get("min_magnitude") is not None else None
        )
        window_days = int(payload.get("window_days", 7))
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            "Invalid backfill request.",
            details={"fields": {"min_magnitude": "number", "window_days": "integer"}},
        ) from exc
    return BackfillRequest(
        start=_date(payload.get("start"), "start"),
        end=_date(payload.get("end"), "end"),
        min_magnitude=min_magnitude,
        window_days=window_days,
        requested_by=requested_by,
    )


def describe_backfill(request: BackfillRequest) -> dict[str, Any]:
    return {
        "start": to_iso(request.start),
        "end": to_iso(request.end),
        "min_magnitude": request.min_magnitude,
        "window_days": request.window_days,
    }


def retry_dead_letter(db: StandardDatabase, key: str) -> dict[str, Any]:
    """Re-run a dead-lettered payload through the normaliser and pipeline.

    Retries are treated as historical reprocessing (mode ``backfill``): they never notify.
    A payload that is still invalid stays dead-lettered with an incremented retry count.
    """
    letter = AuditRepository(db).dead_letter(key)
    if letter is None:
        raise NotFound("Dead letter not found.")
    result = normalize_feature(letter.get("payload") or {})
    pipeline = IngestionPipeline(db, mode="backfill")
    if isinstance(result, NormalizedRecord):
        stats = pipeline.ingest([result])
        outcome = "reingested" if not stats.counts["failed"] else "failed_again"
    else:
        stats = pipeline.ingest([], [result])
        outcome = "still_rejected"
    return {"dead_letter": key, "outcome": outcome, "counts": stats.as_dict()}
