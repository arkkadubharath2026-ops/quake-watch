# QuakeWatch — Engineering System Design (ESD)

**Version:** 1.0  
**Architecture style:** Modular Django monolith + asynchronous ingestion workers + ArangoDB  
**Primary goal:** Industry-grade engineering without unnecessary distributed-system complexity

## 1. Engineering Strategy

QuakeWatch should begin as a **modular monolith**, not premature microservices.

For this project, the hardest engineering problems are:
- data correctness,
- source revision handling,
- provenance,
- reproducibility,
- geospatial query performance,
- ingestion reliability,
- observability.

A well-structured Django application with domain modules and background jobs is simpler to deploy, easier to test, and still production-grade.

## 2. High-Level Architecture

```text
                    ┌──────────────────────────────┐
                    │          USGS APIs           │
                    │ Summary | Catalog | Detail   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      Source Adapter Layer    │
                    │ fetch / validate / normalize │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       Ingestion Pipeline     │
                    │ dedupe / diff / provenance  │
                    └──────────┬─────────┬─────────┘
                               │         │
                     canonical │         │ revisions
                               ▼         ▼
                  ┌───────────────────────────────┐
                  │           ArangoDB            │
                  │ Documents + Edges + Geo Index │
                  └──────────────┬────────────────┘
                                 │
                     ┌───────────┼────────────┐
                     ▼           ▼            ▼
                 Django API   Rule Engine   Research Export
                     │           │            │
                     └───────────┼────────────┘
                                 ▼
                     HTML/CSS/JS/Bootstrap
                     Leaflet + Chart.js
```

## 3. Technology Stack

### Core
- **Database:** ArangoDB Community Edition
- **Backend:** Python 3.12+ + Django
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5
- **Mapping:** Leaflet.js
- **Charts:** Chart.js
- **Repository:** GitHub

### Recommended Supporting Components
- **Background jobs:** Celery
- **Broker/cache:** Redis
- **HTTP client:** httpx or requests
- **Testing:** pytest + pytest-django
- **Containers:** Docker + Docker Compose
- **CI:** GitHub Actions
- **API layer:** Django REST Framework if API endpoints are exposed
- **Observability:** structured logging; Prometheus/Grafana optional

Redis remains a support component only. ArangoDB is the primary database.

## 4. Source Integration

### 4.1 USGS Summary Feed Adapter

Used for frequent synchronization of recent earthquakes.

Normalize to an internal source-neutral structure:

```python
CanonicalEventInput(
    source="USGS",
    source_event_id="...",
    magnitude=...,
    magnitude_type=...,
    place=...,
    occurred_at=...,
    source_updated_at=...,
    longitude=...,
    latitude=...,
    depth_km=...,
    felt=...,
    cdi=...,
    mmi=...,
    alert=...,
    status=...,
    tsunami=...,
    significance=...,
    network=...,
    detail_url=...,
)
```

### 4.2 Catalog API Adapter

Used for:
- historical bootstrap,
- bounded backfill,
- reproducible research queries.

Rules:
- query bounded date windows,
- checkpoint progress,
- persist request parameters,
- retry transient failures,
- avoid one giant historical request.

### 4.3 Detail Feed Adapter

Used for lazy enrichment:
- detailed event products,
- contributor metadata,
- scientific product references.

Fetch on demand for:
- important events,
- event-detail page,
- research jobs requiring detail.

## 5. ArangoDB Data Model

### Document Collections

#### `events`
Latest canonical representation of each event.

Example:

```json
{
  "_key": "usgs_us7000xxxx",
  "source": "USGS",
  "source_event_id": "us7000xxxx",
  "magnitude": 6.1,
  "magnitude_type": "mww",
  "place": "Example region",
  "occurred_at": "2026-09-21T00:00:00Z",
  "source_updated_at": "2026-09-21T00:04:00Z",
  "latitude": 0.0,
  "longitude": 0.0,
  "depth_km": 10.2,
  "coordinates": [0.0, 0.0],
  "felt": null,
  "cdi": null,
  "mmi": null,
  "alert": "green",
  "status": "reviewed",
  "tsunami": false,
  "significance": 0,
  "network": "us",
  "detail_url": "...",
  "first_seen_at": "2026-09-21T00:01:00Z",
  "last_seen_at": "2026-09-21T00:05:00Z",
  "last_ingested_at": "2026-09-21T00:05:00Z",
  "schema_version": 1
}
```

#### `event_revisions`
Immutable meaningful source changes.

Fields:
- event key,
- revision number,
- observed at,
- source updated at,
- changed fields,
- before values,
- after values,
- source payload hash.

#### `regions`
Application-normalized geographic entities.

#### `networks`
Seismic/source networks.

#### `alert_rules`
User-owned CRUD entity.

#### `alert_matches`
Immutable rule-match history.

#### `saved_searches`
Saved explorer filters.

#### `research_snapshots`
Reproducible dataset definitions.

#### `ingestion_runs`
Operational metadata for every sync/import job.

#### `dead_letters`
Rejected or repeatedly failing source records.

### Edge Collections

- `event_in_region`
- `event_reported_by_network`
- `user_owns_rule`
- `rule_matched_event`

Only create edges that support a real query or product feature.

## 6. Constraints and Indexes

### `events`
- unique index: `(source, source_event_id)`
- geo index: `coordinates`
- persistent index: `occurred_at`
- persistent index: `magnitude`
- optional composite index: `(occurred_at, magnitude)` after profiling
- optional indexes on `status`, `alert`, `network` only if query plans justify them

### `event_revisions`
- `(event_key, revision_number)`
- `observed_at`

### `alert_rules`
- `user_id`
- `enabled`

### `ingestion_runs`
- `started_at`
- `status`

Index choices must be demonstrated with `EXPLAIN`/profiling rather than added blindly.

## 7. Ingestion State Machine

```text
FETCH
  ↓
HTTP + SCHEMA VALIDATION
  ↓
NORMALIZE
  ↓
IDENTIFY source + source_event_id
  ↓
LOAD CURRENT EVENT
  ├── absent ──> INSERT canonical + first revision
  │
  └── exists
       ↓
     DIFF
       ├── no meaningful change ──> update last_seen
       └── meaningful change ─────> append revision + update canonical
  ↓
UPSERT GRAPH RELATIONSHIPS
  ↓
EVALUATE ALERT RULES
  ↓
COMMIT
  ↓
WRITE METRICS / INGESTION LOG
```

Canonical update and revision append should be transactional where consistency requires both to succeed together.

## 8. Meaningful Revision Policy

Do not create revisions for operational metadata such as `last_seen_at`.

Revision-triggering source fields can include:
- magnitude,
- magnitude type,
- depth,
- latitude/longitude beyond a defined tolerance,
- place,
- status,
- alert,
- tsunami flag,
- MMI/CDI,
- significance if analytically relevant,
- scientific product availability.

The revision policy itself should be versioned.

## 9. Django Module Boundaries

```text
apps/
  accounts/
  earthquakes/
  ingestion/
  geo/
  alerts/
  analytics/
  research/
  operations/
```

Suggested route families:

```text
GET  /api/v1/events
GET  /api/v1/events/{id}
GET  /api/v1/events/{id}/revisions
GET  /api/v1/events/map
GET  /api/v1/analytics/summary
GET  /api/v1/analytics/timeseries

GET  /api/v1/alert-rules
POST /api/v1/alert-rules
PATCH /api/v1/alert-rules/{id}
DELETE /api/v1/alert-rules/{id}

POST /api/v1/research/snapshots
GET  /api/v1/research/snapshots/{id}
GET  /api/v1/research/snapshots/{id}/export

GET  /api/v1/system/health
GET  /api/v1/system/freshness
```

Pagination is mandatory on event lists.

## 10. Frontend Design

### Dashboard
- latest synchronization time,
- recent event count,
- strongest recent event,
- significant events,
- magnitude chart,
- activity timeline,
- map preview.

### Live Map
- magnitude-scaled markers,
- clustering,
- filters,
- viewport-aware loading,
- side panel,
- legend,
- freshness indicator.

### Explorer
- advanced filters,
- sortable table,
- map/table toggle,
- query summary,
- save query,
- export.

### Event Detail
Tabs:
1. Overview
2. Revision Timeline
3. Scientific Products
4. Relationships
5. Provenance / Raw Metadata

### Analytics
- time series,
- magnitude-depth scatter,
- regional counts,
- revision analytics,
- ingestion latency.

### Research Lab
- define dataset,
- freeze snapshot,
- export data + manifest,
- inspect schema/app version.

### Operations
- sync status,
- API failures,
- dead letters,
- job durations,
- DB counts,
- index/query diagnostics.

## 11. Alert Engine

Rules are data, never executable user code.

Example:

```json
{
  "name": "Strong earthquakes near watch area",
  "enabled": true,
  "conditions": {
    "minimum_magnitude": 5.5,
    "center": [78.4867, 17.3850],
    "radius_km": 300,
    "maximum_depth_km": 100
  },
  "cooldown_minutes": 30
}
```

Evaluation output:

```json
{
  "matched": true,
  "reason": [
    "magnitude 5.9 >= 5.5",
    "distance 214 km <= 300 km",
    "depth 42 km <= 100 km"
  ]
}
```

These are application notifications, not official emergency alerts.

## 12. Research Data Layer

Each research snapshot stores:

```json
{
  "snapshot_id": "...",
  "created_at": "...",
  "source": "USGS",
  "query_definition": {},
  "source_request_manifest": [],
  "schema_version": 1,
  "application_version": "git-sha",
  "row_count": 12345,
  "content_sha256": "...",
  "notes": "..."
}
```

For reproducibility, preserve either:
- raw source payloads for a justified retention period, or
- payload hashes + source-request manifests + normalized revisions.

## 13. Reliability

### Timeouts
Every external HTTP request has connection/read timeouts.

### Retries
Retry only transient failures:
- timeout,
- temporary network error,
- appropriate 429,
- 5xx.

Use exponential backoff with jitter.

### Circuit Breaker
After repeated upstream failure:
- reduce retry pressure,
- continue serving stored data,
- mark source freshness as degraded.

### Dead Letters
Persist failed records with:
- source ID,
- payload hash,
- reason,
- first/last failure,
- retry count.

### Idempotency
Replaying the same feed must not duplicate events, revisions, or alert matches.

## 14. Security

- Django authentication.
- CSRF protection.
- secure cookies in production.
- server-side input validation.
- per-user authorization.
- admin-only ingestion controls.
- secrets outside Git.
- secure response headers.
- dependency scanning.
- rate limiting on expensive queries/exports.
- audit logs for privileged operations.

## 15. Observability

### Structured Log Fields
- timestamp,
- level,
- correlation_id,
- ingestion_run_id,
- source,
- source_event_id,
- endpoint,
- duration_ms,
- outcome.

### Metrics
- sync success/failure,
- source response latency,
- events fetched,
- inserts,
- updates,
- revisions,
- unchanged duplicates,
- rejected records,
- alert matches,
- API p50/p95,
- AQL query latency.

### Health Endpoints
- `/health/live`
- `/health/ready`
- `/system/freshness`

## 16. Testing Strategy

### Unit
- GeoJSON normalizer,
- revision differ,
- alert matcher,
- geodesic calculations,
- export manifest/checksum.

### Contract
Use recorded USGS payload fixtures to detect source-schema breakage.

### Integration
- Django ↔ ArangoDB,
- transactional revision updates,
- indexed AQL filters,
- authorization.

### End-to-End
- dashboard,
- filters,
- event detail,
- CRUD alert rules,
- research export,
- admin health.

### Resilience
- upstream timeout,
- malformed JSON,
- duplicate feed replay,
- detail-feed failure,
- database failure.

### Performance
Benchmark:
- event list before/after indexes,
- geo-radius query,
- analytics aggregate,
- revision lookup,
- datasets at 500, 10k, and 100k+ records when feasible.

## 17. CI/CD

GitHub Actions:

```text
lint
  ↓
unit tests
  ↓
integration tests
  ↓
dependency/security checks
  ↓
container build
  ↓
optional demo deployment
```

Critical test failures block merge.

## 18. Deployment Profiles

### Local / College Demo
Docker Compose:
- web
- worker
- redis
- arangodb

### Small Cloud Demo
- containerized Django web,
- background worker,
- persistent ArangoDB storage,
- HTTPS/reverse proxy,
- automated backup.

Do not add Kubernetes only for appearance.

## 19. Academic Rubric Mapping

| Rubric concept | QuakeWatch implementation |
|---|---|
| NoSQL DB | ArangoDB |
| Schema/ERD | document + edge collection diagram |
| PK | `_key` + unique `(source, source_event_id)` |
| FK | graph edges/document references |
| 3NF wording | conceptual decomposition + NoSQL explanation |
| Complex queries | AQL filters, aggregates, joins/traversals, geo |
| Views | ArangoSearch/application views if justified |
| Trigger/procedure wording | service/job logic; do not falsely claim SQL procedures |
| Transactions | canonical update + revision append |
| Indexes | persistent + geo |
| 500+ records | historical backfill |
| CRUD | alert rules, saved searches, research objects |
| Performance | `EXPLAIN`, profiling, index comparison |
| Frontend | Bootstrap + JS + map/charts |

## 20. Research Extensions

### A. Multi-Source Concordance
Add EMSC through its FDSN event API.

Store each source observation separately and derive matching/concordance records.

Research metrics:
- first-report latency,
- magnitude discrepancy,
- epicenter discrepancy,
- convergence time.

### B. Revision Intelligence
Use early event metadata to classify whether a record will receive a material revision.

This predicts **metadata revision**, not earthquakes.

### C. Spatiotemporal Graph
Create relationships only using scientifically defined temporal/spatial criteria.

Do not label relationships as aftershocks unless methodology supports that interpretation.

## 21. Architecture Decision Records

Create:

- ADR-001: Why ArangoDB
- ADR-002: Why modular monolith
- ADR-003: Canonical event + immutable revisions
- ADR-004: Polling and freshness strategy
- ADR-005: Alert rule representation
- ADR-006: Research snapshot reproducibility
- ADR-007: Raw-data retention policy
- ADR-008: Multi-source canonicalization

## 22. External References

- USGS real-time feeds: https://earthquake.usgs.gov/earthquakes/feed/
- USGS GeoJSON summary: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- USGS GeoJSON detail: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson_detail.php
- USGS Catalog API: https://earthquake.usgs.gov/fdsnws/event/1/
- USGS ShakeMap: https://earthquake.usgs.gov/data/shakemap/
- USGS PAGER: https://earthquake.usgs.gov/data/pager/
- EMSC FDSN Event API: https://www.seismicportal.eu/fdsn-wsevent.html
