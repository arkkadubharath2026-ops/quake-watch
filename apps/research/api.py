"""Research snapshot API (FR-13): create, list, manifest, export (throttled), delete."""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import authenticated_user
from apps.core.arango.client import get_db
from apps.core.throttling import ScopedRateThrottle
from apps.research.repository import ResearchRepository
from apps.research.services import ResearchService
from config.env import get_settings


def _service() -> ResearchService:
    return ResearchService(
        ResearchRepository(get_db()), application_version=get_settings().resolved_app_version
    )


class SnapshotListView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)

    def get_throttles(self) -> list[Any]:
        # Creating a snapshot is far more expensive than listing: separate, stricter scope.
        self.throttle_scope = "snapshot_create" if self.request.method == "POST" else "user"
        return super().get_throttles()

    def get(self, request: Request) -> Response:
        return Response({"results": _service().list_for_user(authenticated_user(request).id)})

    def post(self, request: Request) -> Response:
        created = _service().create(authenticated_user(request).id, request.data)
        return Response(created, status=201)


class SnapshotDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, snapshot_id: str) -> Response:
        return Response(_service().get(authenticated_user(request).id, snapshot_id))

    def delete(self, request: Request, snapshot_id: str) -> Response:
        _service().delete(authenticated_user(request).id, snapshot_id)
        return Response(status=204)


class SnapshotExportView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "export"

    def get(self, request: Request, snapshot_id: str) -> HttpResponse:
        fmt = request.query_params.get("format", "zip")
        export = _service().export(authenticated_user(request).id, snapshot_id, fmt)
        response = HttpResponse(export.content, content_type=export.content_type)
        response["Content-Disposition"] = f'attachment; filename="{export.filename}"'
        response["X-Content-SHA256"] = export.content_sha256
        return response
