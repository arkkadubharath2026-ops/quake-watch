from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest

# (id, label, url name, audience): audience is "all", "user" (signed in) or "staff".
_NAV = (
    ("dashboard", "Dashboard", "pages:dashboard", "all"),
    ("map", "Live Map", "pages:map", "all"),
    ("explorer", "Explorer", "pages:explorer", "all"),
    ("analytics", "Analytics", "pages:analytics", "all"),
    ("alerts", "Alerts", "pages:alerts", "user"),
    ("research", "Research Lab", "pages:research", "user"),
    ("status", "System Status", "pages:status", "all"),
    ("operations", "Operations", "pages:operations", "staff"),
    ("about", "About", "pages:about", "all"),
)


def _visible(audience: str, request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    if audience == "user":
        return bool(user and user.is_authenticated)
    if audience == "staff":
        return bool(user and user.is_authenticated and user.is_staff)
    return True


def site(request: HttpRequest) -> dict[str, Any]:
    return {
        "APP_VERSION": settings.QUAKEWATCH.resolved_app_version,
        "DATA_ATTRIBUTION": "Earthquake data courtesy of the U.S. Geological Survey (USGS).",
        "NAV_ITEMS": [
            {"id": nav_id, "label": label, "url": url}
            for nav_id, label, url, audience in _NAV
            if _visible(audience, request)
        ],
    }
