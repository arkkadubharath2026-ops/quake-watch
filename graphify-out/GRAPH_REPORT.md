# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 117 files · ~42,511 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 4, .geojson 3, .example 1)

## Summary
- 1318 nodes · 2701 edges · 103 communities (80 shown, 23 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 139 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aa0bad1b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- StandardDatabase
- to_iso
- Django Security Best Practices
- api.py
- metrics.py
- django_apps
- client.py
- services.py
- Django + Celery Async Task Patterns
- CorrelationIdMiddleware
- Frontend Accessibility Patterns
- env.py
- sync
- a11y-architect.md
- Review Priorities
- Architecture Decision Records
- Review Priorities
- Security Reviewer
- Path
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
- BaseCommand
- 13. Reliability
- 11. Competitive Positioning
- 7. Core User Journeys
- 9. Non-Functional Requirements
- ADR-001: ArangoDB as the primary database
- ADR-002: Modular Django monolith with background workers
- ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB
- ADR-010: Timestamp representation and source/derived separation
- ARCHITECTURE.md
- 6. Constraints and Indexes
- 12. Research-Paper Potential
- 3. Target Users
- 6. Scope
- urls.py
- 15. Observability
- 20. Research Extensions
- 4. Source Integration
- 13. Success Metrics
- arangodb-reviewer.md
- CircuitBreaker
- 18. Deployment Profiles
- 3. Technology Stack
- entrypoint.sh
- quakewatch
- IngestionPipeline
- test_geo.py
- tasks.py
- revision_policy.py
- test_ingestion_services.py
- RunRepository
- test_tasks_and_commands.py
- normalize_feature
- usgs_models.py
- CanonicalEventInput
- UsgsClient
- errors.py
- pipeline.py
- typing
- ._process_window
- test_usgs_contract.py
- repository.py
- SourceSchemaError
- parse_feed
- AppSettings
- QuakeWatch Architecture
- BackfillInterrupted
- ADR-003: Canonical event + immutable revisions, with identity claims
- run_in_transaction
- usgs.py
- context_processors.py
- .__call__
- Command
- AppConfig
- CommandParser

## God Nodes (most connected - your core abstractions)
1. `CircuitBreaker` - 53 edges
2. `IngestionPipeline` - 37 edges
3. `RunRepository` - 35 edges
4. `BackfillService` - 34 edges
5. `UsgsClient` - 32 edges
6. `sync()` - 31 edges
7. `FeedSyncService` - 23 edges
8. `QuakeWatch — Engineering System Design (ESD)` - 23 edges
9. `IngestionRepository` - 22 edges
10. `QuakeWatch` - 21 edges

## Surprising Connections (you probably didn't know these)
- `5. Transactions and concurrency` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Identity claims (`event_identities`)` --references--> `event_key()`  [INFERRED]
  docs/adr/ADR-003-canonical-event-and-revisions.md → apps/earthquakes/domain.py
- `Runtime (Python)` --references--> `CanonicalEventInput`  [INFERRED]
  docs/DEPENDENCIES.md → apps/earthquakes/domain.py
- `Relational rubric mapping (ESD §19)` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Decision` --references--> `payload_hash()`  [INFERRED]
  docs/adr/ADR-007-raw-data-retention.md → apps/ingestion/normalizer.py

## Import Cycles
- None detected.

## Communities (103 total, 23 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.04
Nodes (49): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Academic Requirements Covered, Alerts / Watch Rules, Analytics, Competitor / Reference Systems (+41 more)

### Community 1 - "StandardDatabase"
Cohesion: 0.12
Nodes (10): parametrize, StandardDatabase, Two writers increment the same doc; conflict retries must not lose an update., TestCollectionRules, TestDataMigrations, TestMigrations, TestQueryRunner, TestTransactions (+2 more)

### Community 2 - "to_iso"
Cohesion: 0.20
Nodes (10): from_epoch_ms(), from_iso(), Time utilities. Timestamps are persisted as fixed-width ISO-8601 UTC strings…, to_iso(), utc_now(), enrichment_is_stale(), timedelta, Jobs left ``running`` by a dead worker (no heartbeat) go back to ``pending``. (+2 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "api.py"
Cohesion: 0.15
Nodes (15): error_body(), exception_handler(), page_params(), PageParams, paginated(), Any, Exception, Shared API plumbing: error envelope, exception mapping, pagination parameters. (+7 more)

### Community 5 - "metrics.py"
Cohesion: 0.09
Nodes (33): Distributed job locks on Redis (prevents overlapping scheduled runs of the same…, counters(), _counters_key(), incr(), _index_key(), observe(), percentile(), ping() (+25 more)

### Community 6 - "django_apps"
Cohesion: 0.07
Nodes (19): AppConfig, AccountsConfig, AppConfig, AlertsConfig, AppConfig, AnalyticsConfig, AppConfig, CoreConfig (+11 more)

### Community 7 - "client.py"
Cohesion: 0.09
Nodes (33): _cached_db(), _connect(), database_name(), drop_database(), ensure_database(), get_client(), StandardDatabase, ArangoDB connection management. One :class:`ArangoClient` per process (it owns… (+25 more)

### Community 8 - "services.py"
Cohesion: 0.20
Nodes (17): apps_core, Instrumented AQL execution. All repositories execute AQL through…, Stream-transaction helpers. :func:`run_in_transaction` executes a unit of work…, Request middleware: correlation IDs and request timing/outcome logging +…, Resilience primitives: jittered exponential backoff and a shared circuit…, Resilient HTTP client for upstream sources (the only module family allowed to…, Ingestion application services: feed sync, checkpointed backfill, detail…, arango_exceptions (+9 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - "CorrelationIdMiddleware"
Cohesion: 0.24
Nodes (8): CorrelationIdMiddleware, new_correlation_id(), HttpRequest, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs., Log endpoint/duration/outcome for every request and feed API latency metrics., RequestTimingMiddleware, 4. Cross-cutting concerns, HttpResponse

### Community 11 - "Frontend Accessibility Patterns"
Cohesion: 0.09
Nodes (22): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Checklist, Complete Accessible Form (+14 more)

### Community 12 - "env.py"
Cohesion: 0.06
Nodes (41): ast, PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, Celery application. Beat schedule is defined in apps.ingestion.schedule., Environment (+33 more)

### Community 13 - "sync"
Cohesion: 0.05
Nodes (44): Any, T, Narrow python-arango's ``Result[T]`` union for APIs that never return None. We…, Like :func:`sync` for APIs where None is a legitimate answer (e.g.…, sync(), sync_optional(), applied_version(), apply_schema() (+36 more)

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

### Community 20 - "health.py"
Cohesion: 0.24
Nodes (11): ping(), Readiness probe: can we reach the server and our database?, live(), HttpRequest, Liveness / readiness probes (ESD §15). ``/health/live`` — the process is up (no…, ready(), django_views_decorators_cache, django_views_decorators_http (+3 more)

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
Nodes (8): Client, django_test, StandardDatabase, test_inbound_request_id_propagates(), test_live_is_always_ok(), test_malformed_request_id_replaced(), test_ready_checks_dependencies(), test_ready_reports_schema_drift()

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

### Community 40 - "ADR-010: Timestamp representation and source/derived separation"
Cohesion: 0.40
Nodes (4): ADR-010: Timestamp representation and source/derived separation, Consequences, Context, Decision

### Community 41 - "ARCHITECTURE.md"
Cohesion: 0.22
Nodes (4): Dependencies and why each exists, Development / test, Frontend (vendored under `static/vendor`, no build step, no CDN at runtime), Runtime (Python)

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

### Community 46 - "urls.py"
Cohesion: 0.50
Nodes (3): apps_operations, django_contrib, django_urls

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

### Community 52 - "CircuitBreaker"
Cohesion: 0.07
Nodes (27): backoff_delay(), CircuitBreaker, Full-jitter exponential backoff for retry ``attempt`` (1-based). An upstream…, Response, ResilientHttpClient, _retry_after(), BaseTransport, NoReturn (+19 more)

### Community 53 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 54 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

### Community 69 - "IngestionPipeline"
Cohesion: 0.12
Nodes (31): NormalizedRecord, EventChange, IngestionPipeline, unit(), Database, Exception, Return the number of side effects produced (e.g. alert matches)., Outcome (+23 more)

### Community 70 - "test_geo.py"
Cohesion: 0.09
Nodes (17): BoundingBox, haversine_km(), InvalidGeometry, Geodesic helpers (pure). Distances use the haversine formula on a spherical…, Viewport box. ``west > east`` means the box crosses the antimeridian., Parse ``south,west,north,east`` (Leaflet ``toBBoxString`` order is w,s,e,n —…, GeoJSON polygon rings (lon, lat), split at the antimeridian when needed., Approximate fraction of the globe covered (for choosing clustering granularity). (+9 more)

### Community 71 - "tasks.py"
Cohesion: 0.11
Nodes (27): get_db(), Handle to the configured application database (``<db>_test`` under tests)., job_lock(), Yield True if the lock was acquired; the body should skip work when False., build_usgs_client(), usgs_breaker(), Any, Command (+19 more)

### Community 72 - "revision_policy.py"
Cohesion: 0.14
Nodes (22): apps_ingestion, diff(), field_changed(), FieldChange, FieldRule, _numeric_changed(), Any, Versioned meaningful-revision policy (ESD §8) (pure). A *revision* is recorded… (+14 more)

### Community 73 - "test_ingestion_services.py"
Cohesion: 0.20
Nodes (12): UpstreamError that also carries the provenance of the failed call., UpstreamRequestFailed, EnrichmentService, FeedSyncService, Lazy detail-feed enrichment (ESD §4.3). Failure never affects the base event…, Scheduled synchronisation of a USGS summary feed (FR-01)., StandardDatabase, Feed sync, backfill and enrichment services on real ArangoDB with a simulated… (+4 more)

### Community 74 - "RunRepository"
Cohesion: 0.22
Nodes (13): ingestion_runs + backfill_jobs bookkeeping (outside the per-record…, RunRepository, BackfillRequest, BackfillService, Bounded, checkpointed historical import through the FDSN catalog API (FR-02,…, FakeCatalog, Any, MonkeyPatch (+5 more)

### Community 75 - "test_tasks_and_commands.py"
Cohesion: 0.17
Nodes (13): django_core_management, Handler, httpx, io, fake_usgs(), fixture, MonkeyPatch, StandardDatabase (+5 more)

### Community 76 - "normalize_feature"
Cohesion: 0.13
Nodes (15): _csv(), normalize_feature(), reject(), payload_hash(), Any, Stable SHA-256 of a JSON payload (sorted keys, compact separators)., RecordRejected, _summarize() (+7 more)

### Community 77 - "usgs_models.py"
Cohesion: 0.19
Nodes (17): _Lenient, BaseModel, Strict contract for USGS GeoJSON payloads (summary feed, catalog query, detail…, Top level only; features are validated one by one so a bad record never sinks a…, UsgsCatalogCount, UsgsDetailFeature, UsgsDetailProperties, UsgsFeature (+9 more)

### Community 78 - "CanonicalEventInput"
Cohesion: 0.13
Nodes (9): CanonicalEventInput, is_important(), Any, BaseModel, datetime, Events that get eager detail enrichment (ESD §4.3 "important events")., JSON-safe source state (persisted on the event and in revision snapshots)., field_validator (+1 more)

### Community 79 - "UsgsClient"
Cohesion: 0.13
Nodes (12): UsgsClient, EventObserver, StandardDatabase, Participates in the ingestion transaction for inserted/revised events., StandardDatabase, Mode, Protocol, breaker() (+4 more)

### Community 80 - "errors.py"
Cohesion: 0.22
Nodes (11): CircuitOpen, Conflict, DatabaseUnavailable, NotFound, PermissionDenied, Any, Exception, QuakeWatchError (+3 more)

### Community 81 - "pipeline.py"
Cohesion: 0.23
Nodes (12): DerivedRegion, Derive an application region from a USGS ``place`` string (pure,…, region_from_place(), slugify(), _event_doc(), _pick_primary(), Any, Ingestion pipeline (ESD §7): identify → diff → transactional upsert →… (+4 more)

### Community 82 - "typing"
Cohesion: 0.21
Nodes (9): Earthquake domain model (pure). :class:`CanonicalEventInput` is the source-…, _date(), CommandParser, datetime, USGS GeoJSON → :class:`CanonicalEventInput` (pure). A feed is parsed in two…, django_core_management_base, json, pydantic (+1 more)

### Community 83 - "._process_window"
Cohesion: 0.25
Nodes (7): IngestionStats, _correlation_id(), _error_dict(), Any, datetime, RunResult, RunStatus

### Community 84 - "test_usgs_contract.py"
Cohesion: 0.21
Nodes (8): copy, load_fixture(), fixture, Contract tests against *recorded* real USGS payloads (tests/fixtures/usgs). If…, sample_feature(), summary_feed(), TestCatalogAndDetail, timedelta

### Community 85 - "repository.py"
Cohesion: 0.20
Nodes (8): apps_core_arango, ArangoDB persistence infrastructure. ``Database`` (any handle, including stream…, network_name(), Reference names for common ANSS / USGS contributing network codes (pure). Only…, Write-path persistence for ingestion: events, revisions, raw payloads, graph,…, arango_database, hashlib, Real-ArangoDB tests for schema reconciliation, validation rules and…

### Community 86 - "SourceSchemaError"
Cohesion: 0.24
Nodes (6): Upstream payload does not match the expected contract., SourceSchemaError, ValidationFailed, FetchResult, _fdsn_time(), datetime

### Community 87 - "parse_feed"
Cohesion: 0.24
Nodes (8): parse_feed(), ParsedFeed, parametrize, TestMalformedRecords, Opt-in live contract tests: the real adapter against the real USGS API. Run…, test_live_catalog_count_and_query_contract(), test_live_detail_contract(), test_live_summary_feed_contract()

### Community 88 - "AppSettings"
Cohesion: 0.29
Nodes (4): BaseSettings, AppSettings, Tests always run against an isolated ``<db>_test`` database., TestSettingsValidation

### Community 89 - "QuakeWatch Architecture"
Cohesion: 0.20
Nodes (9): event_key(), Deterministic ArangoDB ``_key`` for the first-seen identity of a source event., 1. High-level design, 2. Module map and layering, 3. Data model (ArangoDB), 5. Transactions and concurrency, 6. Ingestion (L2), QuakeWatch Architecture (+1 more)

### Community 90 - "BackfillInterrupted"
Cohesion: 0.31
Nodes (6): Command, Any, BaseCommand, BackfillInterrupted, Exception, A window failed transiently; the job is checkpointed and should be retried…

### Community 91 - "ADR-003: Canonical event + immutable revisions, with identity claims"
Cohesion: 0.22
Nodes (8): ADR-003: Canonical event + immutable revisions, with identity claims, Atomicity and failure isolation, Canonical record, Consequences, Context, Decision, Identity claims (`event_identities`), Review history

### Community 92 - "run_in_transaction"
Cohesion: 0.29
Nodes (8): _abort_quietly(), _is_retryable(), StandardDatabase, T, Run ``work`` atomically; retry on write-write conflicts.…, run_in_transaction(), BaseException, TransactionDatabase

### Community 93 - "usgs.py"
Cohesion: 0.32
Nodes (6): Any, SourceRequest, CatalogCount, DetailResult, USGS Earthquake Hazards Program adapter (summary feeds, FDSN catalog, detail…, re

### Community 94 - "context_processors.py"
Cohesion: 0.33
Nodes (5): Any, HttpRequest, site(), django_conf, django_http

### Community 95 - ".__call__"
Cohesion: 0.50
Nodes (3): datetime, Request, Response

### Community 96 - "Command"
Cohesion: 0.50
Nodes (3): Command, BaseCommand, CommandParser

## Knowledge Gaps
- **316 isolated node(s):** `Why QuakeWatch?`, `Operator commands`, `Tests`, `Implementation Status`, `U.S. Geological Survey (USGS)` (+311 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 564 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuakeWatch Architecture` connect `QuakeWatch Architecture` to `ARCHITECTURE.md`, `CorrelationIdMiddleware`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Why does `run_in_transaction()` connect `run_in_transaction` to `StandardDatabase`, `IngestionPipeline`, `services.py`, `errors.py`, `pipeline.py`, `._process_window`, `repository.py`, `QuakeWatch Architecture`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `5. Transactions and concurrency` connect `QuakeWatch Architecture` to `run_in_transaction`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `CircuitBreaker` (e.g. with `ResilientHttpClient` and `breaker()`) actually correct?**
  _`CircuitBreaker` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `IngestionPipeline` (e.g. with `NormalizedRecord` and `RecordRejected`) actually correct?**
  _`IngestionPipeline` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RunRepository` (e.g. with `BackfillService` and `EnrichmentService`) actually correct?**
  _`RunRepository` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `BackfillService` (e.g. with `Command` and `SourceRequest`) actually correct?**
  _`BackfillService` has 12 INFERRED edges - model-reasoned connections that need verification._