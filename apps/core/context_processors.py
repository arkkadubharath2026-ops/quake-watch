from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, Any]:
    return {
        "APP_VERSION": settings.QUAKEWATCH.app_version,
        "DATA_ATTRIBUTION": "Earthquake data courtesy of the U.S. Geological Survey (USGS).",
    }
