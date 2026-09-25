"""Versioned JSON API routes (/api/v1/...)."""

from django.urls import path

from apps.alerts import api as alerts
from apps.analytics import api as analytics
from apps.earthquakes import api as events
from apps.operations import api as operations
from apps.research import api as research

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
    path("saved-searches", events.SavedSearchListView.as_view(), name="saved-searches"),
    path(
        "saved-searches/<str:search_id>",
        events.SavedSearchDetailView.as_view(),
        name="saved-search",
    ),
    path(
        "saved-searches/<str:search_id>/events",
        events.SavedSearchRunView.as_view(),
        name="saved-search-run",
    ),
    path("analytics/summary", analytics.summary, name="analytics-summary"),
    path("analytics/timeseries", analytics.timeseries, name="analytics-timeseries"),
    path("analytics/distributions", analytics.distributions, name="analytics-distributions"),
    path("analytics/breakdowns", analytics.breakdowns, name="analytics-breakdowns"),
    path("analytics/revisions", analytics.revisions, name="analytics-revisions"),
    path("analytics/latency", analytics.latency, name="analytics-latency"),
    path("alert-rules", alerts.RuleListView.as_view(), name="alert-rules"),
    path("alert-rules/<str:rule_id>", alerts.RuleDetailView.as_view(), name="alert-rule"),
    path(
        "alert-rules/<str:rule_id>/preview",
        alerts.RulePreviewView.as_view(),
        name="alert-rule-preview",
    ),
    path("alerts/matches", alerts.MatchFeedView.as_view(), name="alert-matches"),
    path("alerts/matches/read", alerts.MatchReadView.as_view(), name="alert-matches-read"),
    path("alerts/unread-count", alerts.UnreadCountView.as_view(), name="alert-unread-count"),
    path("alerts/matched-events", alerts.MatchedEventsView.as_view(), name="alert-matched-events"),
    path("research/snapshots", research.SnapshotListView.as_view(), name="snapshots"),
    path(
        "research/snapshots/<str:snapshot_id>",
        research.SnapshotDetailView.as_view(),
        name="snapshot",
    ),
    path(
        "research/snapshots/<str:snapshot_id>/export",
        research.SnapshotExportView.as_view(),
        name="snapshot-export",
    ),
    path("system/health", operations.health, name="system-health"),
    path("system/freshness", operations.freshness, name="system-freshness"),
    path("operations/overview", operations.overview, name="ops-overview"),
    path("operations/runs", operations.runs, name="ops-runs"),
    path("operations/dead-letters", operations.dead_letters, name="ops-dead-letters"),
    path("operations/diagnostics", operations.DiagnosticsView.as_view(), name="ops-diagnostics"),
    path("operations/sync", operations.TriggerSyncView.as_view(), name="ops-sync"),
    path("operations/backfill", operations.BackfillView.as_view(), name="ops-backfill"),
    path(
        "operations/dead-letters/<str:key>/retry",
        operations.RetryDeadLetterView.as_view(),
        name="ops-dead-letter-retry",
    ),
    path("operations/audit", operations.audit_log, name="ops-audit"),
]
