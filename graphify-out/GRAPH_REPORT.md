# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 186 files · ~98,925 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .css 6, (none) 4, .geojson 3)

## Summary
- 3512 nodes · 8808 edges · 178 communities (147 shown, 31 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 530 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `900125bc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- StandardDatabase
- chart.umd.min.js
- Django Security Best Practices
- overview
- metrics.py
- django_apps
- get_db
- test_ingestion_services.py
- Django + Celery Async Task Patterns
- .update
- Frontend Accessibility Patterns
- vendor_assets.py
- RunRepository
- a11y-architect.md
- Review Priorities
- Architecture Decision Records
- Review Priorities
- Security Reviewer
- test_boundaries.py
- de
- QuakeWatch — Engineering System Design (ESD)
- Document Collections
- l
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
- e
- 6. Constraints and Indexes
- 12. Research-Paper Potential
- NormalizedRecord
- 6. Scope
- Any
- qw.js
- 20. Research Extensions
- 4. Source Integration
- aql_catalog.py
- to_iso
- IngestionRepository
- B
- QuakeWatch Architecture
- entrypoint.sh
- quakewatch
- IngestionPipeline
- manifest.py
- tn
- revision_policy.py
- s
- Zi
- BackfillService
- test_user_features.py
- core/api.py
- CanonicalEventInput
- .from_params
- errors.py
- oo
- tasks.py
- load_fixture
- n
- ingestion/services.py
- api_urls.py
- EventFilter
- test_pages.py
- web/views.py
- Analytics
- bootstrap.bundle.min.js
- AlertRuleObserver
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
- .hide
- event_key
- ADR-003: Canonical event + immutable revisions, with identity claims
- test_alerts.py
- security.py
- signals.py
- earthquakes/api.py
- es
- authenticated_user
- leaflet.js
- alerts/api.py
- sn
- dashboard.py
- run_query
- Qi
- Zs
- o
- ARCHITECTURE.md
- Major Features
- QuakeWatch build progress
- ruff_on_edit.py
- remove
- qw-map.js
- analytics.js
- ResearchRepository
- Ss
- event.js
- core/apps.py
- map.js
- charts.js
- Any
- hs
- F
- dashboard.js
- AppSettings
- test_health.py
- analytics/apps.py
- accounts/views.py
- m
- StandardDatabase
- os
- d
- .form_invalid
- bi
- O
- geo/apps.py
- Development Phases
- Alerts
- QuakeWatch design system
- research.js
- ADR-004: Polling and freshness strategy
- normalize_feature
- oi
- Provenance
- Research
- pytest_sessionfinish
- Research Directions
- 15. Observability
- safe_usgs_url
- 18. Deployment Profiles
- 3. Technology Stack
- status.js

## God Nodes (most connected - your core abstractions)
1. `tn` - 127 edges
2. `run_query()` - 70 edges
3. `CircuitBreaker` - 60 edges
4. `n()` - 59 edges
5. `IngestionPipeline` - 58 edges
6. `get_db()` - 50 edges
7. `to_iso()` - 45 edges
8. `s()` - 45 edges
9. `EventFilter` - 43 edges
10. `ValidationFailed` - 42 edges

## Surprising Connections (you probably didn't know these)
- `Review history` --references--> `_key()`  [INFERRED]
  docs/adr/ADR-003-canonical-event-and-revisions.md → apps/accounts/security.py
- `5. Transactions and concurrency` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Revisions` --references--> `event_revisions()`  [INFERRED]
  docs/adr/ADR-003-canonical-event-and-revisions.md → apps/earthquakes/api.py
- `39. `event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/AQL_QUERIES.md → apps/earthquakes/api.py
- ``event_revisions`` --references--> `event_revisions()`  [INFERRED]
  docs/ESD.md → apps/earthquakes/api.py

## Import Cycles
- None detected.

## Communities (178 total, 31 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.07
Nodes (27): Academic Requirements Covered, Competitor / Reference Systems, Core, Core Workflow, Current Recommended Milestone, Data Integrity Rules, Document Collections, Documentation (+19 more)

### Community 1 - "StandardDatabase"
Cohesion: 0.12
Nodes (10): parametrize, StandardDatabase, Two writers increment the same doc; conflict retries must not lose an update., TestCollectionRules, TestDataMigrations, TestMigrations, TestQueryRunner, TestTransactions (+2 more)

### Community 2 - "chart.umd.min.js"
Cohesion: 0.03
Nodes (62): ai(), at(), average(), beforeDatasetDraw(), beforeDatasetsDraw(), beforeDraw(), beforeUpdate(), ca (+54 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "overview"
Cohesion: 0.11
Nodes (29): page_params(), PageParams, paginated(), Parse ``page``/``page_size`` query params with strict bounds (pagination is…, _AdminAction, audit_log(), BackfillView, dead_letters() (+21 more)

### Community 5 - "metrics.py"
Cohesion: 0.07
Nodes (40): counters(), _counters_key(), incr(), _index_key(), observe(), percentile(), ping(), Exception (+32 more)

### Community 6 - "django_apps"
Cohesion: 0.09
Nodes (15): AccountsConfig, AppConfig, AlertsConfig, AppConfig, EarthquakesConfig, AppConfig, IngestionConfig, AppConfig (+7 more)

### Community 7 - "get_db"
Cohesion: 0.07
Nodes (44): _cached_db(), _connect(), database_name(), drop_database(), ensure_database(), get_client(), get_db(), ping() (+36 more)

### Community 8 - "test_ingestion_services.py"
Cohesion: 0.11
Nodes (24): Upstream payload does not match the expected contract., SourceSchemaError, ValidationFailed, FetchResult, Any, NoReturn, Response, ResilientHttpClient (+16 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - ".update"
Cohesion: 0.06
Nodes (26): addBox(), afterDraw(), afterEvent(), afterUpdate(), Ba(), configure(), Ee(), f() (+18 more)

### Community 11 - "Frontend Accessibility Patterns"
Cohesion: 0.10
Nodes (20): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Complete Accessible Form, Custom Dropdown (+12 more)

### Community 12 - "vendor_assets.py"
Cohesion: 0.16
Nodes (9): PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, fetch(), main(), Re-record the real USGS payloads used by the contract tests…, fetch(), main(), Download pinned frontend assets into static/vendor and verify their SHA-256…, sys (+1 more)

### Community 13 - "RunRepository"
Cohesion: 0.06
Nodes (39): Any, T, Narrow python-arango's ``Result[T]`` union for APIs that never return None. We…, Like :func:`sync` for APIs where None is a legitimate answer (e.g.…, sync(), sync_optional(), applied_version(), apply_schema() (+31 more)

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

### Community 20 - "de"
Cohesion: 0.19
Nodes (4): ce(), de, dt(), he()

### Community 21 - "QuakeWatch — Engineering System Design (ESD)"
Cohesion: 0.17
Nodes (12): 11. Alert Engine, 12. Research Data Layer, 14. Security, 17. CI/CD, 1. Engineering Strategy, 21. Architecture Decision Records, 22. External References, 2. High-Level Architecture (+4 more)

### Community 22 - "Document Collections"
Cohesion: 0.15
Nodes (13): 5. ArangoDB Data Model, `alert_matches`, `alert_rules`, `dead_letters`, Document Collections, Edge Collections, `event_revisions`, `events` (+5 more)

### Community 23 - "l"
Cohesion: 0.06
Nodes (30): aa(), Ae(), Bn(), _calculateBarIndexPixels(), _calculateBarValuePixels(), da(), _getAxis(), _getAxisCount() (+22 more)

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
Cohesion: 0.05
Nodes (41): CircuitBreaker, Handler, FakeCatalog, Any, datetime, MonkeyPatch, parametrize, Request (+33 more)

### Community 28 - "10. Frontend Design"
Cohesion: 0.25
Nodes (8): 10. Frontend Design, Analytics, Dashboard, Event Detail, Explorer, Live Map, Operations, Research Lab

### Community 29 - "QuakeWatch — Product Requirements Document (PRD)"
Cohesion: 0.12
Nodes (17): 10. Information Architecture, 13. Success Metrics, 14. Risks and Mitigations, 15. Official References, 1. Product Vision, 2. Why This Product Should Exist, 3. Target Users, 5. Product Principles (+9 more)

### Community 30 - "16. Testing Strategy"
Cohesion: 0.29
Nodes (7): 16. Testing Strategy, Contract, End-to-End, Integration, Performance, Resilience, Unit

### Community 31 - "4. User Problems and Product Responses"
Cohesion: 0.29
Nodes (7): 4. User Problems and Product Responses, P1 — Data is available but fragmented, P2 — Earthquake records change after first publication, P3 — Maps alone are not enough, P4 — Alerts can be opaque, P5 — Research datasets are difficult to reproduce, P6 — Data trust is invisible

### Community 32 - "StandardDatabase"
Cohesion: 0.13
Nodes (13): body(), Any, Client, MonkeyPatch, parametrize, StandardDatabase, A polling gap (reviewed version observed 6 h late) must not inflate the metric., TestAnalytics (+5 more)

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
Nodes (31): breakdowns(), distributions(), latency(), api_view, Request, Response, Analytics API (FR-09). All windows are ``?days=N`` (1..3660, default 30)., revisions() (+23 more)

### Community 41 - "e"
Cohesion: 0.12
Nodes (15): an(), b(), cn(), dn(), e(), fe(), gi(), hn() (+7 more)

### Community 42 - "6. Constraints and Indexes"
Cohesion: 0.40
Nodes (5): 6. Constraints and Indexes, `alert_rules`, `event_revisions`, `events`, `ingestion_runs`

### Community 43 - "12. Research-Paper Potential"
Cohesion: 0.40
Nodes (5): 12. Research-Paper Potential, RQ1 — Event Revision Dynamics, RQ2 — Multi-Source Latency and Consistency, RQ3 — Revision-Likelihood Modeling, RQ4 — Spatiotemporal Sequence Characterization

### Community 44 - "NormalizedRecord"
Cohesion: 0.11
Nodes (17): NormalizedRecord, _event_doc(), EventChange, unit(), _pick_primary(), Any, Database, Exception (+9 more)

### Community 45 - "6. Scope"
Cohesion: 0.40
Nodes (5): 6. Scope, MVP, Out of Scope, Research Track, Version 1.1

### Community 46 - "Any"
Cohesion: 0.10
Nodes (10): EventQueryService, EventReader, present_event(), Any, Protocol, Saved explorer queries (FR-12). Filters are stored in canonical form and re-…, SavedSearchService, SavedSearchStore (+2 more)

### Community 47 - "qw.js"
Cohesion: 0.14
Nodes (25): ago(), api(), append(), band(), clear(), csrfToken(), errorState(), eventLink() (+17 more)

### Community 48 - "20. Research Extensions"
Cohesion: 0.50
Nodes (4): 20. Research Extensions, A. Multi-Source Concordance, B. Revision Intelligence, C. Spatiotemporal Graph

### Community 49 - "4. Source Integration"
Cohesion: 0.50
Nodes (4): 4.1 USGS Summary Feed Adapter, 4.2 Catalog API Adapter, 4.3 Detail Feed Adapter, 4. Source Integration

### Community 50 - "aql_catalog.py"
Cohesion: 0.15
Nodes (14): explain(), indexes_used(), collect(), Any, Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics…, Index names (or types) used by a plan, including traversal edge indexes., Command, _index_table() (+6 more)

### Community 51 - "to_iso"
Cohesion: 0.11
Nodes (17): from_epoch_ms(), from_iso(), datetime, to_iso(), BackfillInterrupted, _correlation_id(), _error_dict(), FeedSyncService (+9 more)

### Community 52 - "IngestionRepository"
Cohesion: 0.09
Nodes (11): network_name(), Reference names for common ANSS / USGS contributing network codes (pure). Only…, dead_letter_key(), IngestionRepository, KnownEvent, Database, Fast-path lookup (unique index) of current payload hashes by preferred id., Live canonical events claimed by any of ``ids`` (primary-key lookups only).… (+3 more)

### Community 53 - "B"
Cohesion: 0.11
Nodes (3): B, U, x()

### Community 54 - "QuakeWatch Architecture"
Cohesion: 0.18
Nodes (10): Any, Deterministic, JSON-safe representation (only set fields; sorted keys)., 1. High-level design, 2. Module map and layering, 3. Data model (ArangoDB), 5. Transactions and concurrency, 6. Ingestion (L2), 7. Query & API layer (L3) (+2 more)

### Community 69 - "IngestionPipeline"
Cohesion: 0.19
Nodes (22): IngestionPipeline, arango_db(), StandardDatabase, Clean database per test (collections truncated, schema/indexes kept)., count(), feature(), Any, parametrize (+14 more)

### Community 70 - "manifest.py"
Cohesion: 0.07
Nodes (33): BoundingBox, haversine_km(), InvalidGeometry, Geodesic helpers (pure). Distances use the haversine formula on a spherical…, Viewport box. ``west > east`` means the box crosses the antimeridian., Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n —…, GeoJSON polygon rings (lon, lat), split at the antimeridian when needed., Approximate fraction of the globe covered (for choosing clustering granularity). (+25 more)

### Community 71 - "tn"
Cohesion: 0.04
Nodes (16): Checklist, When to Activate, afterDatasetsUpdate(), d(), Ie(), ke(), onClick(), Pn() (+8 more)

### Community 72 - "revision_policy.py"
Cohesion: 0.16
Nodes (20): diff(), field_changed(), FieldChange, FieldRule, _numeric_changed(), Any, Versioned meaningful-revision policy (ESD §8) (pure). A *revision* is recorded…, Meaningful changes between two source states (ordered as in ``TRACKED_FIELDS``). (+12 more)

### Community 73 - "s"
Cohesion: 0.08
Nodes (17): bo, buildTicks(), determineDataLimits(), getRange(), H(), _i(), ii(), ji() (+9 more)

### Community 75 - "BackfillService"
Cohesion: 0.09
Nodes (26): apps_ingestion, Command, _date(), Any, BaseCommand, CommandParser, datetime, BackfillRequest (+18 more)

### Community 76 - "test_user_features.py"
Cohesion: 0.08
Nodes (41): is_important(), Earthquake domain model (pure). :class:`CanonicalEventInput` is the source-…, Events that get eager detail enrichment (ESD §4.3 "important events")., _Lenient, BaseModel, Strict contract for USGS GeoJSON payloads (summary feed, catalog query, detail…, Top level only; features are validated one by one so a bad record never sinks a…, UsgsCatalogCount (+33 more)

### Community 77 - "core/api.py"
Cohesion: 0.17
Nodes (14): error_body(), exception_handler(), Any, Exception, Response, Shared API plumbing: error envelope, exception mapping, pagination parameters., Research snapshot API (FR-13): create, list, manifest, export (throttled),…, django_http (+6 more)

### Community 78 - "CanonicalEventInput"
Cohesion: 0.10
Nodes (15): CanonicalEventInput, Any, BaseModel, datetime, field_validator, model_validator, JSON-safe source state (persisted on the event and in revision snapshots)., ADR-008: Multi-source canonicalization (research track) (+7 more)

### Community 79 - ".from_params"
Cohesion: 0.16
Nodes (7): number(), text(), timestamp(), Radius, Parse query parameters (strings) or a canonical dict; raise ValidationFailed on…, TestEventFilter, TestSearchCompilation

### Community 80 - "errors.py"
Cohesion: 0.09
Nodes (24): CircuitOpen, Conflict, NotFound, PermissionDenied, Any, Exception, pydantic_details(), QuakeWatchError (+16 more)

### Community 81 - "oo"
Cohesion: 0.17
Nodes (5): eo(), io(), no(), oo, zi()

### Community 82 - "tasks.py"
Cohesion: 0.09
Nodes (29): job_lock(), Yield True if the lock was acquired; the body should skip work when False., backoff_delay(), Full-jitter exponential backoff for retry ``attempt`` (1-based). An upstream…, UpstreamError that also carries the provenance of the failed call., UpstreamRequestFailed, build_usgs_client(), usgs_breaker() (+21 more)

### Community 83 - "load_fixture"
Cohesion: 0.19
Nodes (10): load_fixture(), TestCatalogAndDetail, api_db(), fixture, Shared read-only dataset: seeded once, re-seeded only if a mutating test wiped…, Fresh seeded dataset for tests that mutate data., _seed(), seeded() (+2 more)

### Community 84 - "n"
Cohesion: 0.06
Nodes (14): Be(), ei(), fn(), gn(), je(), n(), ne(), numeric() (+6 more)

### Community 85 - "ingestion/services.py"
Cohesion: 0.06
Nodes (70): Removal of a user's ArangoDB data when their Django account is deleted., Alert rule model (pure). Rules are data, never executable user code (ESD §11)., Deterministic, explainable rule evaluation (FR-11) (pure). Each condition…, Alert-rule evaluation inside the ingestion transaction (ESD §7 "EVALUATE ALERT…, match_key(), Alert rules, matches and their graph edges. Every user-facing query is scoped…, Alert rule use cases (FR-10, FR-11): owner-scoped CRUD, dry-run preview,…, Analytics aggregations (FR-09). Every query is a registered… (+62 more)

### Community 86 - "api_urls.py"
Cohesion: 0.18
Nodes (9): apps_alerts, apps_analytics, apps_earthquakes, apps_operations, apps_web, Server-rendered pages (PRD §10 information architecture). Data comes from…, Versioned JSON API routes (/api/v1/...)., django_contrib (+1 more)

### Community 87 - "EventFilter"
Cohesion: 0.10
Nodes (15): EventFilter, Human-readable query summary for the explorer and exports., compile_filter(), CompiledQuery, EventRepository, Any, Database, Compact points ``[key, lat, lon, mag, depth, occurred_at]``; flag if over the… (+7 more)

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
Cohesion: 0.08
Nodes (48): be(), bi(), Ce(), D(), De(), _e(), ei(), F() (+40 more)

### Community 92 - "AlertRuleObserver"
Cohesion: 0.22
Nodes (8): ThrottledModelBackend, AlertRuleObserver, Any, Database, datetime, timedelta, 8. User features (L4), ModelBackend

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
Cohesion: 0.06
Nodes (13): St, color(), Gt(), It(), jt(), kt(), mt(), qt() (+5 more)

### Community 101 - "xt"
Cohesion: 0.13
Nodes (3): as(), ts(), xt

### Community 103 - "AuditRepository"
Cohesion: 0.18
Nodes (5): AuditRepository, OperationsRepository, Any, Database, Append-only audit trail. There is intentionally no update or delete method.

### Community 104 - "RuleConditions"
Cohesion: 0.06
Nodes (28): BaseModel, field_validator, model_validator, All given conditions must hold (logical AND). At least one condition is…, Create/replace payload. ``cooldown_minutes`` suppresses repeat notifications…, RuleConditions, RuleInput, RulePatch (+20 more)

### Community 105 - "i"
Cohesion: 0.15
Nodes (13): bs(), ct(), Fs(), ge(), is(), ks(), ms(), ss() (+5 more)

### Community 106 - "Search"
Cohesion: 0.25
Nodes (8): 41. `events_deepest`, 42. `events_in_viewport`, 43. `events_location_text`, 44. `events_recent_strong`, 45. `events_strongest_in_range`, 46. `events_tsunami_flagged`, 47. `events_within_radius`, Search

### Community 107 - "ho"
Cohesion: 0.09
Nodes (12): beforeLayout(), buildLookupTable(), _generate(), getDecimalForValue(), _getTimestampsForTable(), getValueForPixel(), Go(), ho() (+4 more)

### Community 108 - "Operations"
Cohesion: 0.29
Nodes (7): 29. `ops_audit_recent`, 30. `ops_backfill_jobs`, 31. `ops_dead_letters`, 32. `ops_latest_run`, 33. `ops_recent_runs`, 34. `ops_run_stats`, Operations

### Community 110 - "Maintenance"
Cohesion: 0.40
Nodes (5): 25. `backfill_active_jobs`, 26. `ingest_repoint_claims`, 27. `ingest_resolve_dead_letters`, 28. `runs_abandon_stale`, Maintenance

### Community 111 - "ps"
Cohesion: 0.07
Nodes (7): ps, qt, vs, Bt(), Ft(), rs(), zt()

### Community 112 - "operations.js"
Cohesion: 0.31
Nodes (12): actionResult(), backfill(), loadAudit(), loadDeadLetters(), loadDiagnostics(), loadJobs(), loadRuns(), renderOverview() (+4 more)

### Community 113 - ".getContext"
Cohesion: 0.12
Nodes (10): ao(), Bi(), Ci(), co(), Do(), Fi(), inXRange(), inYRange() (+2 more)

### Community 115 - "event_key"
Cohesion: 0.22
Nodes (7): event_key(), Deterministic ArangoDB ``_key`` for the first-seen identity of a source event., Identity claims (`event_identities`), ADR-006: Research snapshot reproducibility, Consequences, Context, Decision

### Community 116 - "ADR-003: Canonical event + immutable revisions, with identity claims"
Cohesion: 0.22
Nodes (8): ADR-003: Canonical event + immutable revisions, with identity claims, Atomicity and failure isolation, Canonical record, Consequences, Context, Decision, Review history, Revisions

### Community 117 - "test_alerts.py"
Cohesion: 0.22
Nodes (18): alice(), body(), create_rule(), ingest(), Any, Client, fixture, MonkeyPatch (+10 more)

### Community 118 - "security.py"
Cohesion: 0.21
Nodes (13): AttemptDecision, _incr(), is_locked(), _key(), _known(), Login brute-force protection (PRD NFR security: rate limits). Attempts are…, Count this attempt and decide whether it may proceed to password verification., Read-only view (for display/audit); enforcement happens in… (+5 more)

### Community 119 - "signals.py"
Cohesion: 0.16
Nodes (18): delete_user_data(), work(), StandardDatabase, Atomically delete rules (+ edges), matches, saved searches, snapshots, user…, _meta(), _on_login(), _on_login_failed(), _on_user_deleted() (+10 more)

### Community 120 - "earthquakes/api.py"
Cohesion: 0.22
Nodes (19): event_detail(), event_list(), event_map(), event_provenance(), event_relationships(), event_revisions(), EventEnrichView, api_view (+11 more)

### Community 121 - "es"
Cohesion: 0.08
Nodes (3): es, ot, W

### Community 122 - "authenticated_user"
Cohesion: 0.19
Nodes (13): authenticated_user(), AuthUser, Request, The request's user; views using it must enforce ``IsAuthenticated``., Any, APIView, HttpResponse, Request (+5 more)

### Community 123 - "leaflet.js"
Cohesion: 0.08
Nodes (9): a(), Ci(), ei(), ii(), l(), me(), ri(), x() (+1 more)

### Community 124 - "alerts/api.py"
Cohesion: 0.23
Nodes (14): MatchedEventsView, MatchFeedView, MatchReadView, APIView, Request, Response, Alert rules + notifications API (authenticated; owner-scoped)., Mark one match (``{"id": ...}``) or all unread matches (empty body) as read. (+6 more)

### Community 125 - "sn"
Cohesion: 0.13
Nodes (3): addElements(), en, sn

### Community 126 - "dashboard.py"
Cohesion: 0.33
Nodes (9): bar(), coverage_total(), git(), main(), Milestone, parse(), Print the Project Dashboard, computed from docs/PROGRESS.md, git and the last…, render() (+1 more)

### Community 127 - "run_query"
Cohesion: 0.17
Nodes (9): AlertRepository, Any, Database, Delete a rule and its graph edges. Match history is kept (it snapshots the…, Insert once (deterministic key); returns False if this rule already matched the…, Database, QueryResult, run_query() (+1 more)

### Community 128 - "Qi"
Cohesion: 0.14
Nodes (3): d(), Qi, Pi()

### Community 130 - "o"
Cohesion: 0.12
Nodes (13): a(), Di(), g(), g(), m(), o(), p(), pi() (+5 more)

### Community 131 - "ARCHITECTURE.md"
Cohesion: 0.18
Nodes (6): AQL Query Catalogue, Index justification (ESD §6), Dependencies and why each exists, Development / test, Frontend (vendored under `static/vendor`, no build step, no CDN at runtime), Runtime (Python)

### Community 132 - "Major Features"
Cohesion: 0.20
Nodes (10): Alerts / Watch Rules, Analytics, Earthquake Explorer, Event Detail, Live Earthquake Map, Major Features, Operations Dashboard, Real-Time Situational Dashboard (+2 more)

### Community 133 - "QuakeWatch build progress"
Cohesion: 0.22
Nodes (8): L0 Harness, L1 Foundations, L2 Ingestion, L3 Query & API, L4 User features, L5 User interface, L6 Hardening, QuakeWatch build progress

### Community 134 - "ruff_on_edit.py"
Cohesion: 0.33
Nodes (6): find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, shutil, subprocess

### Community 135 - "remove"
Cohesion: 0.17
Nodes (3): Ln, remove(), ns()

### Community 136 - "qw-map.js"
Cohesion: 0.29
Nodes (10): bboxParam(), color(), create(), cssVar(), eventLayer(), render(), legendControl(), popup() (+2 more)

### Community 137 - "analytics.js"
Cohesion: 0.33
Nodes (8): distributions(), latency(), loadSection(), peak(), revisions(), run(), stats(), timeseries()

### Community 138 - "ResearchRepository"
Cohesion: 0.23
Nodes (5): Any, Database, Insert unless the owner already has ``max_per_user`` snapshots (serialised)., Request provenance of the ingestion runs that produced the pinned revisions., ResearchRepository

### Community 140 - "event.js"
Cohesion: 0.29
Nodes (5): changeTable(), delta(), renderProducts(), renderRevisions(), value()

### Community 142 - "map.js"
Cohesion: 0.40
Nodes (9): filters(), form(), readUrl(), refresh(), renderList(), scheduleRefresh(), select(), setAutoRefresh() (+1 more)

### Community 143 - "charts.js"
Cohesion: 0.44
Nodes (8): bar(), cssVar(), figure(), palette(), series(), surface(), table(), themeDefaults()

### Community 144 - "Any"
Cohesion: 0.24
Nodes (3): Any, Protocol, SnapshotStore

### Community 146 - "F"
Cohesion: 0.22
Nodes (12): F(), G(), h(), j(), k(), ke(), ne(), e() (+4 more)

### Community 147 - "dashboard.js"
Cohesion: 0.39
Nodes (8): eventList(), isoDaysAgo(), renderActivity(), renderMap(), renderSignificant(), renderSummary(), stat(), strongestCard()

### Community 148 - "AppSettings"
Cohesion: 0.06
Nodes (29): CorrelationIdMiddleware, new_correlation_id(), HttpRequest, HttpResponse, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs., Log endpoint/duration/outcome for every request and feed API latency metrics., RequestTimingMiddleware, _bind_task_context() (+21 more)

### Community 149 - "test_health.py"
Cohesion: 0.43
Nodes (7): Client, StandardDatabase, test_inbound_request_id_propagates(), test_live_is_always_ok(), test_malformed_request_id_replaced(), test_ready_checks_dependencies(), test_ready_reports_schema_drift()

### Community 151 - "accounts/views.py"
Cohesion: 0.18
Nodes (12): apps_accounts, Meta, SignupForm, HttpRequest, Sign up, log in (with lockout feedback) and log out. Django auth lives in…, signup(), django, django_contrib_auth_forms (+4 more)

### Community 152 - "m"
Cohesion: 0.31
Nodes (9): be(), De(), m(), p(), pe(), ve(), xe(), ye() (+1 more)

### Community 153 - "StandardDatabase"
Cohesion: 0.07
Nodes (29): _ip(), Any, HttpRequest, Authentication backend that refuses attempts for locked (username, IP) pairs., client_ip(), Any, Client address as seen by our own infrastructure (spoof-resistant). With…, django_contrib_auth_backends (+21 more)

### Community 154 - "os"
Cohesion: 0.25
Nodes (4): Celery application. Beat schedule is defined in apps.ingestion.schedule., django_core_asgi, django_core_wsgi, os

### Community 155 - "d"
Cohesion: 0.29
Nodes (8): at(), d(), i(), Li(), Mi(), v(), W(), zi()

### Community 156 - ".form_invalid"
Cohesion: 0.29
Nodes (5): Any, HttpResponse, QuakeWatchLoginView, AuthenticationForm, LoginView

### Community 157 - "bi"
Cohesion: 0.29
Nodes (7): bi(), c(), e(), hi(), Qe(), Ti(), u()

### Community 158 - "O"
Cohesion: 0.20
Nodes (10): ci(), Ae(), Ie(), Jt(), Le(), O(), Qt(), Re() (+2 more)

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

### Community 164 - "ADR-004: Polling and freshness strategy"
Cohesion: 0.40
Nodes (4): ADR-004: Polling and freshness strategy, Consequences, Context, Decision

### Community 165 - "normalize_feature"
Cohesion: 0.09
Nodes (23): _csv(), normalize_feature(), reject(), payload_hash(), Any, Stable SHA-256 of a JSON payload (sorted keys, compact separators)., RecordRejected, _summarize() (+15 more)

### Community 166 - "oi"
Cohesion: 0.67
Nodes (4): Je(), ni(), oi(), si()

### Community 167 - "Provenance"
Cohesion: 0.67
Nodes (3): 35. `event_raw_payload`, 36. `ingestion_runs_by_ids`, Provenance

### Community 168 - "Research"
Cohesion: 0.67
Nodes (3): 37. `research_rows_from_revisions`, 38. `research_user_snapshots`, Research

### Community 169 - "pytest_sessionfinish"
Cohesion: 0.67
Nodes (3): Session, pytest_sessionfinish(), Record the outcome of full runs in var/test-status.json for…

### Community 172 - "Research Directions"
Cohesion: 0.40
Nodes (5): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Research Directions

### Community 174 - "15. Observability"
Cohesion: 0.50
Nodes (4): 15. Observability, Health Endpoints, Metrics, Structured Log Fields

### Community 175 - "safe_usgs_url"
Cohesion: 0.16
Nodes (11): Only https links on usgs.gov hosts are rendered as links. The stored source…, safe_usgs_url(), ADR-011: Server-rendered pages with API-driven islands, Alternatives considered, Consequences, Context, Decision, 9. User interface (L5) (+3 more)

### Community 176 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 177 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

## Knowledge Gaps
- **371 isolated node(s):** `Meta`, `entrypoint.sh script`, `quakewatch`, `Prompt Defense Baseline`, `Your Role` (+366 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 954 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `recover()` connect `tasks.py` to `ADR-004: Polling and freshness strategy`, `get_db`, `BackfillService`, `RunRepository`, `to_iso`, `ingestion/services.py`?**
  _High betweenness centrality (0.349) - this node is a cross-community bridge._
- **Why does `Consequences` connect `ADR-004: Polling and freshness strategy` to `tasks.py`, `tn`?**
  _High betweenness centrality (0.349) - this node is a cross-community bridge._
- **Why does `xt` connect `xt` to `St`, `chart.umd.min.js`, `tn`, `ps`?**
  _High betweenness centrality (0.284) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `CircuitBreaker` (e.g. with `CircuitOpen` and `ResilientHttpClient`) actually correct?**
  _`CircuitBreaker` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Meta`, `entrypoint.sh script`, `quakewatch` to the rest of the system?**
  _371 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `QuakeWatch` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._
- **Should `StandardDatabase` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._