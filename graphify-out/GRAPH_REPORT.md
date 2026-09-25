# Graph Report - Bharath DBMS project  (2026-09-25)

## Corpus Check
- 75 files · ~25,150 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 4, .example 1)

## Summary
- 754 nodes · 1026 edges · 69 communities (54 shown, 15 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e6cc538e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- QuakeWatch
- run_in_transaction
- AppSettings
- Django Security Best Practices
- api.py
- metrics.py
- django_apps
- client.py
- query.py
- Django + Celery Async Task Patterns
- middleware.py
- Frontend Accessibility Patterns
- ruff_on_edit.py
- migrate.py
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
- Command
- 13. Reliability
- 11. Competitive Positioning
- 7. Core User Journeys
- 9. Non-Functional Requirements
- ADR-001: ArangoDB as the primary database
- ADR-002: Modular Django monolith with background workers
- ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB
- ADR-010: Timestamp representation and source/derived separation
- Dependencies and why each exists
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
- pytest_collection_modifyitems
- 18. Deployment Profiles
- 3. Technology Stack
- entrypoint.sh
- quakewatch

## God Nodes (most connected - your core abstractions)
1. `QuakeWatch — Engineering System Design (ESD)` - 23 edges
2. `QuakeWatch` - 19 edges
3. `sync()` - 16 edges
4. `AppSettings` - 16 edges
5. `QuakeWatch — Product Requirements Document (PRD)` - 16 edges
6. `apply_schema()` - 14 edges
7. `Django Security Best Practices` - 14 edges
8. `run_in_transaction()` - 13 edges
9. `Django + Celery Async Task Patterns` - 13 edges
10. `ensure_database()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `4. Cross-cutting concerns` --references--> `run_query()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/query.py
- `5. Transactions and concurrency` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `Relational rubric mapping (ESD §19)` --references--> `run_in_transaction()`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/arango/transactions.py
- `4. Cross-cutting concerns` --references--> `AppSettings`  [INFERRED]
  docs/ARCHITECTURE.md → config/env.py
- `4. Cross-cutting concerns` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/ARCHITECTURE.md → apps/core/middleware.py

## Import Cycles
- None detected.

## Communities (69 total, 15 thin omitted)

### Community 0 - "QuakeWatch"
Cohesion: 0.04
Nodes (45): 1. Earthquake Record Revision Dynamics, 2. Multi-Source Consistency, 3. Revision-Likelihood Modeling, 4. Spatiotemporal Sequence Analysis, Academic Requirements Covered, Alerts / Watch Rules, Analytics, Competitor / Reference Systems (+37 more)

### Community 1 - "run_in_transaction"
Cohesion: 0.07
Nodes (22): _abort_quietly(), _is_conflict(), StandardDatabase, T, run_in_transaction(), BaseException, 1. High-level design, 2. Module map and layering (+14 more)

### Community 2 - "AppSettings"
Cohesion: 0.10
Nodes (17): from_epoch_ms(), from_iso(), now_iso(), Time utilities. Timestamps are persisted as fixed-width ISO-8601 UTC strings…, to_iso(), utc_now(), percentile(), Nearest-rank percentile on an ascending list. (+9 more)

### Community 3 - "Django Security Best Practices"
Cohesion: 0.06
Nodes (33): API Security, Authentication, Authentication for APIs, Authorization, Content Security Policy, Core Security Settings, CSRF Protection, Custom Permissions (+25 more)

### Community 4 - "api.py"
Cohesion: 0.09
Nodes (28): error_body(), exception_handler(), page_params(), PageParams, paginated(), Any, Exception, Shared API plumbing: error envelope, exception mapping, pagination parameters. (+20 more)

### Community 5 - "metrics.py"
Cohesion: 0.11
Nodes (30): _client(), counters(), incr(), _namespace(), observe(), ping(), Exception, Lightweight operational metrics stored in Redis. Counters are Redis hash… (+22 more)

### Community 6 - "django_apps"
Cohesion: 0.07
Nodes (19): AccountsConfig, AppConfig, AlertsConfig, AppConfig, AnalyticsConfig, AppConfig, CoreConfig, AppConfig (+11 more)

### Community 7 - "client.py"
Cohesion: 0.13
Nodes (24): _cached_db(), _connect(), database_name(), drop_database(), ensure_database(), get_client(), get_db(), StandardDatabase (+16 more)

### Community 8 - "query.py"
Cohesion: 0.12
Nodes (23): apps_core_arango, explain(), indexes_used(), Any, QueryResult, Instrumented AQL execution. All repositories execute AQL through…, Return the optimizer's chosen plan (used by benchmarks and the ops diagnostics…, run_query() (+15 more)

### Community 9 - "Django + Celery Async Task Patterns"
Cohesion: 0.07
Nodes (26): Anti-Patterns, Basic Task, Beat Scheduling (Periodic Tasks), Calling Tasks, Canvas: Chaining and Grouping Tasks, `celery.py` — App Entrypoint, Code-Defined Schedule, Database-Defined Schedule (via django-celery-beat) (+18 more)

### Community 10 - "middleware.py"
Cohesion: 0.11
Nodes (17): Any, HttpRequest, site(), CorrelationIdMiddleware, new_correlation_id(), HttpRequest, Request middleware: correlation IDs and request timing/outcome logging +…, Accept a well-formed inbound X-Request-ID or mint one; bind it to all logs. (+9 more)

### Community 11 - "Frontend Accessibility Patterns"
Cohesion: 0.09
Nodes (22): Anti-Patterns, ARIA Attributes, aria-describedby, aria-expanded and aria-controls, aria-label vs aria-labelledby, aria-live for Dynamic Content, Checklist, Complete Accessible Form (+14 more)

### Community 12 - "ruff_on_edit.py"
Cohesion: 0.10
Nodes (13): PreToolUse hook: block Claude from writing real secret files (.env, *.pem,…, find_ruff(), main(), Path, PostToolUse hook: format + lint-fix a Python file right after Claude edits it.…, Celery application. Beat schedule is defined in apps.ingestion.schedule., django_core_asgi, django_core_wsgi (+5 more)

### Community 13 - "migrate.py"
Cohesion: 0.20
Nodes (16): Any, T, Narrow python-arango's ``Result[T]`` union: we only use synchronous execution., sync(), applied_version(), apply_schema(), MigrationReport, _normalize_declared() (+8 more)

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
Nodes (12): apps_core, ping(), Readiness probe: can we reach the server and our database?, live(), HttpRequest, Liveness / readiness probes (ESD §15). ``/health/live`` — the process is up (no…, ready(), django_views_decorators_cache (+4 more)

### Community 21 - "QuakeWatch — Engineering System Design (ESD)"
Cohesion: 0.15
Nodes (13): 11. Alert Engine, 12. Research Data Layer, 14. Security, 17. CI/CD, 19. Academic Rubric Mapping, 1. Engineering Strategy, 21. Architecture Decision Records, 22. External References (+5 more)

### Community 22 - "Document Collections"
Cohesion: 0.15
Nodes (13): 5. ArangoDB Data Model, `alert_matches`, `alert_rules`, `dead_letters`, Document Collections, Edge Collections, `event_revisions`, `events` (+5 more)

### Community 23 - "schema.py"
Cohesion: 0.25
Nodes (9): collection_spec(), CollectionSpec, IndexSpec, _nullable(), _p(), Any, Declarative ArangoDB schema for QuakeWatch (ESD §5, §6). This module is the…, _ts() (+1 more)

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

### Community 32 - "Command"
Cohesion: 0.33
Nodes (4): Command, Any, BaseCommand, CommandParser

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

### Community 41 - "Dependencies and why each exists"
Cohesion: 0.40
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

### Community 52 - "pytest_collection_modifyitems"
Cohesion: 0.67
Nodes (3): Config, Item, pytest_collection_modifyitems()

### Community 53 - "18. Deployment Profiles"
Cohesion: 0.67
Nodes (3): 18. Deployment Profiles, Local / College Demo, Small Cloud Demo

### Community 54 - "3. Technology Stack"
Cohesion: 0.67
Nodes (3): 3. Technology Stack, Core, Recommended Supporting Components

## Knowledge Gaps
- **306 isolated node(s):** `entrypoint.sh script`, `quakewatch`, `Prompt Defense Baseline`, `Your Role`, `Step 1: Contextual Discovery` (+301 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 441 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuakeWatch Architecture` connect `run_in_transaction` to `middleware.py`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Why does `4. Cross-cutting concerns` connect `middleware.py` to `query.py`, `run_in_transaction`, `AppSettings`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Why does `QuakeWatch — Engineering System Design (ESD)` connect `QuakeWatch — Engineering System Design (ESD)` to `run_in_transaction`, `13. Reliability`, `6. Constraints and Indexes`, `15. Observability`, `20. Research Extensions`, `4. Source Integration`, `18. Deployment Profiles`, `3. Technology Stack`, `Document Collections`, `10. Frontend Design`, `16. Testing Strategy`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `AppSettings` (e.g. with `4. Cross-cutting concerns` and `TestSettingsValidation`) actually correct?**
  _`AppSettings` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `entrypoint.sh script`, `quakewatch`, `Prompt Defense Baseline` to the rest of the system?**
  _306 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `QuakeWatch` be split into smaller, more focused modules?**
  _Cohesion score 0.043478260869565216 - nodes in this community are weakly interconnected._
- **Should `run_in_transaction` be split into smaller, more focused modules?**
  _Cohesion score 0.07207207207207207 - nodes in this community are weakly interconnected._