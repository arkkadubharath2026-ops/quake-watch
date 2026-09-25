# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 197 files · ~110,632 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .css 6, (none) 4, .geojson 3)

## Summary
- 3695 nodes · 9243 edges · 204 communities (164 shown, 40 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 547 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b4b03da9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- typing
- chart.umd.min.js
- Django Security Best Practices
- get_db
- metrics.py
- django_apps
- operations/api.py
- test_ingestion_services.py
- Django + Celery Async Task Patterns
- .update
- benchmark.py
- vendor_assets.py
- client.py
- a11y-architect.md
- Review Priorities
- Architecture Decision Records
- Review Priorities
- Security Reviewer
- test_boundaries.py
- o
- QuakeWatch — Engineering System Design (ESD)
- Document Collections
- usgs
- QuakeWatch verification gate
- Hunt Targets
- QuakeWatch — instructions for Claude
- CircuitBreaker
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
- Page
- 6. Constraints and Indexes
- 12. Research-Paper Potential
- e2e/conftest.py
- 6. Scope
- EventFilter
- qw.js
- 20. Research Extensions
- 4. Source Integration
- explain
- ingestion/services.py
- run_query
- D
- l
- entrypoint.sh
- quakewatch
- IngestionPipeline
- test_geo.py
- tn
- test_revision_policy.py
- s
- Zi
- StandardDatabase
- pipeline.py
- Frontend Accessibility Patterns
- ADR-008: Multi-source canonicalization (research track)
- .from_params
- O
- oo
- .form_invalid
- fixture
- n
- ValidationFailed
- qt
- EventRepository
- test_pages.py
- web/views.py
- Analytics
- bootstrap.bundle.min.js
- .apply_write
- explorer.js
- Qn
- Queries (47)
- alerts.js
- St
- xt
- AuditRepository
- RuleConditions
- i
- Search
- ho
- Operations
- an
- Maintenance
- ps
- operations.js
- .getContext
- remove
- event_key
- ADR-003: Canonical event + immutable revisions, with identity claims
- create_rule
- security.py
- signals.py
- earthquakes/api.py
- B
- alerts/api.py
- leaflet.js
- _service
- sn
- dashboard.py
- AlertRepository
- Qi
- Zs
- Handler
- ARCHITECTURE.md
- Major Features
- QuakeWatch build progress
- ruff_on_edit.py
- .configure
- qw-map.js
- analytics.js
- ResearchRepository
- Ss
- event.js
- core/apps.py
- map.js
- charts.js
- ResearchService
- hs
- F
- dashboard.js
- AppSettings
- test_health.py
- RunRepository
- accounts/views.py
- m
- StandardDatabase
- env.py
- d
- Accessibility audit (WCAG 2.2 AA)
- bi
- exclusive_query
- ADR-010: Timestamp representation and source/derived separation
- Development Phases
- Alerts
- QuakeWatch design system
- research.js
- authenticated_user
- BackfillService
- oi
- Provenance
- Research
- task_context.py
- manifest.py
- Research Directions
- 4. Cross-cutting concerns
- 15. Observability
- safe_usgs_url
- de
- regions.py
- status.js
- .test_authenticated_request_queues_enrichment
- p
- AlertRuleObserver
- .handle
- QuakeWatch operations runbook
- haversine_km
- detect_git_sha
- ADR-007: Raw-data retention policy
- ready
- 3. Target Users
- accounts/apps.py
- ADR-011: Server-rendered pages with API-driven islands
- FakeClock
- Dependencies and why each exists
- 13. Success Metrics
- .__init__
- geo/apps.py
- research/apps.py
- Database
- Client
- MonkeyPatch
- 18. Deployment Profiles
- 3. Technology Stack
- Proposed ArangoDB Model

## God Nodes (most connected - your core abstractions)
1. `tn` - 127 edges
2. `run_query()` - 67 edges
3. `n()` - 59 edges
4. `CircuitBreaker` - 58 edges
5. `IngestionPipeline` - 56 edges
6. `get_db()` - 49 edges
7. `to_iso()` - 46 edges
8. `s()` - 45 edges
9. `ValidationFailed` - 42 edges
10. `ps` - 40 edges

## Surprising Connections (you probably didn't know these)
- `5. Transactions and concurrency` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Decision` --references--> `CanonicalEventInput`  [INFERRED]
  docs/adr/ADR-008-multi-source-canonicalization.md → apps/earthquakes/domain.py
- `Decision` --references--> `CanonicalEventInput`  [INFERRED]
  docs/adr/ADR-010-timestamps-and-derived-values.md → apps/earthquakes/domain.py
- `Runtime (Python)` --references--> `CanonicalEventInput`  [INFERRED]
  docs/DEPENDENCIES.md → apps/earthquakes/domain.py
- `Identity claims (`event_identities`)` --references--> `event_key()`  [INFERRED]
  docs/adr/ADR-003-canonical-event-and-revisions.md → apps/earthquakes/domain.py

## Import Cycles
- None detected.

## Communities (204 total, 40 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.08
Nodes (24): Academic Requirements Covered, Competitor / Reference Systems, Core, Core Workflow, Current Recommended Milestone, Data Integrity Rules, Documentation, EMSC LastQuake (+16 more)

### Community 1 - "typing"
Cohesion: 0.06
Nodes (50): Removal of a user's ArangoDB data when their Django account is deleted., Alert rule model (pure). Rules are data, never executable user code (ESD §11)., Deterministic, explainable rule evaluation (FR-11) (pure). Each condition…, match_key(), Alert rules, matches and their graph edges. Every user-facing query is scoped…, Analytics aggregations (FR-09). Every query is a registered…, Analytics services: parameter validation, windowing, short-lived caching…, apps_core_arango (+42 more)

### Community 2 - "chart.umd.min.js"
Cohesion: 0.03
Nodes (69): ai(), at(), average(), beforeDatasetDraw(), beforeDatasetsDraw(), beforeDraw(), beforeUpdate(), ca (+61 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "get_db"
Cohesion: 0.12
Nodes (30): get_db(), ping(), Handle to the configured application database (``<db>_test`` under tests)., Readiness probe: can we reach the server and our database?, _AdminAction, audit_log(), BackfillView, create() (+22 more)

### Community 5 - "metrics.py"
Cohesion: 0.10
Nodes (33): counters(), _counters_key(), incr(), _index_key(), observe(), percentile(), ping(), Exception (+25 more)

### Community 6 - "django_apps"
Cohesion: 0.11
Nodes (13): AlertsConfig, AppConfig, AnalyticsConfig, AppConfig, EarthquakesConfig, AppConfig, IngestionConfig, AppConfig (+5 more)

### Community 7 - "operations/api.py"
Cohesion: 0.10
Nodes (27): database_name(), get_client(), build_usgs_client(), usgs_breaker(), Any, Command, Any, BaseCommand (+19 more)

### Community 8 - "test_ingestion_services.py"
Cohesion: 0.06
Nodes (48): apps_core, CircuitOpen, An upstream source (e.g. USGS) failed. ``transient`` drives retry decisions., Upstream payload does not match the expected contract., SourceSchemaError, UpstreamError, job_lock(), Yield True if the lock was acquired; the body should skip work when False. (+40 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - ".update"
Cohesion: 0.08
Nodes (18): afterDraw(), afterEvent(), afterUpdate(), Ba(), f(), ki(), Oi(), os() (+10 more)

### Community 11 - "benchmark.py"
Cohesion: 0.07
Nodes (52): apps_analytics, BenchContext, drop_performance_indexes(), _hash(), _import(), _location(), _magnitude(), measure() (+44 more)

### Community 12 - "vendor_assets.py"
Cohesion: 0.16
Nodes (9): PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, fetch(), main(), Re-record the real USGS payloads used by the contract tests…, fetch(), main(), Download pinned frontend assets into static/vendor and verify their SHA-256…, sys (+1 more)

### Community 13 - "client.py"
Cohesion: 0.07
Nodes (44): _cached_db(), _connect(), ensure_database(), Any, StandardDatabase, T, ArangoDB connection management. One :class:`ArangoClient` per process (it owns…, Narrow python-arango's ``Result[T]`` union for APIs that never return None. We… (+36 more)

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

### Community 20 - "o"
Cohesion: 0.14
Nodes (13): a(), determineDataLimits(), g(), g(), m(), o(), p(), r() (+5 more)

### Community 21 - "QuakeWatch — Engineering System Design (ESD)"
Cohesion: 0.17
Nodes (12): 11. Alert Engine, 12. Research Data Layer, 14. Security, 17. CI/CD, 1. Engineering Strategy, 21. Architecture Decision Records, 22. External References, 2. High-Level Architecture (+4 more)

### Community 22 - "Document Collections"
Cohesion: 0.15
Nodes (13): 5. ArangoDB Data Model, `alert_matches`, `alert_rules`, `dead_letters`, Document Collections, Edge Collections, `event_revisions`, `events` (+5 more)

### Community 23 - "usgs"
Cohesion: 0.18
Nodes (13): FakeCatalog, Any, datetime, MonkeyPatch, parametrize, Request, Response, StandardDatabase (+5 more)

### Community 24 - "QuakeWatch verification gate"
Cohesion: 0.18
Nodes (10): 0. Infrastructure up, 1. Lint + format, 2. Types, 3. Django system checks (incl. deploy checks with production settings), 4. Tests (real ArangoDB — integration tests use an isolated `<db>_test` database), 5. Architectural boundaries, 6. Security, 7. Graph refresh + impact check (+2 more)

### Community 25 - "Hunt Targets"
Cohesion: 0.20
Nodes (9): 1. Empty Catch Blocks, 2. Inadequate Logging, 3. Dangerous Fallbacks, 4. Error Propagation Issues, 5. Missing Error Handling, Hunt Targets, Output Format, Prompt Defense Baseline (+1 more)

### Community 26 - "QuakeWatch — instructions for Claude"
Cohesion: 0.22
Nodes (8): Architecture (see docs/ARCHITECTURE.md), Boundary rules (enforced by tests/architecture), Commands, graphify, Project tooling (.claude/), QuakeWatch — instructions for Claude, Safety wording, Standing instructions from the project owner (always follow)

### Community 27 - "CircuitBreaker"
Cohesion: 0.23
Nodes (10): CircuitBreaker, make_client(), Exception, parametrize, Request, Response, sequence(), handler() (+2 more)

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
Cohesion: 0.17
Nodes (10): Client, body(), Any, parametrize, StandardDatabase, A polling gap (reviewed version observed 6 h late) must not inflate the metric., TestAnalytics, TestEventDetail (+2 more)

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
Cohesion: 0.50
Nodes (3): ADR-002: Modular Django monolith with background workers, Consequences, Context

### Community 39 - "ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB"
Cohesion: 0.40
Nodes (4): ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB, Consequences, Context, Decision

### Community 40 - "analytics/api.py"
Cohesion: 0.10
Nodes (30): breakdowns(), distributions(), latency(), api_view, Request, Response, Analytics API (FR-09). All windows are ``?days=N`` (1..3660, default 30)., revisions() (+22 more)

### Community 41 - "Page"
Cohesion: 0.07
Nodes (41): Any, axe_playwright_python_sync_playwright, playwright_sync_api, StandardDatabase, break_api(), handler(), browser_errors(), BrowserErrors (+33 more)

### Community 42 - "6. Constraints and Indexes"
Cohesion: 0.40
Nodes (5): 6. Constraints and Indexes, `alert_rules`, `event_revisions`, `events`, `ingestion_runs`

### Community 43 - "12. Research-Paper Potential"
Cohesion: 0.40
Nodes (5): 12. Research-Paper Potential, RQ1 — Event Revision Dynamics, RQ2 — Multi-Source Latency and Consistency, RQ3 — Revision-Likelihood Modeling, RQ4 — Spatiotemporal Sequence Characterization

### Community 44 - "e2e/conftest.py"
Cohesion: 0.10
Nodes (21): base64, Celery application. Beat schedule is defined in apps.ingestion.schedule., django_core_asgi, django_core_wsgi, fixture, LiveServer, os, pytest_django_live_server_helper (+13 more)

### Community 45 - "6. Scope"
Cohesion: 0.40
Nodes (5): 6. Scope, MVP, Out of Scope, Research Track, Version 1.1

### Community 46 - "EventFilter"
Cohesion: 0.10
Nodes (10): EventFilter, Human-readable query summary for the explorer and exports., EventQueryService, EventReader, Any, Protocol, Saved explorer queries (FR-12). Filters are stored in canonical form and re-…, SavedSearchService (+2 more)

### Community 47 - "qw.js"
Cohesion: 0.13
Nodes (27): ago(), api(), append(), band(), clear(), csrfToken(), errorState(), eventLink() (+19 more)

### Community 48 - "20. Research Extensions"
Cohesion: 0.50
Nodes (4): 20. Research Extensions, A. Multi-Source Concordance, B. Revision Intelligence, C. Spatiotemporal Graph

### Community 49 - "4. Source Integration"
Cohesion: 0.50
Nodes (4): 4.1 USGS Summary Feed Adapter, 4.2 Catalog API Adapter, 4.3 Detail Feed Adapter, 4. Source Integration

### Community 50 - "explain"
Cohesion: 0.23
Nodes (9): explain(), indexes_used(), collect(), Any, Database, Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics…, Index names (or types) used by a plan, including traversal edge indexes., Consequences (+1 more)

### Community 51 - "ingestion/services.py"
Cohesion: 0.07
Nodes (42): Alert-rule evaluation inside the ingestion transaction (ESD §7 "EVALUATE ALERT…, from_epoch_ms(), from_iso(), now_iso(), datetime, Time utilities. Timestamps are persisted as fixed-width ISO-8601 UTC strings…, to_iso(), utc_now() (+34 more)

### Community 52 - "run_query"
Cohesion: 0.10
Nodes (12): QueryResult, run_query(), User-owned saved searches (FR-12). Every query is scoped by ``user_id``., SavedSearchRepository, dead_letter_key(), IngestionRepository, KnownEvent, Database (+4 more)

### Community 53 - "D"
Cohesion: 0.16
Nodes (12): D(), I(), j(), k(), L(), N(), off(), on() (+4 more)

### Community 54 - "l"
Cohesion: 0.10
Nodes (14): buildTicks(), getLabelAndValue(), getLabelForValue(), l(), ii(), mo(), parse(), parseArrayData() (+6 more)

### Community 69 - "IngestionPipeline"
Cohesion: 0.10
Nodes (38): _event_doc(), EventChange, IngestionPipeline, unit(), _pick_primary(), Any, Database, StandardDatabase (+30 more)

### Community 70 - "test_geo.py"
Cohesion: 0.13
Nodes (14): BoundingBox, InvalidGeometry, Geodesic helpers (pure). Distances use the haversine formula on a spherical…, Viewport box. ``west > east`` means the box crosses the antimeridian., Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n —…, GeoJSON polygon rings (lon, lat), split at the antimeridian when needed., Approximate fraction of the globe covered (for choosing clustering granularity)., _ring() (+6 more)

### Community 71 - "tn"
Cohesion: 0.04
Nodes (17): Checklist, When to Activate, aa(), afterDatasetsUpdate(), d(), Di(), es(), generateLabels() (+9 more)

### Community 72 - "test_revision_policy.py"
Cohesion: 0.16
Nodes (17): diff(), field_changed(), FieldRule, _numeric_changed(), Any, Meaningful changes between two source states (ordered as in ``TRACKED_FIELDS``)., _timestamp_changed(), untracked_changed() (+9 more)

### Community 73 - "s"
Cohesion: 0.05
Nodes (25): Ae(), Bn(), bo, _calculateBarValuePixels(), getPixelForTick(), getPixelForValue(), getRange(), Gs() (+17 more)

### Community 75 - "StandardDatabase"
Cohesion: 0.12
Nodes (10): parametrize, StandardDatabase, Two writers increment the same doc; conflict retries must not lose an update., TestCollectionRules, TestDataMigrations, TestMigrations, TestQueryRunner, TestTransactions (+2 more)

### Community 76 - "pipeline.py"
Cohesion: 0.04
Nodes (74): CanonicalEventInput, is_important(), BaseModel, datetime, field_validator, model_validator, Earthquake domain model (pure). :class:`CanonicalEventInput` is the source-…, Events that get eager detail enrichment (ESD §4.3 "important events"). (+66 more)

### Community 77 - "Frontend Accessibility Patterns"
Cohesion: 0.10
Nodes (20): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Complete Accessible Form, Custom Dropdown (+12 more)

### Community 78 - "ADR-008: Multi-source canonicalization (research track)"
Cohesion: 0.40
Nodes (4): ADR-008: Multi-source canonicalization (research track), Consequences, Context, Decision

### Community 79 - ".from_params"
Cohesion: 0.16
Nodes (8): number(), text(), timestamp(), Any, Deterministic, JSON-safe representation (only set fields; sorted keys)., Parse query parameters (strings) or a canonical dict; raise ValidationFailed on…, 7. Query & API layer (L3), TestEventFilter

### Community 80 - "O"
Cohesion: 0.29
Nodes (7): Jt(), Le(), O(), Qt(), Re(), $t(), te()

### Community 81 - "oo"
Cohesion: 0.21
Nodes (4): io(), no(), oo, zi()

### Community 82 - ".form_invalid"
Cohesion: 0.29
Nodes (5): Any, HttpResponse, QuakeWatchLoginView, AuthenticationForm, LoginView

### Community 84 - "n"
Cohesion: 0.06
Nodes (19): Be(), e(), ei(), fn(), gi(), gn(), je(), mi() (+11 more)

### Community 85 - "ValidationFailed"
Cohesion: 0.08
Nodes (28): Alert rule use cases (FR-10, FR-11): owner-scoped CRUD, dry-run preview,…, Conflict, NotFound, PermissionDenied, Any, Exception, pydantic_details(), QuakeWatchError (+20 more)

### Community 86 - "qt"
Cohesion: 0.19
Nodes (3): qt, Bt(), Ft()

### Community 87 - "EventRepository"
Cohesion: 0.13
Nodes (15): compile_filter(), CompiledQuery, EventRepository, Any, EventFilter, One page plus the total match count, in one query (one consistent snapshot).…, Compact points ``[key, lat, lon, mag, depth, occurred_at]``; flag if over the…, Server-side grid clustering for dense viewports (bounded result size). (+7 more)

### Community 88 - "test_pages.py"
Cohesion: 0.13
Nodes (20): Any, HttpRequest, site(), _visible(), django_contrib_staticfiles, events(), html(), _nonce() (+12 more)

### Community 89 - "web/views.py"
Cohesion: 0.36
Nodes (18): about(), alerts(), analytics(), dashboard(), event_detail(), explorer(), live_map(), operations() (+10 more)

### Community 90 - "Analytics"
Cohesion: 0.12
Nodes (17): 10. `analytics_magnitude_by_month`, 11. `analytics_magnitude_changes`, 12. `analytics_magnitude_depth_scatter`, 13. `analytics_magnitude_histogram`, 14. `analytics_most_revised`, 15. `analytics_network_stats`, 16. `analytics_revision_count_distribution`, 17. `analytics_revision_field_frequency` (+9 more)

### Community 91 - "bootstrap.bundle.min.js"
Cohesion: 0.11
Nodes (38): be(), bi(), Ce(), ci(), De(), _e(), ei(), F() (+30 more)

### Community 92 - ".apply_write"
Cohesion: 0.40
Nodes (3): network_name(), Reference names for common ANSS / USGS contributing network codes (pure). Only…, Execute every write for one record in a single multi-collection AQL statement.…

### Community 93 - "explorer.js"
Cohesion: 0.27
Nodes (14): cell(), fillForm(), filtersFromParams(), freezeSnapshot(), headerCell(), loadSaved(), navigate(), radiusMode() (+6 more)

### Community 95 - "Queries (47)"
Cohesion: 0.17
Nodes (12): 21. `event_resolve_id`, 22. `event_nearby_space_time`, 23. `alerts_matched_events_graph`, 24. `event_graph_relationships`, 39. `event_revisions`, 40. `saved_searches_by_user`, Detail, Geo (+4 more)

### Community 96 - "alerts.js"
Cohesion: 0.26
Nodes (14): describe(), fillForm(), loadFeed(), loadRules(), markRead(), number(), payloadFrom(), preview() (+6 more)

### Community 97 - "St"
Cohesion: 0.05
Nodes (12): ot, St, color(), Gt(), jt(), kt(), mt(), qt() (+4 more)

### Community 101 - "xt"
Cohesion: 0.11
Nodes (6): an(), as(), on, rs(), ts(), xt

### Community 103 - "AuditRepository"
Cohesion: 0.08
Nodes (20): Authentication backend that refuses attempts for locked (username, IP) pairs., ThrottledModelBackend, AuditRepository, OperationsRepository, Any, Database, Append-only audit trail. There is intentionally no update or delete method., django_contrib_auth_backends (+12 more)

### Community 104 - "RuleConditions"
Cohesion: 0.06
Nodes (28): BaseModel, field_validator, model_validator, All given conditions must hold (logical AND). At least one condition is…, Create/replace payload. ``cooldown_minutes`` suppresses repeat notifications…, RuleConditions, RuleInput, RulePatch (+20 more)

### Community 105 - "i"
Cohesion: 0.14
Nodes (14): bs(), ct(), ge(), is(), ks(), ms(), ps(), ss() (+6 more)

### Community 106 - "Search"
Cohesion: 0.25
Nodes (8): 41. `events_deepest`, 42. `events_in_viewport`, 43. `events_location_text`, 44. `events_recent_strong`, 45. `events_strongest_in_range`, 46. `events_tsunami_flagged`, 47. `events_within_radius`, Search

### Community 107 - "ho"
Cohesion: 0.08
Nodes (15): beforeLayout(), buildLookupTable(), Fs(), _generate(), getDecimalForValue(), _getTimestampsForTable(), getValueForPixel(), Go() (+7 more)

### Community 108 - "Operations"
Cohesion: 0.29
Nodes (7): 29. `ops_audit_recent`, 30. `ops_backfill_jobs`, 31. `ops_dead_letters`, 32. `ops_latest_run`, 33. `ops_recent_runs`, 34. `ops_run_stats`, Operations

### Community 110 - "Maintenance"
Cohesion: 0.40
Nodes (5): 25. `backfill_active_jobs`, 26. `ingest_repoint_claims`, 27. `ingest_resolve_dead_letters`, 28. `runs_abandon_stale`, Maintenance

### Community 111 - "ps"
Cohesion: 0.08
Nodes (3): d(), ps, vs

### Community 112 - "operations.js"
Cohesion: 0.31
Nodes (12): actionResult(), backfill(), loadAudit(), loadDeadLetters(), loadDiagnostics(), loadJobs(), loadRuns(), renderOverview() (+4 more)

### Community 113 - ".getContext"
Cohesion: 0.10
Nodes (13): ao(), Bi(), Ci(), co(), da(), Do(), Fi(), getBasePixel() (+5 more)

### Community 114 - "remove"
Cohesion: 0.09
Nodes (4): Ln, mo, remove(), uo()

### Community 115 - "event_key"
Cohesion: 0.25
Nodes (6): event_key(), Deterministic ArangoDB ``_key`` for the first-seen identity of a source event., ADR-006: Research snapshot reproducibility, Consequences, Context, Decision

### Community 116 - "ADR-003: Canonical event + immutable revisions, with identity claims"
Cohesion: 0.20
Nodes (9): ADR-003: Canonical event + immutable revisions, with identity claims, Atomicity and failure isolation, Canonical record, Consequences, Context, Decision, Identity claims (`event_identities`), Review history (+1 more)

### Community 117 - "create_rule"
Cohesion: 0.24
Nodes (16): alice(), body(), create_rule(), ingest(), Any, Client, fixture, MonkeyPatch (+8 more)

### Community 118 - "security.py"
Cohesion: 0.16
Nodes (16): AttemptDecision, _incr(), is_locked(), _key(), _known(), Login brute-force protection (PRD NFR security: rate limits). Attempts are…, Count this attempt and decide whether it may proceed to password verification., Read-only view (for display/audit); enforcement happens in… (+8 more)

### Community 119 - "signals.py"
Cohesion: 0.14
Nodes (21): delete_user_data(), work(), StandardDatabase, Atomically delete rules (+ edges), matches, saved searches, snapshots, user…, _meta(), _on_login(), _on_login_failed(), _on_user_deleted() (+13 more)

### Community 120 - "earthquakes/api.py"
Cohesion: 0.22
Nodes (19): event_detail(), event_list(), event_map(), event_provenance(), event_relationships(), event_revisions(), EventEnrichView, api_view (+11 more)

### Community 121 - "B"
Cohesion: 0.07
Nodes (4): B, es, U, W

### Community 122 - "alerts/api.py"
Cohesion: 0.11
Nodes (23): apps_alerts, Alert rules + notifications API (authenticated; owner-scoped)., error_body(), exception_handler(), page_params(), PageParams, paginated(), Any (+15 more)

### Community 123 - "leaflet.js"
Cohesion: 0.08
Nodes (6): a(), Ci(), l(), me(), x(), ze()

### Community 124 - "_service"
Cohesion: 0.23
Nodes (13): MatchedEventsView, MatchFeedView, MatchReadView, APIView, Request, Response, Mark one match (``{"id": ...}``) or all unread matches (empty body) as read., RuleDetailView (+5 more)

### Community 126 - "dashboard.py"
Cohesion: 0.33
Nodes (9): bar(), coverage_total(), git(), main(), Milestone, parse(), Print the Project Dashboard, computed from docs/PROGRESS.md, git and the last…, render() (+1 more)

### Community 127 - "AlertRepository"
Cohesion: 0.18
Nodes (6): AlertRepository, Any, Database, Delete a rule and its graph edges. Match history is kept (it snapshots the…, Insert once (deterministic key); returns False if this rule already matched the…, create()

### Community 130 - "Handler"
Cohesion: 0.20
Nodes (10): Handler, fake_usgs(), install(), fixture, MonkeyPatch, StandardDatabase, TestCommands, TestEnrichTask (+2 more)

### Community 131 - "ARCHITECTURE.md"
Cohesion: 0.15
Nodes (9): AQL Query Catalogue, Index benchmarks, Reading the results, Results (p50 / p95 ms), Workloads, Academic rubric mapping, ESD §19 concepts, Example AQL questions (README) (+1 more)

### Community 132 - "Major Features"
Cohesion: 0.20
Nodes (10): Alerts / Watch Rules, Analytics, Earthquake Explorer, Event Detail, Live Earthquake Map, Major Features, Operations Dashboard, Real-Time Situational Dashboard (+2 more)

### Community 133 - "QuakeWatch build progress"
Cohesion: 0.22
Nodes (8): L0 Harness, L1 Foundations, L2 Ingestion, L3 Query & API, L4 User features, L5 User interface, L6 Hardening, QuakeWatch build progress

### Community 134 - "ruff_on_edit.py"
Cohesion: 0.33
Nodes (6): find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, shutil, subprocess

### Community 135 - ".configure"
Cohesion: 0.10
Nodes (15): addBox(), addElements(), b(), cn(), configure(), dn(), eo(), fe() (+7 more)

### Community 136 - "qw-map.js"
Cohesion: 0.29
Nodes (10): bboxParam(), color(), create(), cssVar(), eventLayer(), render(), legendControl(), popup() (+2 more)

### Community 137 - "analytics.js"
Cohesion: 0.33
Nodes (8): distributions(), latency(), loadSection(), peak(), revisions(), run(), stats(), timeseries()

### Community 138 - "ResearchRepository"
Cohesion: 0.20
Nodes (6): Any, Database, Insert unless the owner already has ``max_per_user`` snapshots (serialised)., ``[[event_key, revision_number], ...]`` for matching live events, capped at…, Request provenance of the ingestion runs that produced the pinned revisions., ResearchRepository

### Community 140 - "event.js"
Cohesion: 0.29
Nodes (5): changeTable(), delta(), renderProducts(), renderRevisions(), value()

### Community 142 - "map.js"
Cohesion: 0.40
Nodes (9): filters(), form(), readUrl(), refresh(), renderList(), scheduleRefresh(), select(), setAutoRefresh() (+1 more)

### Community 143 - "charts.js"
Cohesion: 0.44
Nodes (8): bar(), cssVar(), figure(), palette(), series(), surface(), table(), themeDefaults()

### Community 144 - "ResearchService"
Cohesion: 0.16
Nodes (6): ExportFile, IntegrityError, Any, Protocol, ResearchService, SnapshotStore

### Community 146 - "F"
Cohesion: 0.24
Nodes (12): F(), G(), h(), j(), k(), ke(), ne(), e() (+4 more)

### Community 147 - "dashboard.js"
Cohesion: 0.39
Nodes (8): eventList(), isoDaysAgo(), renderActivity(), renderMap(), renderSignificant(), renderSummary(), stat(), strongestCard()

### Community 148 - "AppSettings"
Cohesion: 0.18
Nodes (6): BaseSettings, AppSettings, field_validator, model_validator, Tests always run against an isolated ``<db>_test`` database., TestSettingsValidation

### Community 149 - "test_health.py"
Cohesion: 0.43
Nodes (7): Client, StandardDatabase, test_inbound_request_id_propagates(), test_live_is_always_ok(), test_malformed_request_id_replaced(), test_ready_checks_dependencies(), test_ready_reports_schema_drift()

### Community 150 - "RunRepository"
Cohesion: 0.17
Nodes (7): Any, ingestion_runs + backfill_jobs bookkeeping (outside the per-record…, RunRepository, FeedSyncService, Scheduled synchronisation of a USGS summary feed (FR-01)., TestFeedSync, TestOperationalRecovery

### Community 151 - "accounts/views.py"
Cohesion: 0.12
Nodes (16): apps_accounts, Meta, SignupForm, HttpRequest, Sign up, log in (with lockout feedback) and log out. Django auth lives in…, signup(), apps_web, Server-rendered pages (PRD §10 information architecture). Data comes from… (+8 more)

### Community 152 - "m"
Cohesion: 0.27
Nodes (10): c(), e(), hi(), m(), Qe(), u(), ve(), xe() (+2 more)

### Community 153 - "StandardDatabase"
Cohesion: 0.09
Nodes (19): _ip(), Any, HttpRequest, body(), Any, Client, fixture, MonkeyPatch (+11 more)

### Community 154 - "env.py"
Cohesion: 0.09
Nodes (18): configured_observers(), Registry of ingestion observers (dependency inversion: ingestion never imports…, EventObserver, Protocol, Participates in the ingestion transaction for inserted/revised events., StandardDatabase, Typed, validated application configuration loaded from environment / .env. All…, build_logging_config() (+10 more)

### Community 155 - "d"
Cohesion: 0.25
Nodes (9): at(), d(), ht(), i(), Li(), Mi(), v(), W() (+1 more)

### Community 156 - "Accessibility audit (WCAG 2.2 AA)"
Cohesion: 0.40
Nodes (5): Accessibility audit (WCAG 2.2 AA), Exceptions (documented, not violations), Findings and fixes, How it is tested, Manual review (criteria tools cannot decide)

### Community 158 - "exclusive_query"
Cohesion: 0.40
Nodes (4): exclusive_query(), Any, Database, Run one AQL statement holding exclusive locks (serialises check-then-insert…

### Community 159 - "ADR-010: Timestamp representation and source/derived separation"
Cohesion: 0.40
Nodes (4): ADR-010: Timestamp representation and source/derived separation, Consequences, Context, Decision

### Community 160 - "Development Phases"
Cohesion: 0.29
Nodes (7): Development Phases, Phase 1 — Database + Ingestion Spine, Phase 2 — Core Application, Phase 3 — Database Depth, Phase 4 — Product Differentiators, Phase 5 — Hardening, Phase 6 — Research Extension

### Community 161 - "Alerts"
Cohesion: 0.40
Nodes (5): 1. `alerts_enabled_rules`, 2. `alerts_last_notified`, 3. `alerts_user_feed`, 4. `alerts_user_rules`, Alerts

### Community 162 - "QuakeWatch design system"
Cohesion: 0.33
Nodes (6): Accessibility checklist (WCAG 2.2 AA), Components, Magnitude ramp, QuakeWatch design system, Tokens, UI states (every data region)

### Community 163 - "research.js"
Cohesion: 0.60
Nodes (5): downloads(), loadSnapshots(), manifestView(), remove(), submit()

### Community 164 - "authenticated_user"
Cohesion: 0.21
Nodes (12): authenticated_user(), AuthUser, The request's user; views using it must enforce ``IsAuthenticated``., Any, APIView, HttpResponse, Request, Response (+4 more)

### Community 165 - "BackfillService"
Cohesion: 0.20
Nodes (11): Command, _date(), Any, BaseCommand, CommandParser, datetime, BackfillRequest, BackfillService (+3 more)

### Community 166 - "oi"
Cohesion: 0.67
Nodes (4): Je(), ni(), oi(), si()

### Community 167 - "Provenance"
Cohesion: 0.67
Nodes (3): 35. `event_raw_payload`, 36. `ingestion_runs_by_ids`, Provenance

### Community 168 - "Research"
Cohesion: 0.67
Nodes (3): 37. `research_rows_from_revisions`, 38. `research_user_snapshots`, Research

### Community 169 - "task_context.py"
Cohesion: 0.27
Nodes (11): _bind_task_context(), _clear_task_context(), _propagate_correlation_id(), Any, Propagate correlation IDs from the enqueuing request/job into Celery tasks. The…, celery_signals, test_eager_task_restores_the_callers_context(), test_publisher_copies_bound_correlation_id_into_headers() (+3 more)

### Community 171 - "manifest.py"
Cohesion: 0.22
Nodes (14): build_manifest(), bundle(), canonical_order(), _cell(), content_sha256(), export_row(), _json_line(), Any (+6 more)

### Community 172 - "Research Directions"
Cohesion: 0.40
Nodes (5): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Research Directions

### Community 173 - "4. Cross-cutting concerns"
Cohesion: 0.24
Nodes (8): CorrelationIdMiddleware, new_correlation_id(), HttpRequest, HttpResponse, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs., Log endpoint/duration/outcome for every request and feed API latency metrics., RequestTimingMiddleware, 4. Cross-cutting concerns

### Community 174 - "15. Observability"
Cohesion: 0.50
Nodes (4): 15. Observability, Health Endpoints, Metrics, Structured Log Fields

### Community 175 - "safe_usgs_url"
Cohesion: 0.20
Nodes (9): Only https links on usgs.gov hosts are rendered as links. The stored source…, safe_usgs_url(), 9. User interface (L5), 2026-09-25 — L4 user features (alerts, saved searches, research, operations, accounts), 2026-09-25 — L5 user interface, Security Review Log, parametrize, test_parse_days() (+1 more)

### Community 176 - "de"
Cohesion: 0.21
Nodes (4): ce(), de, dt(), he()

### Community 177 - "regions.py"
Cohesion: 0.29
Nodes (6): DerivedRegion, Derive an application region from a USGS ``place`` string (pure,…, region_from_place(), slugify(), TestRegions, unicodedata

### Community 179 - ".test_authenticated_request_queues_enrichment"
Cohesion: 0.22
Nodes (3): MonkeyPatch, TestEnrichEndpoint, TestMap

### Community 181 - "p"
Cohesion: 0.22
Nodes (9): Ae(), be(), De(), ei(), Ie(), ii(), p(), pe() (+1 more)

### Community 182 - "AlertRuleObserver"
Cohesion: 0.32
Nodes (5): AlertRuleObserver, Any, Database, datetime, timedelta

### Community 183 - ".handle"
Cohesion: 0.36
Nodes (5): Command, _index_table(), Any, BaseCommand, CommandParser

### Community 184 - "QuakeWatch operations runbook"
Cohesion: 0.29
Nodes (7): 1. Start, stop, upgrade, 3. Common incidents, 4. Data tasks, 5. Backup and restore, 6. Secrets and access, 7. Release checklist, QuakeWatch operations runbook

### Community 186 - "detect_git_sha"
Cohesion: 0.40
Nodes (4): detect_git_sha(), Path, Explicit QW_APP_VERSION (container builds) or the checkout's git SHA., Short commit SHA from ``.git`` files (no subprocess); None outside a git…

### Community 187 - "ADR-007: Raw-data retention policy"
Cohesion: 0.40
Nodes (4): ADR-007: Raw-data retention policy, Consequences, Context, Decision

### Community 188 - "ready"
Cohesion: 0.53
Nodes (6): live(), HttpRequest, require_GET, ready(), JsonResponse, never_cache

### Community 189 - "3. Target Users"
Cohesion: 0.40
Nodes (5): 3. Target Users, Administrators, Disaster-management learners and analysts, General users, Students and researchers

### Community 191 - "ADR-011: Server-rendered pages with API-driven islands"
Cohesion: 0.40
Nodes (4): ADR-011: Server-rendered pages with API-driven islands, Alternatives considered, Consequences, Context

### Community 192 - "FakeClock"
Cohesion: 0.18
Nodes (7): breaker(), clock(), FakeClock, fixture, MonkeyPatch, TestCircuitBreaker, __getattr__()

### Community 193 - "Dependencies and why each exists"
Cohesion: 0.40
Nodes (4): Dependencies and why each exists, Development / test, Frontend (vendored under `static/vendor`, no build step, no CDN at runtime), Runtime (Python)

### Community 194 - "13. Success Metrics"
Cohesion: 0.50
Nodes (4): 13. Success Metrics, Academic, Product, Research Readiness

### Community 201 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 202 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

### Community 203 - "Proposed ArangoDB Model"
Cohesion: 0.67
Nodes (3): Document Collections, Edge Collections, Proposed ArangoDB Model

## Knowledge Gaps
- **387 isolated node(s):** `Standing instructions from the project owner (always follow)`, `Boundary rules (enforced by tests/architecture)`, `Commands`, `Project tooling (.claude/)`, `Safety wording` (+382 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1006 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **40 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `recover()` connect `operations/api.py` to `ingestion/services.py`, `get_db`, `BackfillService`, `RunRepository`?**
  _High betweenness centrality (0.400) - this node is a cross-community bridge._
- **Why does `Consequences` connect `operations/api.py` to `tn`?**
  _High betweenness centrality (0.399) - this node is a cross-community bridge._
- **Why does `xt` connect `xt` to `chart.umd.min.js`, `tn`, `.getContext`, `n`, `qt`?**
  _High betweenness centrality (0.326) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `CircuitBreaker` (e.g. with `CircuitOpen` and `ResilientHttpClient`) actually correct?**
  _`CircuitBreaker` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Standing instructions from the project owner (always follow)`, `Boundary rules (enforced by tests/architecture)`, `Commands` to the rest of the system?**
  _387 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `QuakeWatch` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `typing` be split into smaller, more focused modules?**
  _Cohesion score 0.05964912280701754 - nodes in this community are weakly interconnected._