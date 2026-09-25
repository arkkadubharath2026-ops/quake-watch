"""Alert rules + notifications API (authenticated; owner-scoped)."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.repository import AlertRepository
from apps.alerts.services import AlertService
from apps.core.api import authenticated_user, page_params, paginated
from apps.core.arango.client import get_db
from apps.earthquakes.repository import EventRepository


def _service() -> AlertService:
    db = get_db()
    return AlertService(AlertRepository(db), EventRepository(db))


def _user(request: Request) -> tuple[int, str]:
    user = authenticated_user(request)
    return user.id, user.username


class RuleListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        return Response({"results": _service().list_rules(_user(request)[0])})

    def post(self, request: Request) -> Response:
        user_id, username = _user(request)
        return Response(_service().create(user_id, username, request.data), status=201)


class RuleDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, rule_id: str) -> Response:
        return Response(_service().get(_user(request)[0], rule_id))

    def patch(self, request: Request, rule_id: str) -> Response:
        return Response(_service().update(_user(request)[0], rule_id, request.data))

    def delete(self, request: Request, rule_id: str) -> Response:
        _service().delete(_user(request)[0], rule_id)
        return Response(status=204)


class RulePreviewView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, rule_id: str) -> Response:
        return Response(_service().preview(_user(request)[0], rule_id))


class MatchFeedView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        params = page_params(request)
        unread = request.query_params.get("unread", "false").lower() == "true"
        rows, total = _service().feed(
            _user(request)[0], unread_only=unread, offset=params.offset, limit=params.page_size
        )
        return Response(paginated(rows, total, params))


class MatchReadView(APIView):
    """Mark one match (``{"id": ...}``) or all unread matches (empty body) as read."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        match_id = request.data.get("id") if isinstance(request.data, dict) else None
        updated = _service().mark_read(_user(request)[0], str(match_id) if match_id else None)
        return Response({"marked_read": updated})


class UnreadCountView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        return Response({"unread": _service().unread_count(_user(request)[0])})


class MatchedEventsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        return Response({"results": _service().matched_events(_user(request)[0])})
