"""Event API (ESD §9): search, map, detail, revisions, provenance, relationships, enrichment."""

from __future__ import annotations

from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.api import page_params, paginated
from apps.core.arango.client import get_db
from apps.earthquakes.filters import EventFilter
from apps.earthquakes.repository import EventRepository
from apps.earthquakes.services import EventQueryService
from apps.ingestion.tasks import enrich_event


def _service() -> EventQueryService:
    return EventQueryService(EventRepository(get_db()))


@api_view(["GET"])
def event_list(request: Request) -> Response:
    f = EventFilter.from_params(request.query_params)
    params = page_params(request)
    result = _service().search(f, offset=params.offset, limit=params.page_size)
    body = paginated(result["rows"], result["total"], params)
    body["query"] = result["query"]
    return Response(body)


@api_view(["GET"])
def event_map(request: Request) -> Response:
    return Response(_service().map(EventFilter.from_params(request.query_params)))


@api_view(["GET"])
def event_detail(request: Request, identifier: str) -> Response:
    return Response(_service().detail(identifier))


@api_view(["GET"])
def event_revisions(request: Request, identifier: str) -> Response:
    return Response(_service().revisions(identifier))


@api_view(["GET"])
def event_provenance(request: Request, identifier: str) -> Response:
    return Response(_service().provenance(identifier))


@api_view(["GET"])
def event_relationships(request: Request, identifier: str) -> Response:
    return Response(_service().relationships(identifier))


class EventEnrichView(APIView):
    """Queue a detail-feed refresh (lazy enrichment). Returns 202; results appear on the event."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "expensive"

    def post(self, request: Request, identifier: str) -> Response:
        doc = _service().get(identifier)
        task = enrich_event.delay(doc["_key"], force=True)
        return Response({"key": doc["_key"], "status": "queued", "task_id": task.id}, status=202)
