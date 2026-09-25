"""Page views: thin shells rendered by Django; interactive data is fetched from /api/v1 by the
page's static script (ADR-011). Event Detail renders its overview on the server so that missing
events produce a real 404 and the core facts are readable without JavaScript."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from apps.core.arango.client import get_db
from apps.core.errors import DatabaseUnavailable, NotFound
from apps.earthquakes.repository import EventRepository
from apps.earthquakes.services import EventQueryService


def _page(request: HttpRequest, template: str, nav: str, **context: object) -> HttpResponse:
    return render(request, template, {"nav_active": nav, **context})


@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/dashboard.html", "dashboard")


@require_GET
def live_map(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/map.html", "map")


@require_GET
def explorer(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/explorer.html", "explorer")


@require_GET
def event_detail(request: HttpRequest, identifier: str) -> HttpResponse:
    service = EventQueryService(EventRepository(get_db()))
    try:
        event = service.detail(identifier)
    except NotFound as exc:
        raise Http404(str(exc)) from exc
    except DatabaseUnavailable:
        return render(request, "503.html", status=503)
    if event["key"] != identifier:  # historical/raw USGS id → canonical URL
        return redirect("pages:event", identifier=event["key"])
    source = event["source"]
    return _page(request, "pages/event_detail.html", "explorer", event=event, source=source)


@require_GET
def analytics(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/analytics.html", "analytics")


@require_GET
@login_required
def alerts(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/alerts.html", "alerts")


@require_GET
@login_required
def research(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/research.html", "research")


@require_GET
def status(request: HttpRequest) -> HttpResponse:
    app = settings.QUAKEWATCH
    return _page(
        request,
        "pages/status.html",
        "status",
        degraded_minutes=app.freshness_degraded_minutes,
        stale_minutes=app.freshness_stale_minutes,
    )


@require_GET
@login_required
def operations(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        raise PermissionDenied("Operations are available to staff only.")
    return _page(request, "pages/operations.html", "operations")


@require_GET
def about(request: HttpRequest) -> HttpResponse:
    return _page(request, "pages/about.html", "about")
