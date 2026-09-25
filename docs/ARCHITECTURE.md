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

Runtime processes (one image): **web** (gunicorn), **worker** (Celery), **beat** (Celery beat).
Stores: **ArangoDB** (all domain data), **SQLite** (Django auth/sessions only — ADR-009),
**Redis** (Celery broker, cache, throttling, metrics, circuit-breaker state).

## 2. Module map and layering

| Module | Responsibility | Layers present |
|---|---|---|
| `apps/core` | Shared kernel: Arango client/schema/migrations/transactions, query runner, clock, errors, middleware, metrics, API error envelope + pagination | infra |
| `apps/geo` | Geodesic distance, bbox/radius validation, region normalisation | pure |
| `apps/earthquakes` | Event read models, filters, EventRepository, query services, API + pages | domain, repo, service, API |
| `apps/ingestion` | USGS adapters, normaliser, revision policy/differ, pipeline, backfill, dead letters, Celery tasks | adapters, pure, repo, service, tasks |
| `apps/alerts` | Rule model + matcher (pure), repositories, CRUD API, evaluation | pure, repo, service, API |
| `apps/analytics` | Aggregations (AQL) + API | repo, API |
| `apps/research` | Snapshots pinned to revisions, manifests, checksums, exports | pure, repo, service, API |
| `apps/operations` | Health/readiness, freshness, ingestion dashboard, audit log, admin actions | repo, service, API |
| `apps/accounts` | Django auth (ORM/SQLite), signup/login | Django |

Dependency direction: `API/views → services → repositories/adapters → core`; pure modules
(`domain`, `normalizer`, `revision_policy`, `differ`, `matcher`, `manifest`, `geo`) depend on nothing
framework- or I/O-related. Enforced by `tests/architecture/test_boundaries.py`.

## 3. Data model (ArangoDB)

Declared in `apps/core/arango/schema.py` (schema version 2; versioned data migrations in
`apps/core/arango/migrate.py`).

| Collection | Kind | Key | Purpose | Indexes (`qw_*`) |
|---|---|---|---|---|
| `events` | doc | `usgs_<first-seen id>` | canonical current event | unique(source, source_event_id, merged_into), geo(coordinates, GeoJSON), occurred_at, magnitude |
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
- **Metrics:** Redis-backed counters and latency series (`apps/core/metrics.py`), p50/p95/p99 on the
  Operations page; every AQL query is named and timed (`run_query`).
- **Errors:** `apps/core/errors.py` hierarchy → one JSON error envelope
  `{"error": {code, message, details, correlation_id}}` (`apps/core/api.py`).
- **Security:** Django auth/CSRF, secure cookies + HSTS in production, native CSP with nonces,
  DRF throttles (`anon`, `user`, `expensive`, `export`, `admin_action`), bind-var-only AQL.
- **Health:** `/health/live`, `/health/ready` (ArangoDB + schema version + Redis).

## 5. Transactions and concurrency
`run_in_transaction` opens a stream transaction on declared collections, commits on success,
aborts on any exception, and retries the whole unit on write-write conflicts (error 1200) with
jittered exponential backoff. Verified by `tests/integration/test_arango_foundation.py`
(concurrent increments lose no update).

## 6. Ingestion (L2)

```text
beat ─► sync_feed (lock) ─► UsgsClient.summary_feed ─► parse_feed ─► IngestionPipeline.ingest
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
| Admin actions (FR-14) | `operations/sync`, `operations/backfill` (GET, POST), `operations/dead-letters/{key}/retry` | Celery tasks, `backfill_jobs`, `dead_letters` | — |
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
