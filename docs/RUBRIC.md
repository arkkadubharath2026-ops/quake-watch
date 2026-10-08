# Academic rubric mapping

Each rubric concept from ESD §19, and each "Academic Requirements Covered" item in the README,
mapped to where it is implemented and how it is demonstrated. Relational terms are mapped to their
honest ArangoDB equivalents. QuakeWatch does not claim SQL features it does not have.

Figures come from the development database on 2026-09-25 (live USGS feed + 30-day M2.5+
backfill) and from the committed test and benchmark runs.

## ESD §19 concepts

| Rubric concept | QuakeWatch implementation | Evidence |
|---|---|---|
| NoSQL DB | ArangoDB 3.12 (document + graph + search), ADR-001 | `docker-compose.yml`, `apps/core/arango/` |
| Schema / ERD | 16 document + 4 edge collections, JSON-schema validation rules, named graph `quakewatch_graph` | `apps/core/arango/schema.py`, ARCHITECTURE.md §3 |
| Primary key | deterministic `_key` (`usgs_<id>`) + unique persistent index `(source, source_event_id, merged_into)` + identity claims for historical ids | ADR-003, `qw_events_source_identity`, `event_identities` |
| Foreign key | edge `_from`/`_to` (event→region, event→network, user→rule, rule→event) and checked `event_key` / `user_id` references | `EDGE_DEFINITIONS`, graph traversal queries |
| 3NF wording | canonical event vs immutable revisions vs content-addressed raw payloads vs derived region and network entities; source values never overwritten by derived values | ARCHITECTURE.md "Relational rubric mapping", ADR-010 |
| Complex queries | 47 named AQL queries: 16 analytics aggregates, filtered/sorted/paginated search, geo radius + bbox, 2-hop graph traversals, percentiles, subqueries, ArangoSearch full text | `docs/AQL_QUERIES.md` (generated with live EXPLAIN plans) |
| Views | ArangoSearch view `events_search` (place + derived region, `text_en` analyzer, primary sort) | `EVENTS_SEARCH_VIEW_PROPERTIES`, Explorer "Place contains" |
| Trigger / procedure wording | none claimed. Equivalent logic is service code: the ingestion pipeline, the in-transaction alert observer and background jobs (`apps.jobs`) | `apps/ingestion/pipeline.py`, `apps/alerts/observer.py` |
| Transactions | stream transaction per record: canonical upsert + revision append + identity claims + edges + alert matches, with conflict retry | `apps/core/arango/transactions.py`, `IngestionPipeline._apply_in_txn`, ADR-003 |
| Indexes | persistent (incl. composite, array and covering with stored values), geo (GeoJSON), TTL, unique; every one justified by a query plan | `schema.py`, AQL_QUERIES.md index table, ADR-012 |
| 500+ records | 2,256 events, 2,278 revisions, 2,325 raw payloads, 2,256 + 2,256 edges, 120 regions, 12 networks, 57 ingestion runs | `manage.py backfill`, `/operations/` |
| CRUD | alert rules (create/read/update/delete + preview), saved searches, research snapshots (create/list/delete/export), notification read state | `/alerts/`, `/explorer/`, `/research/`; `tests/e2e/test_flows.py` |
| Performance | EXPLAIN checks for every named query; index before/after benchmark at 500 / 10k / 100k; a regression found and fixed (505 → 27 ms p50) | `docs/BENCHMARKS.md`, `TestQueryCatalog`, ADR-012 |
| Frontend | Django-rendered pages + Bootstrap 5 + vanilla JS islands, Leaflet maps, Chart.js charts with data tables | ADR-011, `docs/DESIGN_SYSTEM.md` |

## README "Academic Requirements Covered"

| Requirement | Where |
|---|---|
| Open-source NoSQL DBMS | ArangoDB Community (Docker image `arangodb:3.12.5`) |
| Schema and graph design | `schema.py`; graph traversal on Event Detail → Relationships |
| Front end ↔ back end ↔ database | pages call `/api/v1` (session + CSRF), which calls repositories and AQL. Exercised end to end in Playwright |
| Aggregation | `/analytics/`: time series, histograms, per-region and per-network stats, revision dynamics, time-to-reviewed percentiles |
| Geospatial queries | radius (`GEO_DISTANCE`), viewport (`GEO_CONTAINS`, antimeridian-aware), server-side clustering |
| Query optimisation | covering sort indexes + count subquery (ADR-012); `aql_catalog` fails if a plan stops using its index |
| Security | Security review with every finding fixed and regression-tested (`docs/SECURITY_REVIEW.md`); strict CSP with nonces; throttling and lockout; object-level authorisation; audit log; `check --deploy` clean |
| Testing | 601 unit/contract/resilience/integration/architecture tests (94 % coverage, real ArangoDB) + 58 browser E2E and accessibility tests + opt-in live USGS contract tests |
| Performance tuning | `docs/BENCHMARKS.md` (tuning history) |
| Dashboards / reports | Dashboard, Analytics, System Status, Operations; research exports (CSV/JSON/ZIP with SHA-256 manifest) |
| Accessibility | WCAG 2.2 AA audit (`docs/ACCESSIBILITY.md`) |
| GitHub repository and CI | `.github/workflows/ci.yml`: lint → unit → integration → e2e/a11y → dependency audit + deploy checks → container build |
| Demo-ready web application | `docker compose up -d --build`; `docs/RUNBOOK.md` |

## Example AQL questions (README)

The README asks for at least 15 meaningful queries. The catalogue holds 47, each with its
question, AQL, bind variables, chosen indexes and plan shape: see `docs/AQL_QUERIES.md`.

| # | README question | Named query |
|---|---|---|
| 1 | Strongest events in a date range | `events_strongest_in_range` |
| 2 | Events within a geographic radius | `events_within_radius`, `event_nearby_space_time` |
| 3 | Average magnitude by region | `analytics_avg_magnitude_by_region` |
| 4 | Magnitude distribution by month | `analytics_magnitude_by_month` |
| 5 | Deepest events | `events_deepest` |
| 6 | Tsunami-flagged events | `events_tsunami_flagged` |
| 7 | Reviewed vs automatic status counts | `analytics_status_counts` |
| 8 | Events with the most revisions | `analytics_most_revised` |
| 9 | Time from first seen to reviewed | `analytics_time_to_reviewed` (from origin and from first observation, on USGS timestamps) |
| 10 | Graph traversal from region to associated events | `event_graph_relationships` |
| 11 | Network-specific event statistics | `analytics_network_stats` |
| 12 | Significant events by period | `analytics_significant_by_week` |
| 13 | Watch-rule matched events | `alerts_matched_events_graph`, `alerts_user_feed` |
| 14 | Events whose magnitude changed beyond a threshold | `analytics_magnitude_changes` |
| 15 | Ingestion latency percentiles | `analytics_ingestion_latency` |
