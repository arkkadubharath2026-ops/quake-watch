"""Analytics aggregations (FR-09). Every query is a registered :class:`NamedQuery`.

Windows are expressed as ``@since`` (ISO timestamp); all queries exclude merged records.
Derived statistics are labelled as such in the API; source values are never modified.
"""

from __future__ import annotations

from typing import Any

from arango.database import Database

from apps.core.arango import catalog
from apps.core.arango.catalog import NamedQuery
from apps.core.arango.query import run_query

SINCE = "2026-08-26T00:00:00.000Z"


def _q(
    name: str,
    question: str,
    aql: str,
    binds: dict[str, Any],
    indexes: tuple[str, ...] = (),
    features: tuple[str, ...] = ("aggregation",),
) -> NamedQuery:
    return catalog.register(
        NamedQuery(
            name=name,
            category="analytics",
            question=question,
            aql=aql,
            sample_binds=lambda: dict(binds),
            expected_indexes=indexes,
            features=features,
        )
    )


SUMMARY = _q(
    "analytics_dashboard_summary",
    "Situational summary: counts in the last 24 h / 7 d, strongest events, significant events.",
    """
    LET day = (FOR e IN events FILTER e.occurred_at >= @day FILTER e.merged_into == null
               RETURN e)
    LET week = (FOR e IN events FILTER e.occurred_at >= @week FILTER e.merged_into == null
                RETURN KEEP(e, "_key", "magnitude", "place", "occurred_at", "alert",
                            "significance", "tsunami", "depth_km", "status"))
    RETURN {
      count_24h: LENGTH(day),
      count_7d: LENGTH(week),
      m45_plus_7d: LENGTH(FOR e IN week FILTER e.magnitude >= 4.5 RETURN 1),
      strongest_24h: FIRST(FOR e IN day FILTER e.magnitude != null SORT e.magnitude DESC LIMIT 1
                           RETURN MERGE(KEEP(e, "magnitude", "place", "occurred_at", "depth_km"),
                                        {key: e._key})),
      strongest_7d: FIRST(FOR e IN week FILTER e.magnitude != null SORT e.magnitude DESC LIMIT 1
                          RETURN MERGE(UNSET(e, "_key"), {key: e._key})),
      significant_7d: (FOR e IN week
                         FILTER e.significance >= 600 OR e.alert != null OR e.tsunami
                         SORT e.significance DESC LIMIT 10
                         RETURN MERGE(UNSET(e, "_key"), {key: e._key})),
      reviewed_share_7d: LENGTH(week) == 0 ? null
        : LENGTH(FOR e IN week FILTER e.status == "reviewed" RETURN 1) / LENGTH(week)
    }
    """,
    {"day": SINCE, "week": SINCE},
    ("qw_events_occurred_at",),
    ("aggregation", "subqueries"),
)

TIMESERIES = _q(
    "analytics_daily_counts_by_band",
    "Events per day by magnitude band (activity timeline).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      LET band = e.magnitude == null ? "unknown" : e.magnitude < 2.5 ? "<2.5"
               : e.magnitude < 4.5 ? "2.5-4.5" : e.magnitude < 6 ? "4.5-6" : "6+"
      COLLECT day = SUBSTRING(e.occurred_at, 0, 10), b = band WITH COUNT INTO n
      SORT day
      RETURN {day: day, band: b, count: n}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

MAGNITUDE_HISTOGRAM = _q(
    "analytics_magnitude_histogram",
    "Magnitude distribution in 0.5 bins.",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null FILTER e.magnitude != null
      COLLECT bin = FLOOR(e.magnitude * 2) / 2 WITH COUNT INTO n
      SORT bin
      RETURN {bin: bin, count: n}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

DEPTH_HISTOGRAM = _q(
    "analytics_depth_histogram",
    "Depth distribution (shallow < 70 km, intermediate 70 to 300 km, deep > 300 km, 10 km bins).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null FILTER e.depth_km != null
      COLLECT bin = FLOOR(e.depth_km / 10) * 10 WITH COUNT INTO n
      SORT bin
      RETURN {bin: bin, count: n}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

SCATTER = _q(
    "analytics_magnitude_depth_scatter",
    "Magnitude vs depth sample for a scatter plot (bounded).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      FILTER e.magnitude != null AND e.depth_km != null
      SORT e.occurred_at DESC
      LIMIT @limit
      RETURN [e.magnitude, e.depth_km, e._key]
    """,
    {"since": SINCE, "limit": 2000},
    ("qw_events_occurred_at",),
    ("sort", "bounded sample"),
)

BY_REGION = _q(
    "analytics_avg_magnitude_by_region",
    "Event count and average/max magnitude by derived region (README Q3).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      COLLECT region = e.derived.region_name
      AGGREGATE n = LENGTH(1), avg_mag = AVERAGE(e.magnitude), max_mag = MAX(e.magnitude)
      SORT n DESC
      LIMIT @limit
      RETURN {region: region, count: n, avg_magnitude: ROUND(avg_mag * 100) / 100,
              max_magnitude: max_mag}
    """,
    {"since": SINCE, "limit": 20},
    ("qw_events_occurred_at",),
)

BY_MONTH = _q(
    "analytics_magnitude_by_month",
    "Magnitude distribution by month (README Q4).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null FILTER e.magnitude != null
      COLLECT month = SUBSTRING(e.occurred_at, 0, 7)
      AGGREGATE n = LENGTH(1), avg_mag = AVERAGE(e.magnitude), max_mag = MAX(e.magnitude),
                m45 = SUM(e.magnitude >= 4.5 ? 1 : 0)
      SORT month
      RETURN {month: month, count: n, avg_magnitude: ROUND(avg_mag * 100) / 100,
              max_magnitude: max_mag, m45_plus: m45}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

STATUS_COUNTS = _q(
    "analytics_status_counts",
    "Reviewed vs automatic status counts (README Q7).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      COLLECT status = e.status WITH COUNT INTO n
      RETURN {status: status, count: n}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

NETWORK_STATS = _q(
    "analytics_network_stats",
    "Per-network event statistics joined with network names via the graph (README Q11).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      COLLECT code = e.network
      AGGREGATE n = LENGTH(1), avg_mag = AVERAGE(e.magnitude), max_mag = MAX(e.magnitude),
                reviewed = SUM(e.status == "reviewed" ? 1 : 0)
      LET network = DOCUMENT("networks", code)
      SORT n DESC
      RETURN {network: code, name: network.name, count: n,
              avg_magnitude: ROUND(avg_mag * 100) / 100, max_magnitude: max_mag,
              reviewed_share: ROUND(reviewed / n * 1000) / 1000}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
    ("aggregation", "join"),
)

SIGNIFICANT_BY_WEEK = _q(
    "analytics_significant_by_week",
    "Significant events (significance ≥ 600, PAGER alert or tsunami flag) per ISO week "
    "(README Q12).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      FILTER e.significance >= 600 OR e.alert != null OR e.tsunami
      LET iso = DATE_ISOWEEKYEAR(e.occurred_at)
      COLLECT week = CONCAT(iso.year, "-W", RIGHT(CONCAT("0", iso.week), 2)) INTO members = e
      SORT week
      RETURN {week: week, count: LENGTH(members),
              strongest: MAX(members[*].magnitude)}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)

MOST_REVISED = _q(
    "analytics_most_revised",
    "Events with the most meaningful revisions (README Q8).",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null FILTER e.revision_count > 1
      SORT e.revision_count DESC, e.occurred_at DESC
      LIMIT @limit
      RETURN {key: e._key, revision_count: e.revision_count, magnitude: e.magnitude,
              place: e.place, occurred_at: e.occurred_at, status: e.status}
    """,
    {"since": SINCE, "limit": 15},
    ("qw_events_occurred_at",),
)

REVISION_FIELDS = _q(
    "analytics_revision_field_frequency",
    "How often each tracked field is revised (revision dynamics, PRD RQ1).",
    """
    FOR r IN event_revisions
      FILTER r.observed_at >= @since AND r.kind == "updated"
      FOR f IN r.changed_fields
        COLLECT field = f WITH COUNT INTO n
        SORT n DESC
        RETURN {field: field, count: n}
    """,
    {"since": SINCE},
    ("qw_revisions_observed_at",),
)

MAGNITUDE_CHANGES = _q(
    "analytics_magnitude_changes",
    "Revisions whose magnitude changed by at least a threshold (README Q14).",
    """
    FOR r IN event_revisions
      FILTER "magnitude" IN r.changed_fields[*]
      FILTER r.before.magnitude != null AND r.after.magnitude != null
      LET delta = r.after.magnitude - r.before.magnitude
      FILTER ABS(delta) >= @threshold
      SORT ABS(delta) DESC, r.observed_at DESC
      LIMIT @limit
      LET e = DOCUMENT("events", r.event_key)
      RETURN {key: r.event_key, revision_number: r.revision_number, observed_at: r.observed_at,
              before: r.before.magnitude, after: r.after.magnitude,
              delta: ROUND(delta * 100) / 100, place: e.place}
    """,
    {"threshold": 0.3, "limit": 20},
    ("qw_revisions_changed_fields",),
    ("array index", "join"),
)

TIME_TO_REVIEWED = _q(
    "analytics_time_to_reviewed",
    "Hours until USGS published an event as 'reviewed' (README Q9, RQ1). The review moment is the "
    "USGS update time of the first reviewed version, so gaps in QuakeWatch polling cannot inflate "
    "it. Reported from origin time (USGS clocks only) and from QuakeWatch's first observation.",
    """
    FOR r IN event_revisions
      FILTER "status" IN r.changed_fields[*] AND r.after.status == "reviewed"
      FILTER r.observed_at >= @since
      LET created = DOCUMENT("event_revisions", CONCAT(r.event_key, "_000001"))
      FILTER created != null
      LET from_origin = DATE_DIFF(r.state.occurred_at, r.source_updated_at, "h", true)
      LET from_first_seen = MAX([0, DATE_DIFF(created.observed_at, r.source_updated_at, "h", true)])
      COLLECT AGGREGATE n = LENGTH(1), max_origin = MAX(from_origin)
        INTO values = {origin: from_origin, seen: from_first_seen}
      LET origin = values[*].origin
      LET seen = values[*].seen
      RETURN {count: n,
              origin_p50_hours: n == 0 ? null : PERCENTILE(origin, 50),
              origin_p90_hours: n == 0 ? null : PERCENTILE(origin, 90),
              origin_max_hours: max_origin,
              first_seen_p50_hours: n == 0 ? null : PERCENTILE(seen, 50),
              first_seen_p90_hours: n == 0 ? null : PERCENTILE(seen, 90)}
    """,
    {"since": SINCE},
    ("qw_revisions_changed_fields",),
    ("array index", "percentiles"),
)

INGESTION_LATENCY = _q(
    "analytics_ingestion_latency",
    "Seconds from origin time to first observation by QuakeWatch, for events that occurred after "
    "live monitoring began (README Q15, derived value).",
    """
    LET monitoring_start = FIRST(
      FOR r IN ingestion_runs OPTIONS {indexHint: "qw_runs_kind_started"}
        FILTER r.kind == "feed_sync" AND r.status IN ["succeeded", "partial"]
        SORT r.kind ASC, r.started_at ASC
        LIMIT 1
        RETURN r.started_at
    )
    LET since = monitoring_start == null ? @since : MAX([@since, monitoring_start])
    LET latencies = (
      FOR e IN events
        FILTER e.occurred_at >= since FILTER e.merged_into == null
        FILTER e.derived.first_seen_via == "feed" AND e.derived.first_seen_latency_s != null
        RETURN e.derived.first_seen_latency_s
    )
    RETURN {
      monitoring_start: monitoring_start,
      count: LENGTH(latencies),
      p50_s: LENGTH(latencies) == 0 ? null : PERCENTILE(latencies, 50),
      p90_s: LENGTH(latencies) == 0 ? null : PERCENTILE(latencies, 90),
      p99_s: LENGTH(latencies) == 0 ? null : PERCENTILE(latencies, 99),
      min_s: MIN(latencies), max_s: MAX(latencies)
    }
    """,
    {"since": SINCE},
    ("qw_runs_kind_started", "qw_events_occurred_at"),
    ("percentiles", "subqueries"),
)

REVISION_COUNT_DISTRIBUTION = _q(
    "analytics_revision_count_distribution",
    "Distribution of revision counts per event.",
    """
    FOR e IN events
      FILTER e.occurred_at >= @since FILTER e.merged_into == null
      COLLECT revisions = e.revision_count WITH COUNT INTO n
      SORT revisions
      RETURN {revisions: revisions, events: n}
    """,
    {"since": SINCE},
    ("qw_events_occurred_at",),
)


class AnalyticsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def run(self, query: NamedQuery, binds: dict[str, Any]) -> list[Any]:
        return run_query(self.db, query.name, query.aql, binds).rows

    def first(self, query: NamedQuery, binds: dict[str, Any]) -> Any:
        rows = self.run(query, binds)
        return rows[0] if rows else None
