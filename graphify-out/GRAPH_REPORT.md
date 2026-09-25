# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 133 files · ~57,143 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 4, .geojson 3, .example 1)

## Summary
- 1634 nodes · 3731 edges · 113 communities (93 shown, 20 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 218 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5faec556`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- run_in_transaction
- to_iso
- Django Security Best Practices
- operations/api.py
- metrics.py
- django_apps
- client.py
- http.py
- Django + Celery Async Task Patterns
- logging.py
- Frontend Accessibility Patterns
- ruff_on_edit.py
- sync
- a11y-architect.md
- Review Priorities
- Architecture Decision Records
- Review Priorities
- Security Reviewer
- test_boundaries.py
- health.py
- QuakeWatch — Engineering System Design (ESD)
- Document Collections
- schema.py
- QuakeWatch verification gate
- Hunt Targets
- QuakeWatch — instructions for Claude
- test_health.py
- 10. Frontend Design
- QuakeWatch — Product Requirements Document (PRD)
- 16. Testing Strategy
- 4. User Problems and Product Responses
- StandardDatabase
- 13. Reliability
- 11. Competitive Positioning
- 7. Core User Journeys
- 9. Non-Functional Requirements
- ADR-001: ArangoDB as the primary database
- ADR-002: Modular Django monolith with background workers
- ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB
- analytics/api.py
- ARCHITECTURE.md
- 6. Constraints and Indexes
- 12. Research-Paper Potential
- 3. Target Users
- 6. Scope
- EventFilter
- 15. Observability
- 20. Research Extensions
- 4. Source Integration
- 13. Success Metrics
- test_query_layer.py
- CircuitBreaker
- 18. Deployment Profiles
- 3. Technology Stack
- entrypoint.sh
- quakewatch
- IngestionPipeline
- test_geo.py
- locks.py
- revision_policy.py
- test_ingestion_services.py
- usgs
- test_tasks_and_commands.py
- normalizer.py
- usgs_models.py
- CanonicalEventInput
- ValidationFailed
- .__init__
- pipeline.py
- build_usgs_client
- ingestion/services.py
- load_fixture
- typing
- test_api.py
- run_query
- AppSettings
- IngestionRepository
- Analytics
- migrate.py
- FakeClock
- earthquakes/repository.py
- context_processors.py
- Queries (36)
- aql_catalog.py
- sync_feed.py
- env.py
- OperationsRepository
- .handle
- os
- Search
- Command
- Operations
- RecordingObserver
- Maintenance
- Dependencies and why each exists
- pytest_collection_modifyitems

## God Nodes (most connected - your core abstractions)
1. `CircuitBreaker` - 57 edges
2. `IngestionPipeline` - 44 edges
3. `to_iso()` - 41 edges
4. `run_query()` - 40 edges
5. `RunRepository` - 38 edges
6. `UsgsClient` - 37 edges
7. `BackfillService` - 37 edges
8. `get_db()` - 33 edges
9. `EventFilter` - 31 edges
10. `sync()` - 29 edges

## Surprising Connections (you probably didn't know these)
- `29. `event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/AQL_QUERIES.md → apps/earthquakes/api.py
- `Index justification (ESD §6)` --references--> `event_revisions()`  [INFERRED]
  docs/AQL_QUERIES.md → apps/earthquakes/api.py
- ``event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/ESD.md → apps/earthquakes/api.py
- ``event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/ESD.md → apps/earthquakes/api.py
- `Runtime (Python)` --references--> `CanonicalEventInput`  [INFERRED]
  docs/DEPENDENCIES.md → apps/earthquakes/domain.py

## Import Cycles
- None detected.

## Communities (113 total, 20 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.04
Nodes (49): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Academic Requirements Covered, Alerts / Watch Rules, Analytics, Competitor / Reference Systems (+41 more)

### Community 1 - "run_in_transaction"
Cohesion: 0.06
Nodes (31): _abort_quietly(), _is_retryable(), StandardDatabase, T, Stream-transaction helpers. :func:`run_in_transaction` executes a unit of work…, Run ``work`` atomically; retry on write-write conflicts.…, run_in_transaction(), arango_exceptions (+23 more)

### Community 2 - "to_iso"
Cohesion: 0.16
Nodes (12): from_epoch_ms(), from_iso(), datetime, Time utilities. Timestamps are persisted as fixed-width ISO-8601 UTC strings…, to_iso(), utc_now(), Human-readable query summary for the explorer and exports., Any (+4 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "operations/api.py"
Cohesion: 0.06
Nodes (60): apps_analytics, error_body(), exception_handler(), page_params(), PageParams, paginated(), Any, Exception (+52 more)

### Community 5 - "metrics.py"
Cohesion: 0.08
Nodes (39): counters(), _counters_key(), incr(), _index_key(), observe(), percentile(), ping(), Exception (+31 more)

### Community 6 - "django_apps"
Cohesion: 0.07
Nodes (19): AccountsConfig, AppConfig, AlertsConfig, AppConfig, AnalyticsConfig, AppConfig, CoreConfig, AppConfig (+11 more)

### Community 7 - "client.py"
Cohesion: 0.16
Nodes (23): _cached_db(), _connect(), database_name(), drop_database(), ensure_database(), get_client(), get_db(), StandardDatabase (+15 more)

### Community 8 - "http.py"
Cohesion: 0.12
Nodes (18): CircuitOpen, An upstream source (e.g. USGS) failed. ``transient`` drives retry decisions., UpstreamError, backoff_delay(), Resilience primitives: jittered exponential backoff and a shared circuit…, Full-jitter exponential backoff for retry ``attempt`` (1-based). An upstream…, Any, Response (+10 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - "logging.py"
Cohesion: 0.10
Nodes (26): apps_core, CorrelationIdMiddleware, new_correlation_id(), HttpRequest, Request middleware: correlation IDs and request timing/outcome logging +…, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs., Log endpoint/duration/outcome for every request and feed API latency metrics., RequestTimingMiddleware (+18 more)

### Community 11 - "Frontend Accessibility Patterns"
Cohesion: 0.09
Nodes (22): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Checklist, Complete Accessible Form (+14 more)

### Community 12 - "ruff_on_edit.py"
Cohesion: 0.13
Nodes (13): PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, pathlib, fetch(), main() (+5 more)

### Community 13 - "sync"
Cohesion: 0.16
Nodes (11): Any, T, Narrow python-arango's ``Result[T]`` union for APIs that never return None. We…, Like :func:`sync` for APIs where None is a legitimate answer (e.g.…, sync(), sync_optional(), now_iso(), dead_letter_key() (+3 more)

### Community 14 - "a11y-architect.md"
Cohesion: 0.11
Nodes (17): 1. Perceivable (Information must be presentable), 2. Operable (Interface components must be usable), 3. Understandable (Information must be clear), 4. Robust (Content must be compatible), Accessibility Decision Record Template, Anti-Patterns, Example: Accessible Search Component, Examples (+9 more)

### Community 15 - "Review Priorities"
Cohesion: 0.12
Nodes (15): Approval Criteria, CRITICAL — Migration Safety, CRITICAL — ORM Correctness, CRITICAL — Security, Diagnostic Commands, Framework-Specific Checks, HIGH — Code Quality, HIGH — DRF Patterns (+7 more)

### Community 16 - "Architecture Decision Records"
Cohesion: 0.12
Nodes (15): ADR Directory Structure, ADR Format, ADR Index Format, ADR Lifecycle, Architecture Decision Records, Capturing a New ADR, Categories of Decisions Worth Recording, Decision Detection Signals (+7 more)

### Community 17 - "Review Priorities"
Cohesion: 0.13
Nodes (14): Approval Criteria, CRITICAL — Error Handling, CRITICAL — Security, Diagnostic Commands, Framework Checks, HIGH — Code Quality, HIGH — Concurrency, HIGH — Pythonic Patterns (+6 more)

### Community 18 - "Security Reviewer"
Cohesion: 0.13
Nodes (14): 1. Initial Scan, 2. OWASP Top 10 Check, 3. Code Pattern Review, Analysis Commands, Common False Positives, Core Responsibilities, Emergency Response, Key Principles (+6 more)

### Community 19 - "test_boundaries.py"
Cohesion: 0.37
Nodes (13): ast, _imports(), _is_repository(), _pure_modules(), parametrize, Path, _python_files(), Architecture fitness tests: enforce module boundaries from CLAUDE.md /… (+5 more)

### Community 20 - "health.py"
Cohesion: 0.23
Nodes (12): ping(), Readiness probe: can we reach the server and our database?, DatabaseUnavailable, live(), HttpRequest, Liveness / readiness probes (ESD §15). ``/health/live`` — the process is up (no…, ready(), django_views_decorators_cache (+4 more)

### Community 21 - "QuakeWatch — Engineering System Design (ESD)"
Cohesion: 0.15
Nodes (13): 11. Alert Engine, 12. Research Data Layer, 14. Security, 17. CI/CD, 19. Academic Rubric Mapping, 1. Engineering Strategy, 21. Architecture Decision Records, 22. External References (+5 more)

### Community 22 - "Document Collections"
Cohesion: 0.15
Nodes (13): 5. ArangoDB Data Model, `alert_matches`, `alert_rules`, `dead_letters`, Document Collections, Edge Collections, `event_revisions`, `events` (+5 more)

### Community 23 - "schema.py"
Cohesion: 0.29
Nodes (8): collection_spec(), CollectionSpec, IndexSpec, _nullable(), _p(), Any, Declarative ArangoDB schema for QuakeWatch (ESD §5, §6). This module is the…, _ts()

### Community 24 - "QuakeWatch verification gate"
Cohesion: 0.18
Nodes (10): 0. Infrastructure up, 1. Lint + format, 2. Types, 3. Django system checks (incl. deploy checks with production settings), 4. Tests (real ArangoDB — integration tests use an isolated `<db>_test` database), 5. Architectural boundaries, 6. Security, 7. Graph refresh + impact check (+2 more)

### Community 25 - "Hunt Targets"
Cohesion: 0.20
Nodes (9): 1. Empty Catch Blocks, 2. Inadequate Logging, 3. Dangerous Fallbacks, 4. Error Propagation Issues, 5. Missing Error Handling, Hunt Targets, Output Format, Prompt Defense Baseline (+1 more)

### Community 26 - "QuakeWatch — instructions for Claude"
Cohesion: 0.22
Nodes (8): Architecture (see docs/ARCHITECTURE.md), Boundary rules (enforced by tests/architecture), Commands, graphify, Project tooling (.claude/), QuakeWatch — instructions for Claude, Safety wording, Standing instructions from the project owner (always follow)

### Community 27 - "test_health.py"
Cohesion: 0.36
Nodes (8): django_test, Client, StandardDatabase, test_inbound_request_id_propagates(), test_live_is_always_ok(), test_malformed_request_id_replaced(), test_ready_checks_dependencies(), test_ready_reports_schema_drift()

### Community 28 - "10. Frontend Design"
Cohesion: 0.25
Nodes (8): 10. Frontend Design, Analytics, Dashboard, Event Detail, Explorer, Live Map, Operations, Research Lab

### Community 29 - "QuakeWatch — Product Requirements Document (PRD)"
Cohesion: 0.25
Nodes (8): 10. Information Architecture, 14. Risks and Mitigations, 15. Official References, 1. Product Vision, 2. Why This Product Should Exist, 5. Product Principles, 8. Functional Requirements, QuakeWatch — Product Requirements Document (PRD)

### Community 30 - "16. Testing Strategy"
Cohesion: 0.29
Nodes (7): 16. Testing Strategy, Contract, End-to-End, Integration, Performance, Resilience, Unit

### Community 31 - "4. User Problems and Product Responses"
Cohesion: 0.29
Nodes (7): 4. User Problems and Product Responses, P1 — Data is available but fragmented, P2 — Earthquake records change after first publication, P3 — Maps alone are not enough, P4 — Alerts can be opaque, P5 — Research datasets are difficult to reproduce, P6 — Data trust is invisible

### Community 32 - "StandardDatabase"
Cohesion: 0.12
Nodes (18): api_db(), body(), Any, Client, fixture, MonkeyPatch, parametrize, StandardDatabase (+10 more)

### Community 33 - "13. Reliability"
Cohesion: 0.33
Nodes (6): 13. Reliability, Circuit Breaker, Dead Letters, Idempotency, Retries, Timeouts

### Community 34 - "11. Competitive Positioning"
Cohesion: 0.33
Nodes (6): 11. Competitive Positioning, EMSC LastQuake, PAGER / ShakeMap, ShakeAlert, USGS, USGS ENS

### Community 35 - "7. Core User Journeys"
Cohesion: 0.33
Nodes (6): 7. Core User Journeys, A. What is happening now?, B. Find earthquakes matching a condition, C. Watch an area, D. See how an event changed, E. Create a research dataset

### Community 36 - "9. Non-Functional Requirements"
Cohesion: 0.33
Nodes (6): 9. Non-Functional Requirements, Observability, Performance, Reliability, Reproducibility, Security

### Community 37 - "ADR-001: ArangoDB as the primary database"
Cohesion: 0.40
Nodes (4): ADR-001: ArangoDB as the primary database, Consequences, Context, Decision

### Community 38 - "ADR-002: Modular Django monolith with background workers"
Cohesion: 0.40
Nodes (4): ADR-002: Modular Django monolith with background workers, Consequences, Context, Decision

### Community 39 - "ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB"
Cohesion: 0.40
Nodes (4): ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB, Consequences, Context, Decision

### Community 40 - "analytics/api.py"
Cohesion: 0.12
Nodes (25): breakdowns(), distributions(), latency(), api_view, Request, Response, Analytics API (FR-09). All windows are ``?days=N`` (1..3660, default 30)., revisions() (+17 more)

### Community 42 - "6. Constraints and Indexes"
Cohesion: 0.40
Nodes (5): 6. Constraints and Indexes, `alert_rules`, `event_revisions`, `events`, `ingestion_runs`

### Community 43 - "12. Research-Paper Potential"
Cohesion: 0.40
Nodes (5): 12. Research-Paper Potential, RQ1 — Event Revision Dynamics, RQ2 — Multi-Source Latency and Consistency, RQ3 — Revision-Likelihood Modeling, RQ4 — Spatiotemporal Sequence Characterization

### Community 44 - "3. Target Users"
Cohesion: 0.40
Nodes (5): 3. Target Users, Administrators, Disaster-management learners and analysts, General users, Students and researchers

### Community 45 - "6. Scope"
Cohesion: 0.40
Nodes (5): 6. Scope, MVP, Out of Scope, Research Track, Version 1.1

### Community 46 - "EventFilter"
Cohesion: 0.17
Nodes (8): EventFilter, EventQueryService, EventReader, present_event(), Any, Protocol, Event query services (pure: no HTTP framework or driver imports). Presentation…, _title()

### Community 47 - "15. Observability"
Cohesion: 0.50
Nodes (4): 15. Observability, Health Endpoints, Metrics, Structured Log Fields

### Community 48 - "20. Research Extensions"
Cohesion: 0.50
Nodes (4): 20. Research Extensions, A. Multi-Source Concordance, B. Revision Intelligence, C. Spatiotemporal Graph

### Community 49 - "4. Source Integration"
Cohesion: 0.50
Nodes (4): 4.1 USGS Summary Feed Adapter, 4.2 Catalog API Adapter, 4.3 Detail Feed Adapter, 4. Source Integration

### Community 50 - "13. Success Metrics"
Cohesion: 0.50
Nodes (4): 13. Success Metrics, Academic, Product, Research Readiness

### Community 51 - "test_query_layer.py"
Cohesion: 0.14
Nodes (14): BreakerState, classify(), Freshness, FreshnessService, Any, datetime, Protocol, Source freshness (ADR-004): is the stored data current, and is the upstream… (+6 more)

### Community 52 - "CircuitBreaker"
Cohesion: 0.22
Nodes (11): CircuitBreaker, BaseTransport, make_client(), Exception, parametrize, Request, Response, sequence() (+3 more)

### Community 53 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 54 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

### Community 69 - "IngestionPipeline"
Cohesion: 0.23
Nodes (18): IngestionPipeline, count(), feature(), Any, parametrize, StandardDatabase, Ingestion pipeline against a real ArangoDB: idempotency, revisions, identity,…, Reviewer scenario: feed sees preferred id a, backfill sees b, for the same… (+10 more)

### Community 70 - "test_geo.py"
Cohesion: 0.08
Nodes (23): BoundingBox, haversine_km(), InvalidGeometry, Geodesic helpers (pure). Distances use the haversine formula on a spherical…, Viewport box. ``west > east`` means the box crosses the antimeridian., Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n —…, GeoJSON polygon rings (lon, lat), split at the antimeridian when needed., Approximate fraction of the globe covered (for choosing clustering granularity). (+15 more)

### Community 71 - "locks.py"
Cohesion: 0.15
Nodes (14): job_lock(), Distributed job locks on Redis (prevents overlapping scheduled runs of the same…, Yield True if the lock was acquired; the body should skip work when False., Any, recover(), run_backfill(), sync_feed(), ADR-004: Polling and freshness strategy (+6 more)

### Community 72 - "revision_policy.py"
Cohesion: 0.15
Nodes (21): apps_ingestion, diff(), field_changed(), FieldChange, FieldRule, _numeric_changed(), Any, Versioned meaningful-revision policy (ESD §8) (pure). A *revision* is recorded… (+13 more)

### Community 73 - "test_ingestion_services.py"
Cohesion: 0.22
Nodes (8): ingestion_runs + backfill_jobs bookkeeping (outside the per-record…, RunRepository, FeedSyncService, StandardDatabase, Scheduled synchronisation of a USGS summary feed (FR-01)., Feed sync, backfill and enrichment services on real ArangoDB with a simulated…, TestFeedSync, TestOperationalRecovery

### Community 74 - "usgs"
Cohesion: 0.19
Nodes (14): EnrichmentService, Lazy detail-feed enrichment (ESD §4.3). Failure never affects the base event…, FakeCatalog, Any, datetime, MonkeyPatch, parametrize, Request (+6 more)

### Community 75 - "test_tasks_and_commands.py"
Cohesion: 0.15
Nodes (15): BackfillRequest, django_core_management, Handler, io, fake_usgs(), fixture, MonkeyPatch, StandardDatabase (+7 more)

### Community 76 - "normalizer.py"
Cohesion: 0.08
Nodes (31): _csv(), normalize_feature(), reject(), parse_feed(), ParsedFeed, payload_hash(), Any, USGS GeoJSON → :class:`CanonicalEventInput` (pure). A feed is parsed in two… (+23 more)

### Community 77 - "usgs_models.py"
Cohesion: 0.21
Nodes (15): _Lenient, BaseModel, Strict contract for USGS GeoJSON payloads (summary feed, catalog query, detail…, Top level only; features are validated one by one so a bad record never sinks a…, UsgsCatalogCount, UsgsDetailFeature, UsgsDetailProperties, UsgsFeature (+7 more)

### Community 78 - "CanonicalEventInput"
Cohesion: 0.09
Nodes (18): CanonicalEventInput, event_key(), is_important(), Any, BaseModel, datetime, field_validator, model_validator (+10 more)

### Community 79 - "ValidationFailed"
Cohesion: 0.16
Nodes (9): ValidationFailed, number(), text(), timestamp(), Any, Deterministic, JSON-safe representation (only set fields; sorted keys)., Parse query parameters (strings) or a canonical dict; raise ValidationFailed on…, 7. Query & API layer (L3) (+1 more)

### Community 81 - "pipeline.py"
Cohesion: 0.11
Nodes (22): NormalizedRecord, _event_doc(), EventChange, EventObserver, unit(), _pick_primary(), Any, Database (+14 more)

### Community 82 - "build_usgs_client"
Cohesion: 0.13
Nodes (16): Conflict, PermissionDenied, Exception, QuakeWatchError, build_usgs_client(), Command, _date(), Any (+8 more)

### Community 83 - "ingestion/services.py"
Cohesion: 0.14
Nodes (19): NotFound, IngestionStats, BackfillInterrupted, BackfillService, _correlation_id(), enrichment_is_stale(), _error_dict(), Any (+11 more)

### Community 84 - "load_fixture"
Cohesion: 0.28
Nodes (5): load_fixture(), TestCatalogAndDetail, timedelta, feed_doc(), fixture

### Community 85 - "typing"
Cohesion: 0.12
Nodes (23): _q(), Analytics aggregations (FR-09). Every query is a registered…, Analytics services: parameter validation, windowing, short-lived caching…, apps_core_arango, all_queries(), get(), NamedQuery, Registry of named AQL queries. Static queries are declared once as… (+15 more)

### Community 86 - "test_api.py"
Cohesion: 0.13
Nodes (20): Upstream payload does not match the expected contract., SourceSchemaError, FetchResult, ResilientHttpClient, CatalogCount, DetailResult, _fdsn_time(), datetime (+12 more)

### Community 87 - "run_query"
Cohesion: 0.22
Nodes (7): QueryResult, run_query(), EventRepository, Any, Database, Compact points ``[key, lat, lon, mag, depth, occurred_at]``; flag if over the…, Server-side grid clustering for dense viewports (bounded result size).

### Community 88 - "AppSettings"
Cohesion: 0.18
Nodes (6): BaseSettings, AppSettings, field_validator, model_validator, Tests always run against an isolated ``<db>_test`` database., TestSettingsValidation

### Community 89 - "IngestionRepository"
Cohesion: 0.12
Nodes (8): IngestionRepository, KnownEvent, Database, Fast-path lookup (unique index) of current payload hashes by preferred id., Live canonical events claimed by any of ``ids`` (primary-key lookups only).…, Claim (or re-point) ids for an existing live event., Mark ``loser`` merged into ``primary`` and move everything identity-related…, Execute every write for one record in a single multi-collection AQL statement.…

### Community 90 - "Analytics"
Cohesion: 0.12
Nodes (17): 10. `analytics_most_revised`, 11. `analytics_network_stats`, 12. `analytics_revision_count_distribution`, 13. `analytics_revision_field_frequency`, 14. `analytics_significant_by_week`, 15. `analytics_status_counts`, 16. `analytics_time_to_reviewed`, 1. `analytics_avg_magnitude_by_region` (+9 more)

### Community 91 - "migrate.py"
Cohesion: 0.26
Nodes (12): applied_version(), apply_schema(), _migrate_v2_identity_claims(), MigrationReport, _normalize_declared(), _normalize_existing(), Any, StandardDatabase (+4 more)

### Community 92 - "FakeClock"
Cohesion: 0.18
Nodes (7): breaker(), clock(), FakeClock, fixture, MonkeyPatch, TestCircuitBreaker, __getattr__()

### Community 93 - "earthquakes/repository.py"
Cohesion: 0.26
Nodes (7): compile_filter(), CompiledQuery, Read-side persistence for events: search, detail, revisions, map, graph…, search_aql(), _variant(), _with_page(), TestSearchCompilation

### Community 94 - "context_processors.py"
Cohesion: 0.33
Nodes (5): Any, HttpRequest, site(), django_conf, django_http

### Community 95 - "Queries (36)"
Cohesion: 0.17
Nodes (12): 17. `event_resolve_id`, 18. `event_nearby_space_time`, 19. `event_graph_relationships`, 27. `event_raw_payload`, 28. `ingestion_runs_by_ids`, 29. `event_revisions`, Detail, Geo (+4 more)

### Community 96 - "aql_catalog.py"
Cohesion: 0.22
Nodes (9): explain(), indexes_used(), collect(), Any, Database, Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics…, Index names (or types) used by a plan, including traversal edge indexes., Generate docs/AQL_QUERIES.md from the named-query catalog with live EXPLAIN… (+1 more)

### Community 97 - "sync_feed.py"
Cohesion: 0.22
Nodes (7): Command, Any, BaseCommand, CommandParser, configured_observers(), Registry of ingestion observers (dependency inversion: ingestion never imports…, django_utils_module_loading

### Community 101 - "env.py"
Cohesion: 0.22
Nodes (7): Typed, validated application configuration loaded from environment / .env. All…, Django settings for QuakeWatch. Values come from :mod:`config.env` (typed,…, Test settings: forces QW_ENV=test so ArangoDB uses the isolated ``<db>_test``…, django_utils_csp, enum, functools, pydantic_settings

### Community 103 - "OperationsRepository"
Cohesion: 0.31
Nodes (3): OperationsRepository, Any, Database

### Community 104 - ".handle"
Cohesion: 0.36
Nodes (5): Command, _index_table(), Any, BaseCommand, CommandParser

### Community 105 - "os"
Cohesion: 0.25
Nodes (4): Celery application. Beat schedule is defined in apps.ingestion.schedule., django_core_asgi, django_core_wsgi, os

### Community 106 - "Search"
Cohesion: 0.25
Nodes (8): 30. `events_deepest`, 31. `events_in_viewport`, 32. `events_location_text`, 33. `events_recent_strong`, 34. `events_strongest_in_range`, 35. `events_tsunami_flagged`, 36. `events_within_radius`, Search

### Community 107 - "Command"
Cohesion: 0.33
Nodes (4): Command, Any, BaseCommand, CommandParser

### Community 108 - "Operations"
Cohesion: 0.40
Nodes (5): 23. `ops_dead_letters`, 24. `ops_latest_run`, 25. `ops_recent_runs`, 26. `ops_run_stats`, Operations

### Community 109 - "RecordingObserver"
Cohesion: 0.40
Nodes (3): Database, RecordingObserver, on_event()

### Community 110 - "Maintenance"
Cohesion: 0.50
Nodes (4): 20. `ingest_repoint_claims`, 21. `ingest_resolve_dead_letters`, 22. `runs_abandon_stale`, Maintenance

### Community 111 - "Dependencies and why each exists"
Cohesion: 0.50
Nodes (4): Dependencies and why each exists, Development / test, Frontend (vendored under `static/vendor`, no build step, no CDN at runtime), Runtime (Python)

### Community 112 - "pytest_collection_modifyitems"
Cohesion: 0.67
Nodes (3): Config, Item, pytest_collection_modifyitems()

## Knowledge Gaps
- **346 isolated node(s):** `entrypoint.sh script`, `quakewatch`, `Prompt Defense Baseline`, `Your Role`, `Step 1: Contextual Discovery` (+341 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 629 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuakeWatch Architecture` connect `run_in_transaction` to `ARCHITECTURE.md`, `logging.py`, `ValidationFailed`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Why does `AQL Query Catalogue` connect `ARCHITECTURE.md` to `aql_catalog.py`, `Queries (36)`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `TestQueryCatalog` connect `aql_catalog.py` to `ARCHITECTURE.md`, `test_api.py`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `CircuitBreaker` (e.g. with `CircuitOpen` and `ResilientHttpClient`) actually correct?**
  _`CircuitBreaker` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `IngestionPipeline` (e.g. with `DatabaseUnavailable` and `NormalizedRecord`) actually correct?**
  _`IngestionPipeline` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `entrypoint.sh script`, `quakewatch`, `Prompt Defense Baseline` to the rest of the system?**
  _346 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `QuakeWatch` be split into smaller, more focused modules?**
  _Cohesion score 0.04081632653061224 - nodes in this community are weakly interconnected._