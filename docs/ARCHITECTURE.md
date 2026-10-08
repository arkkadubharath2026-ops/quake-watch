# QuakeWatch Architecture

Living document. Source requirements: [PRD](PRD.md), [ESD](ESD.md). Decisions: [adr/](adr/).

## 1. High-level design

```text
USGS Summary / Catalog / Detail APIs
        │  httpx (timeouts, retries+jitter, circuit breaker)      apps/ingestion/adapters
        ▼
Validate (pydantic) → Normalize → Hash                            apps/ingestion/normalizer
        ▼
Pipeline: identify → load current → diff (versioned policy)       apps/ingestion/pipeline
        → stream transaction { canonical upsert + revision append
                               + raw payload + graph edges }
        → alert evaluation (idempotent matches) → run metrics
        ▼
ArangoDB  documents + edges + geo index + ArangoSearch view       apps/core/arango
        ▼
Repositories (AQL, bind vars) → Services → DRF API / Django pages
        ▼
Bootstrap 5 + Leaflet (markercluster) + Chart.js (vendored, CSP nonce)
```

Runtime processes (one image): **web** (gunicorn), **worker** (`manage.py run_worker`),
**scheduler** (`manage.py run_scheduler`).
Store: **ArangoDB only** (ADR-014, ADR-015) — domain data; accounts (`auth_users`) and sessions
(`sessions`); the durable job queue (`jobs`, `job_schedules`); job leases (`job_leases`); the Django
cache (`cache_entries`: throttles, login counters, page caches); metrics (`metric_counters`,
`metric_series`); circuit-breaker state (`circuit_breakers`). There is no relational database
(`DATABASES = {}`), no Redis and no Celery.

## 2. Module map and layering

| Module | Responsibility | Layers present |
|---|---|---|
| `apps/core` | Shared kernel: Arango client/schema/migrations/transactions, query runner, clock, errors, middleware, metrics, API error envelope + pagination | infra |
| `apps/geo` | Geodesic distance, bbox/radius validation, region normalisation | pure |
| `apps/earthquakes` | Event read models, filters, EventRepository, query services, API + pages | domain, repo, service, API |
| `apps/ingestion` | USGS adapters, normaliser, revision policy/differ, pipeline, backfill, dead letters, job tasks | adapters, pure, repo, service, tasks |
| `apps/jobs` | Durable job queue: task registry (`@task`, `.delay`), atomic claim/heartbeat/reap repository, worker (fork per job), scheduler, `jobs` command | pure, repo, service |
| `apps/alerts` | Rule model + matcher (pure), repositories, CRUD API, evaluation | pure, repo, service, API |
| `apps/analytics` | Aggregations (AQL) + API | repo, API |
| `apps/research` | Snapshots pinned to revisions, manifests, checksums, exports | pure, repo, service, API |
| `apps/operations` | Health/readiness, freshness, ingestion dashboard, audit log, admin actions | repo, service, API |
| `apps/accounts` | Accounts and sessions in ArangoDB (`ArangoUser`, session engine, throttled backend), signup/login, user admin commands, SQLite migration | repo, Django |

Dependency direction: `API/views → services → repositories/adapters → core`; pure modules
(`domain`, `normalizer`, `revision_policy`, `differ`, `matcher`, `manifest`, `geo`) depend on nothing
framework- or I/O-related. Enforced by `tests/architecture/test_boundaries.py`.

## 3. Data model (ArangoDB)

Declared in `apps/core/arango/schema.py` (schema version 2; versioned data migrations in
`apps/core/arango/migrate.py`).

| Collection | Kind | Key | Purpose | Indexes (`qw_*`) |
|---|---|---|---|---|
| `events` | doc | `usgs_<first-seen id>` | canonical current event | unique(source, source_event_id, merged_into), geo(coordinates, GeoJSON), (occurred_at, _key) storing merged_into+magnitude, (magnitude, _key) storing merged_into — ADR-012 |
| `event_identities` | doc | `usgs_<id>` | identity claims: every associated id → live event (ADR-003) | event_key |
| `event_revisions` | doc | `<event_key>_<n>` | immutable meaningful changes | unique(event_key, revision_number), observed_at |
| `raw_payloads` | doc | sha256 | content-addressed raw source payloads | TTL(expires_at) |
| `regions` | doc | slug | derived geographic entities | — |
| `networks` | doc | network code | source networks | — |
| `users` | doc | Django user id | graph vertex mirror (no credentials) | — |
| `alert_rules` | doc | uuid | user rules | user_id, enabled |
| `alert_matches` | doc | hash(rule, event) | immutable match history + explanation | unique(rule_key, event_key), (user_id, matched_at) |
| `saved_searches` | doc | uuid | saved explorer filters | (user_id, created_at) |
| `research_snapshots` | doc | uuid | reproducible dataset definitions | (user_id, created_at) |
| `ingestion_runs` | doc | uuid | every sync/backfill/enrichment run | started_at, status, (kind, started_at) |
| `backfill_jobs` | doc | uuid | checkpointed backfill progress | status |
| `dead_letters` | doc | hash(source, record) | rejected/failing records | last_failure_at, (source, source_event_id) |
| `audit_log` | doc | uuid | privileged actions (FR-15) | at |
| `schema_meta` | doc | `current` | applied schema version | — |
| `event_in_region` | edge | — | events → regions | edge index |
| `event_reported_by_network` | edge | — | events → networks | edge index |
| `user_owns_rule` | edge | — | users → alert_rules | edge index |
| `rule_matched_event` | edge | — | alert_rules → events | edge index |

Named graph `quakewatch_graph` holds the four edge definitions. ArangoSearch view `events_search`
indexes `place` and `derived.region_name` with `text_en` for location-text search.

DB-level integrity: JSON-schema rules (level `strict`) on `events`, `event_revisions`, `alert_rules`
enforce types, ranges, enums and the timestamp format.

### Relational rubric mapping (ESD §19)

| Rubric term | QuakeWatch / ArangoDB equivalent |
|---|---|
| Primary key | `_key` (deterministic) + unique persistent index on `(source, source_event_id)` |
| Foreign key | edge `_from`/`_to` and `event_key`/`user_id` references, checked in services |
| Constraints | collection JSON-schema rules + unique indexes |
| 3NF | canonical event vs. immutable revisions vs. raw payloads vs. derived region/network entities |
| Views | ArangoSearch view `events_search` |
| Triggers/procedures | none claimed — equivalent logic lives in the ingestion pipeline service |
| Transactions | stream transactions: canonical update + revision append + edges (`run_in_transaction`) |

## 4. Cross-cutting concerns

- **Configuration:** `config/env.py` (`AppSettings`, pydantic-settings, `QW_*` env vars, production guards).
- **Logging:** structlog JSON/console; `correlation_id` bound per request by `CorrelationIdMiddleware`
  (accepts a well-formed inbound `X-Request-ID`), per job by task wrappers.
- **Metrics:** counters and latency series buffered per process and flushed atomically to ArangoDB
  every 5 s / 500 samples / on read (`apps/core/metrics.py`, `arango/metrics_store.py`), p50/p95/p99 on
  the Operations page; every AQL query is named and timed (`run_query`).
- **Shared state:** Django cache on ArangoDB (`arango/cache.py`: atomic `add`/`incr`, server-time
  expiry), circuit breaker (`arango/breaker_store.py`, fails open), job leases (`arango/leases.py`,
  fail closed). All use single-statement AQL re-run on write-write conflicts (`arango/atomic.py`).
- **Errors:** `apps/core/errors.py` hierarchy → one JSON error envelope
  `{"error": {code, message, details, correlation_id}}` (`apps/core/api.py`).
- **Security:** Django auth/CSRF, secure cookies + HSTS in production, native CSP with nonces,
  DRF throttles (`anon`, `user`, `expensive`, `export`, `admin_action`), bind-var-only AQL.
- **Health:** `/health/live`, `/health/ready` (ArangoDB + schema version).

## 5. Transactions and concurrency
`run_in_transaction` opens a stream transaction on declared collections, commits on success,
aborts on any exception, and retries the whole unit on write-write conflicts (error 1200) with
jittered exponential backoff. Verified by `tests/integration/test_arango_foundation.py`
(concurrent increments lose no update).

## 6. Ingestion (L2)

```text
scheduler ─► jobs ─► worker ─► sync_feed (lease) ─► UsgsClient.summary_feed ─► parse_feed ─► IngestionPipeline.ingest
                                                            │            ├─ fast path: hash unchanged → bulk last_seen
                                                            │            └─ per record: stream txn {claims, event,
                                                            │               revision, raw payload, edges, observers}
                                                            └─ rejected → dead_letters      failures → dead_letters
      run doc (ingestion_runs): params, request manifests (url, status, attempts, sha256), counts, error
important inserted/revised events ─► enrich_event (detail feed → events.enrichment.products)
backfill job ─► windows (checkpoint after each) ─► count → split if ≥ limit → query → pipeline
recover (10 min) ─► abandon dead runs, resume stalled/idle backfills
```

Outcomes per record: `inserted`, `revised` (tracked change → revision), `refreshed` (untracked
change), `unchanged`, `stale` (older `source_updated_at`), `rejected` (contract violation),
`failed` (rolled back + dead-lettered). Representational coercions in the normaliser: epoch ms →
UTC ISO string, `tsunami` 0/1 → bool, CSV `ids`/`sources`/`types` → sorted lists, alert level
lower-cased. Nothing else is inferred; missing values stay `null`.

## 7. Query & API layer (L3)

All endpoints are under `/api/v1/`, return JSON, and share one error envelope
`{"error": {code, message, details, correlation_id}}`. Event identifiers accept the canonical key
(`usgs_<id>`) or **any** current or historical USGS id (resolved through identity claims).

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET events` | explorer search (FR-06) | filters below, `page`/`page_size` (≤ 200, offset ≤ 50k), `sort`, `direction`; returns `query.filters` (canonical) + `query.summary` |
| `GET events/map` | viewport map (FR-07) | `bbox` required; ≤ 2000 points, otherwise server-side grid clusters |
| `GET events/{id}` | detail (FR-08) | grouped `source` / `derived` (with method notes) / `operational` / `products` / `enrichment` |
| `GET events/{id}/revisions` | revision timeline + initial-vs-current + policy | |
| `GET events/{id}/provenance` | payload hashes, retained raw payload, ingestion runs + request manifests | |
| `GET events/{id}/relationships` | graph: region, network, same-region events; spatial-temporal neighbours | neighbours are proximity only, not aftershock claims |
| `POST events/{id}/enrich` | queue detail-feed enrichment | auth + CSRF, throttle `expensive` |
| `GET analytics/{summary,timeseries,distributions,breakdowns,revisions,latency}` | FR-09 | `days` 1..3660; cached 60 s |
| `GET system/health`, `system/freshness` | public status (ADR-004) | |
| `GET operations/{overview,runs,dead-letters,diagnostics}` | FR-14 | staff only; diagnostics = live EXPLAIN of every named query |

Explorer filters: `start`, `end`, `min_magnitude`, `max_magnitude`, `min_depth_km`, `max_depth_km`,
`bbox` (south,west,north,east; antimeridian-aware) **or** `lat`+`lon`+`radius_km`, `alert`
(green/yellow/orange/red/none), `tsunami`, `status`, `network`, `event_type`, `q` (ArangoSearch over
place and derived region). `EventFilter.canonical()` is deterministic and is reused by saved searches
and research snapshots.

**Named-query catalogue.** Every static AQL query is a `NamedQuery` registered next to its repository
and auto-discovered at startup. `manage.py aql_catalog --write` regenerates
[AQL_QUERIES.md](AQL_QUERIES.md) from live EXPLAIN plans; tests assert each plan uses one of its
expected indexes. Write queries are marked `read_only=False` and are only ever explained by tooling.

**Performance (2.2k real events, local Docker):** all catalogued queries 1.4–26 ms; API responses
5–140 ms (map clustering of the whole globe is the slowest). Ingestion: 8.6 ms per new record after
consolidating each record's writes into one multi-collection AQL statement (was 31 ms with 11 round
trips); unchanged-record replay ≈ 0.13 ms/record via the fast path.

## 8. User features (L4)

| Feature | Endpoints (`/api/v1/`) | Storage / graph | Decision |
|---|---|---|---|
| Alert rules (FR-10) | `alert-rules` (GET, POST), `alert-rules/{id}` (GET, PATCH, DELETE), `alert-rules/{id}/preview` | `alert_rules`, `users -user_owns_rule-> alert_rules` | ADR-005 |
| Explainable matches (FR-11) | `alerts/matches`, `alerts/matches/read`, `alerts/unread-count`, `alerts/matched-events` | `alert_matches`, `alert_rules -rule_matched_event-> events` | ADR-005 |
| Saved searches (FR-12) | `saved-searches` (GET, POST), `saved-searches/{id}` (GET, PATCH, DELETE), `saved-searches/{id}/events` | `saved_searches` (canonical `EventFilter`) | — |
| Research snapshots (FR-13) | `research/snapshots` (GET, POST), `research/snapshots/{id}` (GET, DELETE), `research/snapshots/{id}/export?format=zip\|csv\|json` | `research_snapshots` (pinned `[event_key, revision]`) | ADR-006 |
| Admin actions (FR-14) | `operations/sync`, `operations/backfill` (GET, POST), `operations/dead-letters/{key}/retry` | job queue (`jobs`), `backfill_jobs`, `dead_letters` | — |
| Audit trail (FR-15) | `operations/audit` (GET only) | `audit_log` (append-only; no update/delete code path) | — |

**Authorization.** All user-owned data is filtered by `user_id` inside the repository queries
(object-level authorization in the data layer, not only in views); another user's object answers
404, never 403, so existence is not leaked. Operations endpoints require `is_staff`; state-changing
admin actions are throttled (`admin_action`) and audited with actor, target, IP, user agent and the
request's correlation id.

**Authentication hardening.** `ThrottledModelBackend` refuses attempts once a (username, client IP)
pair reaches 10 failures in 15 minutes (30 per username across addresses); every login outcome is
audited through Django's auth signals. Session auth enforces CSRF for all unsafe API methods.

**Alert delivery.** Matches are evaluated inside the ingestion transaction by the
`AlertRuleObserver`; live-feed only, events < 24 h old, created after the rule, one match per
(rule, event), cooldown-suppressed repeats recorded with `notify: false`.

## 9. User interface (L5)

Server-rendered page shells with API-driven islands (ADR-011); design tokens, components, UI
states and the accessibility checklist are in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

| Page | URL | Access | Server-side | Islands (`static/qw/js/`) → API |
|---|---|---|---|---|
| Dashboard | `/` | public | shell | `dashboard.js` → `analytics/summary`, `analytics/timeseries`, `events`, `events/map` |
| Live Map | `/map/` | public | shell, filters | `map.js` → `events/map` (viewport bbox), `events` (side panel), `events/{id}` |
| Explorer | `/explorer/` | public (save/export: signed in) | GET filter form (works without JS) | `explorer.js` → `events`, `events/map`, `saved-searches`, `research/snapshots` |
| Event Detail | `/events/{id}/` | public | overview (404 / canonical redirect) | `event.js` → `events/{id}/revisions`, `/relationships`, `/provenance`, `/enrich` |
| Analytics | `/analytics/` | public | shell | `analytics.js` → `analytics/*` |
| Alerts | `/alerts/` | signed in | shell | `alerts.js` → `alert-rules*`, `alerts/matches*` |
| Research Lab | `/research/` | signed in | shell | `research.js` → `research/snapshots*` |
| System Status | `/status/` | public | thresholds from settings | `status.js` → `system/freshness`, `system/health` |
| Operations | `/operations/` | staff (403 otherwise) | shell | `operations.js` → `operations/*` |
| About | `/about/` | public | static methodology text | — |
| Accounts | `/accounts/login/`, `signup/`, `logout/` (POST) | public | Django auth forms; lockout message from `accounts.security` | — |

Every page carries the freshness badge (polls `system/freshness`), the USGS attribution and the
"no prediction / not an emergency warning" statement. `apps/web/views.py` holds no business logic;
Event Detail calls `EventQueryService` directly (same service as the API).

**Security.** Strict CSP (only the theme bootstrap is inline, with a nonce); the runtime inserts
API data with `textContent` only; upstream URLs are rendered as links only when they are
`https://*.usgs.gov` (`earthquakes.services.safe_usgs_url`); logout is POST-only; the login page
explains a lockout without revealing whether the account exists.

## 10. Hardening (L6)

**Performance.** `manage.py arango_benchmark` seeds a disposable `*_bench_test` database with a
synthetic, schema-valid catalogue shaped like the USGS feed (`apps/core/arango/benchmark.py`). It
then times the production AQL for five workloads with and without the read indexes, at 500, 10k
and 100k records. The first run exposed a list-query regression at 100k (p95 611 ms). It was fixed
with covering sort indexes and a count subquery in place of `fullCount` (ADR-012, now p95 37 ms).
Results and tuning history: [BENCHMARKS.md](BENCHMARKS.md).

**Browser tests.** `tests/e2e` (Playwright + pytest-django live server) drives the real app
against the real ArangoDB test database, seeded from the recorded feed. It covers:
- the dashboard, Explorer filters/sort/paging/history, Event Detail tabs, a real 404;
- alert rule CRUD with validation, research snapshot + manifest + CSV export, saved searches;
- accounts, staff-only operations;
- the server, network and throttling states with retry.

Map tiles are the only thing stubbed. Any console error or CSP violation fails a test. Accounts
and sessions live in the ArangoDB test database like everything else (ADR-015).

**Accessibility.** The axe-core WCAG 2.2 A/AA rules run on every page in both themes and at
320 px, alongside keyboard, focus and reduced-motion tests. The findings (contrast, target size,
focusable scroll regions, stuck `aria-busy`, focus-ring contrast, reduced-motion flicker) were
fixed in shared CSS/JS (`QW.fill`, `QW.scrollRegion`). See [ACCESSIBILITY.md](ACCESSIBILITY.md).

**CI** (`.github/workflows/ci.yml`, ESD §17): lint + format + strict mypy → unit/contract/
resilience/architecture → integration with coverage ≥ 90 % → browser + accessibility suite →
`pip-audit` + `check --deploy` with production settings → container build and a smoke check that
the image runs as non-root. The only service is the same ArangoDB image as Compose.

**Operations.** [RUNBOOK.md](RUNBOOK.md) covers start/upgrade, health and freshness signals,
incident playbooks, data tasks, backup/restore and the release checklist. The rubric mapping is
in [RUBRIC.md](RUBRIC.md).
