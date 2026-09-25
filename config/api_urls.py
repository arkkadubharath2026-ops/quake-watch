"""Versioned JSON API routes (/api/v1/...)."""

from django.urls import path

from apps.analytics import api as analytics
from apps.earthquakes import api as events
from apps.operations import api as operations

app_name = "api"

# Event identifiers are canonical keys (usgs_<id>) or any USGS event id (current or historical).
ID = "<str:identifier>"

urlpatterns = [
    path("events", events.event_list, name="event-list"),
    path("events/map", events.event_map, name="event-map"),
    path(f"events/{ID}", events.event_detail, name="event-detail"),
    path(f"events/{ID}/revisions", events.event_revisions, name="event-revisions"),
    path(f"events/{ID}/provenance", events.event_provenance, name="event-provenance"),
    path(f"events/{ID}/relationships", events.event_relationships, name="event-relationships"),
    path(f"events/{ID}/enrich", events.EventEnrichView.as_view(), name="event-enrich"),
    path("analytics/summary", analytics.summary, name="analytics-summary"),
    path("analytics/timeseries", analytics.timeseries, name="analytics-timeseries"),
    path("analytics/distributions", analytics.distributions, name="analytics-distributions"),
    path("analytics/breakdowns", analytics.breakdowns, name="analytics-breakdowns"),
    path("analytics/revisions", analytics.revisions, name="analytics-revisions"),
    path("analytics/latency", analytics.latency, name="analytics-latency"),
    path("system/health", operations.health, name="system-health"),
    path("system/freshness", operations.freshness, name="system-freshness"),
    path("operations/overview", operations.overview, name="ops-overview"),
    path("operations/runs", operations.runs, name="ops-runs"),
    path("operations/dead-letters", operations.dead_letters, name="ops-dead-letters"),
    path("operations/diagnostics", operations.DiagnosticsView.as_view(), name="ops-diagnostics"),
]
