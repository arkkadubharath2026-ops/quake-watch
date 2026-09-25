# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 160 files · ~75,701 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .css 5, (none) 4, .geojson 3)

## Summary
- 3203 nodes · 7973 edges · 171 communities (139 shown, 32 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 404 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8be20734`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- run_in_transaction
- chart.umd.min.js
- Django Security Best Practices
- operations/api.py
- metrics.py
- django_apps
- client.py
- ResilientHttpClient
- Django + Celery Async Task Patterns
- task_context.py
- Frontend Accessibility Patterns
- ruff_on_edit.py
- RunRepository
- a11y-architect.md
- Review Priorities
- Architecture Decision Records
- Review Priorities
- Security Reviewer
- test_boundaries.py
- health.py
- QuakeWatch — Engineering System Design (ESD)
- Document Collections
- IndexSpec
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
- NamedQuery
- ARCHITECTURE.md
- 6. Constraints and Indexes
- 12. Research-Paper Potential
- 3. Target Users
- 6. Scope
- Any
- 15. Observability
- 20. Research Extensions
- 4. Source Integration
- 13. Success Metrics
- test_query_layer.py
- make_client
- 18. Deployment Profiles
- 3. Technology Stack
- entrypoint.sh
- quakewatch
- IngestionPipeline
- BoundingBox
- tn
- revision_policy.py
- .update
- usgs
- Handler
- normalize_feature
- normalizer.py
- CanonicalEventInput
- .from_params
- .__init__
- NormalizedRecord
- tasks.py
- ingestion/services.py
- n
- typing
- ValidationFailed
- EventRepository
- AppSettings
- IngestionRepository
- Analytics
- bootstrap.bundle.min.js
- test_http_resilience.py
- s
- logging.py
- Queries (47)
- explain
- St
- xt
- AuditRepository
- RuleConditions
- o
- Search
- ho
- Operations
- EventChange
- Maintenance
- ps
- pytest_collection_modifyitems
- ro
- B
- remove
- Client
- create_rule
- oo
- signals.py
- earthquakes/api.py
- es
- core/api.py
- leaflet.js
- alerts/api.py
- sn
- Qn
- run_query
- Qi
- Zs
- a
- AlertService
- de
- CircuitBreaker
- manifest.py
- Ln
- AlertRuleObserver
- analytics/api.py
- ResearchRepository
- Ss
- StandardDatabase
- ot
- CorrelationIdMiddleware
- ResearchService
- Zi
- hs
- F
- test_geo.py
- regions.py
- Any
- SavedSearchRepository
- api_urls.py
- event_key
- ADR-003: Canonical event + immutable revisions, with identity claims
- p
- d
- .test_concurrent_writers_with_different_preferred_ids_create_one_event
- bi
- O
- haversine_km
- detect_git_sha
- Alerts
- m
- accounts/apps.py
- core/apps.py
- .canonical
- oi
- Provenance
- Research
- AppConfig

## God Nodes (most connected - your core abstractions)
1. `tn` - 127 edges
2. `run_query()` - 62 edges
3. `n()` - 59 edges
4. `CircuitBreaker` - 58 edges
5. `IngestionPipeline` - 49 edges
6. `s()` - 45 edges
7. `ValidationFailed` - 42 edges
8. `ps` - 40 edges
9. `to_iso()` - 39 edges
10. `get_db()` - 39 edges

## Surprising Connections (you probably didn't know these)
- `39. `event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/AQL_QUERIES.md → apps/earthquakes/api.py
- ``event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/ESD.md → apps/earthquakes/api.py
- ``event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/ESD.md → apps/earthquakes/api.py
- `5. Transactions and concurrency` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Runtime (Python)` --references--> `CanonicalEventInput`  [INFERRED]
  docs/DEPENDENCIES.md → apps/earthquakes/domain.py

## Import Cycles
- None detected.

## Communities (171 total, 32 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.04
Nodes (49): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Academic Requirements Covered, Alerts / Watch Rules, Analytics, Competitor / Reference Systems (+41 more)

### Community 1 - "run_in_transaction"
Cohesion: 0.15
Nodes (12): _abort_quietly(), _is_retryable(), StandardDatabase, T, Run ``work`` atomically; retry on write-write conflicts.…, run_in_transaction(), BaseException, Two writers increment the same doc; conflict retries must not lose an update. (+4 more)

### Community 2 - "chart.umd.min.js"
Cohesion: 0.03
Nodes (56): ai(), at(), average(), beforeUpdate(), Bt(), dataset(), draw(), ea() (+48 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "operations/api.py"
Cohesion: 0.13
Nodes (31): page_params(), PageParams, paginated(), Request, Parse ``page``/``page_size`` query params with strict bounds (pagination is…, get_db(), Handle to the configured application database (``<db>_test`` under tests)., _AdminAction (+23 more)

### Community 5 - "metrics.py"
Cohesion: 0.10
Nodes (36): job_lock(), Distributed job locks on Redis (prevents overlapping scheduled runs of the same…, Yield True if the lock was acquired; the body should skip work when False., counters(), _counters_key(), incr(), _index_key(), observe() (+28 more)

### Community 6 - "django_apps"
Cohesion: 0.09
Nodes (15): AlertsConfig, AppConfig, AnalyticsConfig, AppConfig, EarthquakesConfig, AppConfig, GeoConfig, AppConfig (+7 more)

### Community 7 - "client.py"
Cohesion: 0.07
Nodes (34): _cached_db(), _connect(), database_name(), drop_database(), ensure_database(), get_client(), StandardDatabase, ArangoDB connection management. One :class:`ArangoClient` per process (it owns… (+26 more)

### Community 8 - "ResilientHttpClient"
Cohesion: 0.18
Nodes (9): An upstream source (e.g. USGS) failed. ``transient`` drives retry decisions., UpstreamError, Response, UpstreamError that also carries the provenance of the failed call., ResilientHttpClient, _retry_after(), UpstreamRequestFailed, BaseTransport (+1 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - "task_context.py"
Cohesion: 0.26
Nodes (12): _bind_task_context(), _clear_task_context(), _propagate_correlation_id(), Any, Propagate correlation IDs from the enqueuing request/job into Celery tasks. The…, celery_signals, connect, test_eager_task_restores_the_callers_context() (+4 more)

### Community 11 - "Frontend Accessibility Patterns"
Cohesion: 0.09
Nodes (22): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Checklist, Complete Accessible Form (+14 more)

### Community 12 - "ruff_on_edit.py"
Cohesion: 0.08
Nodes (19): PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, Celery application. Beat schedule is defined in apps.ingestion.schedule., django_core_asgi, django_core_wsgi (+11 more)

### Community 13 - "RunRepository"
Cohesion: 0.09
Nodes (30): Any, T, Narrow python-arango's ``Result[T]`` union for APIs that never return None. We…, Like :func:`sync` for APIs where None is a legitimate answer (e.g.…, sync(), sync_optional(), applied_version(), apply_schema() (+22 more)

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
Cohesion: 0.22
Nodes (12): ping(), Readiness probe: can we reach the server and our database?, live(), HttpRequest, Liveness / readiness probes (ESD §15). ``/health/live`` — the process is up (no…, ready(), django_http, django_views_decorators_cache (+4 more)

### Community 21 - "QuakeWatch — Engineering System Design (ESD)"
Cohesion: 0.15
Nodes (13): 11. Alert Engine, 12. Research Data Layer, 14. Security, 17. CI/CD, 19. Academic Rubric Mapping, 1. Engineering Strategy, 21. Architecture Decision Records, 22. External References (+5 more)

### Community 22 - "Document Collections"
Cohesion: 0.15
Nodes (13): 5. ArangoDB Data Model, `alert_matches`, `alert_rules`, `dead_letters`, Document Collections, Edge Collections, `event_revisions`, `events` (+5 more)

### Community 23 - "IndexSpec"
Cohesion: 0.33
Nodes (5): IndexSpec, _nullable(), _p(), Any, _ts()

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
Cohesion: 0.43
Nodes (7): Client, StandardDatabase, test_inbound_request_id_propagates(), test_live_is_always_ok(), test_malformed_request_id_replaced(), test_ready_checks_dependencies(), test_ready_reports_schema_drift()

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
Cohesion: 0.10
Nodes (21): load_fixture(), TestCatalogAndDetail, api_db(), body(), Any, Client, fixture, MonkeyPatch (+13 more)

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

### Community 40 - "NamedQuery"
Cohesion: 0.11
Nodes (20): AnalyticsRepository, Any, Database, _q(), AnalyticsReader, AnalyticsService, compute(), compute() (+12 more)

### Community 41 - "ARCHITECTURE.md"
Cohesion: 0.20
Nodes (5): AQL Query Catalogue, Dependencies and why each exists, Development / test, Frontend (vendored under `static/vendor`, no build step, no CDN at runtime), Runtime (Python)

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

### Community 46 - "Any"
Cohesion: 0.09
Nodes (11): EventQueryService, EventReader, present_event(), Any, EventFilter, Protocol, Saved explorer queries (FR-12). Filters are stored in canonical form and re-…, SavedSearchService (+3 more)

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
Cohesion: 0.16
Nodes (13): BreakerState, classify(), Freshness, FreshnessService, Any, datetime, Protocol, Source freshness (ADR-004): is the stored data current, and is the upstream… (+5 more)

### Community 52 - "make_client"
Cohesion: 0.20
Nodes (10): make_client(), Exception, parametrize, Request, Response, sequence(), handler(), TestRetries (+2 more)

### Community 53 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 54 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

### Community 69 - "IngestionPipeline"
Cohesion: 0.25
Nodes (16): IngestionPipeline, count(), feature(), feed_doc(), Any, fixture, StandardDatabase, Ingestion pipeline against a real ArangoDB: idempotency, revisions, identity,… (+8 more)

### Community 70 - "BoundingBox"
Cohesion: 0.15
Nodes (7): BoundingBox, Viewport box. ``west > east`` means the box crosses the antimeridian., Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n —…, GeoJSON polygon rings (lon, lat), split at the antimeridian when needed., Approximate fraction of the globe covered (for choosing clustering granularity)., _ring(), TestBoundingBox

### Community 71 - "tn"
Cohesion: 0.04
Nodes (14): addBox(), afterDatasetsUpdate(), configure(), d(), Di(), es(), generateLabels(), getPixelForTick() (+6 more)

### Community 72 - "revision_policy.py"
Cohesion: 0.17
Nodes (19): diff(), field_changed(), FieldChange, FieldRule, _numeric_changed(), Any, Versioned meaningful-revision policy (ESD §8) (pure). A *revision* is recorded…, Meaningful changes between two source states (ordered as in ``TRACKED_FIELDS``). (+11 more)

### Community 73 - ".update"
Cohesion: 0.05
Nodes (26): Ae(), afterDraw(), afterEvent(), afterUpdate(), Ba(), Bi(), Ci(), Ee() (+18 more)

### Community 74 - "usgs"
Cohesion: 0.18
Nodes (12): FakeCatalog, Any, datetime, MonkeyPatch, parametrize, Request, Response, StandardDatabase (+4 more)

### Community 75 - "Handler"
Cohesion: 0.21
Nodes (10): Handler, fake_usgs(), install(), fixture, MonkeyPatch, StandardDatabase, TestCommands, TestEnrichTask (+2 more)

### Community 76 - "normalize_feature"
Cohesion: 0.10
Nodes (20): _csv(), normalize_feature(), reject(), payload_hash(), Any, Stable SHA-256 of a JSON payload (sorted keys, compact separators)., RecordRejected, _summarize() (+12 more)

### Community 77 - "normalizer.py"
Cohesion: 0.13
Nodes (23): Earthquake domain model (pure). :class:`CanonicalEventInput` is the source-…, _Lenient, BaseModel, Strict contract for USGS GeoJSON payloads (summary feed, catalog query, detail…, Top level only; features are validated one by one so a bad record never sinks a…, UsgsCatalogCount, UsgsDetailFeature, UsgsDetailProperties (+15 more)

### Community 78 - "CanonicalEventInput"
Cohesion: 0.09
Nodes (17): CanonicalEventInput, is_important(), Any, BaseModel, datetime, field_validator, model_validator, Events that get eager detail enrichment (ESD §4.3 "important events"). (+9 more)

### Community 79 - ".from_params"
Cohesion: 0.15
Nodes (9): EventFilter, number(), text(), timestamp(), Radius, Human-readable query summary for the explorer and exports., Parse query parameters (strings) or a canonical dict; raise ValidationFailed on…, TestEventFilter (+1 more)

### Community 81 - "NormalizedRecord"
Cohesion: 0.16
Nodes (13): NormalizedRecord, _event_doc(), unit(), _pick_primary(), Any, Exception, StandardDatabase, _revision() (+5 more)

### Community 82 - "tasks.py"
Cohesion: 0.07
Nodes (40): CircuitOpen, Conflict, DatabaseUnavailable, NotFound, PermissionDenied, Exception, QuakeWatchError, Application error hierarchy. Domain and service code raise these; the API layer… (+32 more)

### Community 83 - "ingestion/services.py"
Cohesion: 0.08
Nodes (34): from_epoch_ms(), from_iso(), datetime, Time utilities. Timestamps are persisted as fixed-width ISO-8601 UTC strings…, to_iso(), utc_now(), Command, _date() (+26 more)

### Community 84 - "n"
Cohesion: 0.05
Nodes (14): Be(), ei(), fn(), gn(), je(), n(), ne(), numeric() (+6 more)

### Community 85 - "typing"
Cohesion: 0.08
Nodes (51): Alert rule model (pure). Rules are data, never executable user code (ESD §11)., Deterministic, explainable rule evaluation (FR-11) (pure). Each condition…, Alert-rule evaluation inside the ingestion transaction (ESD §7 "EVALUATE ALERT…, match_key(), Alert rules, matches and their graph edges. Every user-facing query is scoped…, Alert rule use cases (FR-10, FR-11): owner-scoped CRUD, dry-run preview,…, Analytics aggregations (FR-09). Every query is a registered…, Analytics services: parameter validation, windowing, short-lived caching… (+43 more)

### Community 86 - "ValidationFailed"
Cohesion: 0.11
Nodes (26): Upstream payload does not match the expected contract., SourceSchemaError, ValidationFailed, FetchResult, Any, SourceRequest, CatalogCount, DetailResult (+18 more)

### Community 87 - "EventRepository"
Cohesion: 0.21
Nodes (8): compile_filter(), CompiledQuery, EventRepository, Any, EventFilter, Compact points ``[key, lat, lon, mag, depth, occurred_at]``; flag if over the…, Server-side grid clustering for dense viewports (bounded result size)., search_aql()

### Community 88 - "AppSettings"
Cohesion: 0.18
Nodes (6): BaseSettings, AppSettings, field_validator, model_validator, Tests always run against an isolated ``<db>_test`` database., TestSettingsValidation

### Community 89 - "IngestionRepository"
Cohesion: 0.09
Nodes (11): network_name(), Reference names for common ANSS / USGS contributing network codes (pure). Only…, dead_letter_key(), IngestionRepository, KnownEvent, Database, Fast-path lookup (unique index) of current payload hashes by preferred id., Live canonical events claimed by any of ``ids`` (primary-key lookups only).… (+3 more)

### Community 90 - "Analytics"
Cohesion: 0.12
Nodes (17): 10. `analytics_magnitude_by_month`, 11. `analytics_magnitude_changes`, 12. `analytics_magnitude_depth_scatter`, 13. `analytics_magnitude_histogram`, 14. `analytics_most_revised`, 15. `analytics_network_stats`, 16. `analytics_revision_count_distribution`, 17. `analytics_revision_field_frequency` (+9 more)

### Community 91 - "bootstrap.bundle.min.js"
Cohesion: 0.08
Nodes (50): be(), bi(), Ce(), ci(), D(), De(), _e(), ei() (+42 more)

### Community 92 - "test_http_resilience.py"
Cohesion: 0.13
Nodes (11): backoff_delay(), Full-jitter exponential backoff for retry ``attempt`` (1-based). An upstream…, breaker(), clock(), FakeClock, fixture, MonkeyPatch, Resilience tests for the upstream HTTP adapter and the shared circuit breaker.… (+3 more)

### Community 93 - "s"
Cohesion: 0.06
Nodes (38): aa(), Bn(), buildTicks(), _calculateBarIndexPixels(), _calculateBarValuePixels(), _getAxis(), _getAxisCount(), getFirstScaleIdForIndexAxis() (+30 more)

### Community 94 - "logging.py"
Cohesion: 0.11
Nodes (16): Any, HttpRequest, site(), Request middleware: correlation IDs and request timing/outcome logging +…, Registry of ingestion observers (dependency inversion: ingestion never imports…, EventObserver, Protocol, Participates in the ingestion transaction for inserted/revised events. (+8 more)

### Community 95 - "Queries (47)"
Cohesion: 0.17
Nodes (12): 21. `event_resolve_id`, 22. `event_nearby_space_time`, 23. `alerts_matched_events_graph`, 24. `event_graph_relationships`, 39. `event_revisions`, 40. `saved_searches_by_user`, Detail, Geo (+4 more)

### Community 96 - "explain"
Cohesion: 0.15
Nodes (13): explain(), indexes_used(), collect(), Any, Database, Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics…, Index names (or types) used by a plan, including traversal edge indexes., Command (+5 more)

### Community 97 - "St"
Cohesion: 0.07
Nodes (9): St, color(), jt(), kt(), mt(), qt(), _t(), te() (+1 more)

### Community 101 - "xt"
Cohesion: 0.08
Nodes (9): un, an(), as(), cn(), hn(), ln(), on, ts() (+1 more)

### Community 103 - "AuditRepository"
Cohesion: 0.10
Nodes (16): ThrottledModelBackend, AuditRepository, OperationsRepository, Any, Database, Append-only audit trail. There is intentionally no update or delete method., Index justification (ESD §6), 1. High-level design (+8 more)

### Community 104 - "RuleConditions"
Cohesion: 0.09
Nodes (19): field_validator, model_validator, All given conditions must hold (logical AND). At least one condition is…, Create/replace payload. ``cooldown_minutes`` suppresses repeat notifications…, RuleConditions, RuleInput, RulePatch, _compare() (+11 more)

### Community 105 - "o"
Cohesion: 0.09
Nodes (29): b(), beforeLayout(), bs(), ct(), dn(), e(), fe(), g() (+21 more)

### Community 106 - "Search"
Cohesion: 0.25
Nodes (8): 41. `events_deepest`, 42. `events_in_viewport`, 43. `events_location_text`, 44. `events_recent_strong`, 45. `events_strongest_in_range`, 46. `events_tsunami_flagged`, 47. `events_within_radius`, Search

### Community 107 - "ho"
Cohesion: 0.08
Nodes (13): buildLookupTable(), Fs(), _generate(), getDecimalForValue(), _getTimestampsForTable(), getValueForPixel(), ho(), init() (+5 more)

### Community 108 - "Operations"
Cohesion: 0.29
Nodes (7): 29. `ops_audit_recent`, 30. `ops_backfill_jobs`, 31. `ops_dead_letters`, 32. `ops_latest_run`, 33. `ops_recent_runs`, 34. `ops_run_stats`, Operations

### Community 109 - "EventChange"
Cohesion: 0.24
Nodes (6): EventChange, Database, Return the number of side effects produced (e.g. alert matches)., Database, RecordingObserver, on_event()

### Community 110 - "Maintenance"
Cohesion: 0.40
Nodes (5): 25. `backfill_active_jobs`, 26. `ingest_repoint_claims`, 27. `ingest_resolve_dead_letters`, 28. `runs_abandon_stale`, Maintenance

### Community 111 - "ps"
Cohesion: 0.09
Nodes (4): ps, vs, ns(), rs()

### Community 112 - "pytest_collection_modifyitems"
Cohesion: 0.67
Nodes (3): Config, Item, pytest_collection_modifyitems()

### Community 113 - "ro"
Cohesion: 0.08
Nodes (13): ao(), bo, co(), da(), Do(), getBasePixel(), H(), inXRange() (+5 more)

### Community 114 - "B"
Cohesion: 0.07
Nodes (5): B, mo, U, x(), eo()

### Community 115 - "remove"
Cohesion: 0.13
Nodes (5): qt, remove(), Nn(), uo(), wn()

### Community 116 - "Client"
Cohesion: 0.14
Nodes (14): body(), Any, Client, fixture, MonkeyPatch, parametrize, StandardDatabase, staff_client() (+6 more)

### Community 117 - "create_rule"
Cohesion: 0.22
Nodes (18): NormalizedRecord, alice(), body(), create_rule(), ingest(), Any, Client, fixture (+10 more)

### Community 118 - "oo"
Cohesion: 0.09
Nodes (16): beforeDatasetDraw(), beforeDatasetsDraw(), beforeDraw(), fa(), ga(), ia(), Ie(), io() (+8 more)

### Community 119 - "signals.py"
Cohesion: 0.11
Nodes (26): apps_accounts, _ip(), Any, HttpRequest, Authentication backend that refuses attempts for locked (username, IP) pairs., is_locked(), _key(), _keys() (+18 more)

### Community 120 - "earthquakes/api.py"
Cohesion: 0.19
Nodes (21): event_detail(), event_list(), event_map(), event_provenance(), event_relationships(), event_revisions(), EventEnrichView, api_view (+13 more)

### Community 122 - "core/api.py"
Cohesion: 0.13
Nodes (22): authenticated_user(), AuthUser, error_body(), exception_handler(), Any, Exception, Response, Shared API plumbing: error envelope, exception mapping, pagination parameters. (+14 more)

### Community 123 - "leaflet.js"
Cohesion: 0.08
Nodes (6): a(), Ci(), l(), me(), x(), ze()

### Community 124 - "alerts/api.py"
Cohesion: 0.22
Nodes (15): MatchedEventsView, MatchFeedView, MatchReadView, APIView, Request, Response, Alert rules + notifications API (authenticated; owner-scoped)., Mark one match (``{"id": ...}``) or all unread matches (empty body) as read. (+7 more)

### Community 125 - "sn"
Cohesion: 0.14
Nodes (3): addElements(), en, sn

### Community 126 - "Qn"
Cohesion: 0.12
Nodes (4): an, Qn, kn(), qn()

### Community 127 - "run_query"
Cohesion: 0.20
Nodes (7): AlertRepository, Any, Database, Delete a rule and its graph edges. Match history is kept (it snapshots the…, Insert once (deterministic key); returns False if this rule already matched the…, QueryResult, run_query()

### Community 130 - "a"
Cohesion: 0.20
Nodes (7): a(), determineDataLimits(), pi(), r(), ri(), So, v()

### Community 131 - "AlertService"
Cohesion: 0.19
Nodes (7): AlertService, _parse(), Any, Which recent events would this rule have matched, and why? (no side effects), pydantic_details(), Map a pydantic ValidationError to ``{"fields": {"a.b": "message"}}`` for the…, M

### Community 132 - "de"
Cohesion: 0.18
Nodes (5): ca, ce(), de, dt(), he()

### Community 133 - "CircuitBreaker"
Cohesion: 0.25
Nodes (4): CircuitBreaker, Raise :class:`CircuitOpen` if calls must not be attempted right now., Revisions, TestEnrichment

### Community 134 - "manifest.py"
Cohesion: 0.22
Nodes (14): build_manifest(), bundle(), canonical_order(), _cell(), content_sha256(), export_row(), _json_line(), Any (+6 more)

### Community 136 - "AlertRuleObserver"
Cohesion: 0.16
Nodes (10): AlertRuleObserver, Any, Database, datetime, timedelta, ADR-005: Alert rule representation and evaluation, Consequences, Context (+2 more)

### Community 137 - "analytics/api.py"
Cohesion: 0.43
Nodes (13): breakdowns(), distributions(), latency(), api_view, Request, Response, Analytics API (FR-09). All windows are ``?days=N`` (1..3660, default 30)., revisions() (+5 more)

### Community 138 - "ResearchRepository"
Cohesion: 0.20
Nodes (6): Any, Database, EventFilter, ``[[event_key, revision_number], ...]`` for matching live events, capped at…, Request provenance of the ingestion runs that produced the pinned revisions., ResearchRepository

### Community 140 - "StandardDatabase"
Cohesion: 0.19
Nodes (6): parametrize, StandardDatabase, TestCollectionRules, TestDataMigrations, TestMigrations, TestQueryRunner

### Community 142 - "CorrelationIdMiddleware"
Cohesion: 0.24
Nodes (8): CorrelationIdMiddleware, new_correlation_id(), HttpRequest, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs., Log endpoint/duration/outcome for every request and feed API latency metrics., RequestTimingMiddleware, 4. Cross-cutting concerns, HttpResponse

### Community 143 - "ResearchService"
Cohesion: 0.23
Nodes (4): ExportFile, IntegrityError, ResearchService, _text()

### Community 146 - "F"
Cohesion: 0.24
Nodes (12): F(), G(), h(), j(), k(), ke(), ne(), e() (+4 more)

### Community 147 - "test_geo.py"
Cohesion: 0.33
Nodes (7): InvalidGeometry, Geodesic helpers (pure). Distances use the haversine formula on a spherical…, validate_lat_lon(), validate_radius_km(), math, TestValidation, ValueError

### Community 148 - "regions.py"
Cohesion: 0.27
Nodes (7): DerivedRegion, Derive an application region from a USGS ``place`` string (pure,…, region_from_place(), slugify(), parametrize, TestRegions, unicodedata

### Community 149 - "Any"
Cohesion: 0.27
Nodes (4): Any, EventFilter, Protocol, SnapshotStore

### Community 150 - "SavedSearchRepository"
Cohesion: 0.20
Nodes (3): Database, User-owned saved searches (FR-12). Every query is scoped by ``user_id``., SavedSearchRepository

### Community 151 - "api_urls.py"
Cohesion: 0.25
Nodes (7): apps_alerts, apps_analytics, apps_earthquakes, apps_operations, Versioned JSON API routes (/api/v1/...)., django_contrib, django_urls

### Community 152 - "event_key"
Cohesion: 0.22
Nodes (7): event_key(), Deterministic ArangoDB ``_key`` for the first-seen identity of a source event., ADR-006: Research snapshot reproducibility, Consequences, Context, Decision, Relational rubric mapping (ESD §19)

### Community 153 - "ADR-003: Canonical event + immutable revisions, with identity claims"
Cohesion: 0.22
Nodes (8): ADR-003: Canonical event + immutable revisions, with identity claims, Atomicity and failure isolation, Canonical record, Consequences, Context, Decision, Identity claims (`event_identities`), Review history

### Community 154 - "p"
Cohesion: 0.22
Nodes (9): Ae(), be(), De(), ei(), Ie(), ii(), p(), pe() (+1 more)

### Community 155 - "d"
Cohesion: 0.25
Nodes (9): at(), d(), ht(), i(), Li(), Mi(), v(), W() (+1 more)

### Community 156 - ".test_concurrent_writers_with_different_preferred_ids_create_one_event"
Cohesion: 0.25
Nodes (8): arango_db(), StandardDatabase, Clean database per test (collections truncated, schema/indexes kept)., parametrize, Reviewer scenario: feed sees preferred id a, backfill sees b, for the same…, TestIdentityClaims, run(), run()

### Community 157 - "bi"
Cohesion: 0.25
Nodes (8): bi(), c(), e(), hi(), Pi(), Qe(), Ti(), u()

### Community 158 - "O"
Cohesion: 0.29
Nodes (7): Jt(), Le(), O(), Qt(), Re(), $t(), te()

### Community 160 - "detect_git_sha"
Cohesion: 0.40
Nodes (4): detect_git_sha(), Short commit SHA from ``.git`` files (no subprocess); None outside a git…, Explicit QW_APP_VERSION (container builds) or the checkout's git SHA., Path

### Community 161 - "Alerts"
Cohesion: 0.40
Nodes (5): 1. `alerts_enabled_rules`, 2. `alerts_last_notified`, 3. `alerts_user_feed`, 4. `alerts_user_rules`, Alerts

### Community 162 - "m"
Cohesion: 0.60
Nodes (5): m(), ve(), xe(), ye(), z()

### Community 165 - ".canonical"
Cohesion: 0.50
Nodes (3): Any, Deterministic, JSON-safe representation (only set fields; sorted keys)., 7. Query & API layer (L3)

### Community 166 - "oi"
Cohesion: 0.67
Nodes (4): Je(), ni(), oi(), si()

### Community 167 - "Provenance"
Cohesion: 0.67
Nodes (3): 35. `event_raw_payload`, 36. `ingestion_runs_by_ids`, Provenance

### Community 168 - "Research"
Cohesion: 0.67
Nodes (3): 37. `research_rows_from_revisions`, 38. `research_user_snapshots`, Research

## Knowledge Gaps
- **363 isolated node(s):** `Standing instructions from the project owner (always follow)`, `Boundary rules (enforced by tests/architecture)`, `Commands`, `Project tooling (.claude/)`, `Safety wording` (+358 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 903 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `event_revisions()` connect `earthquakes/api.py` to `CircuitBreaker`, `AuditRepository`, `6. Constraints and Indexes`, `Document Collections`, `Queries (47)`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `AQL Query Catalogue` connect `ARCHITECTURE.md` to `explain`, `Queries (47)`, `AuditRepository`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `QuakeWatch Architecture` connect `AuditRepository` to `ARCHITECTURE.md`, `.canonical`, `CorrelationIdMiddleware`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `CircuitBreaker` (e.g. with `CircuitOpen` and `ResilientHttpClient`) actually correct?**
  _`CircuitBreaker` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Standing instructions from the project owner (always follow)`, `Boundary rules (enforced by tests/architecture)`, `Commands` to the rest of the system?**
  _363 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `QuakeWatch` be split into smaller, more focused modules?**
  _Cohesion score 0.04081632653061224 - nodes in this community are weakly interconnected._
- **Should `chart.umd.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.03011204481792717 - nodes in this community are weakly interconnected._