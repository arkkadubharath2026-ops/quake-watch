# QuakeWatch

> Real-time earthquake intelligence, revision-aware analytics, and reproducible seismic-data exploration using ArangoDB and Django.

QuakeWatch is an open-source academic and research-oriented web application that ingests earthquake information from authoritative public sources, stores it in a multi-model NoSQL database, tracks how events evolve after first publication, and exposes the data through maps, search, analytics, alert rules, and research exports.

**QuakeWatch is not an earthquake prediction system and is not an official emergency-warning service.**

## Why QuakeWatch?

A basic earthquake project can fetch an API and put markers on a map. QuakeWatch is designed to go further:

- continuously ingest live earthquake data,
- backfill historical catalog data,
- perform idempotent updates,
- preserve event revision history,
- expose source provenance,
- query geospatially with ArangoDB,
- model real relationships as a graph,
- provide explainable watch/alert rules,
- create reproducible research datasets,
- benchmark indexes and AQL query performance,
- remain useful when the upstream source is temporarily unavailable.

This makes the project suitable for a serious NoSQL/database course while also creating a foundation for later research.

## Quick Start

Requirements: Docker (for ArangoDB — the only database/stateful service), Python 3.12.

```bash
cp .env.example .env                      # then set QW_SECRET_KEY and the ArangoDB passwords
docker compose up -d arangodb
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # (bin/ on Linux/macOS)
.venv/Scripts/python manage.py arango_migrate     # all collections (data, accounts, jobs...), indexes, view, graph
.venv/Scripts/python manage.py sync_feed          # ingest the live USGS feed now
.venv/Scripts/python manage.py backfill --start 2026-08-26 --end 2026-09-25 --min-magnitude 2.5
```

Then run `.venv/Scripts/python manage.py runserver` and open http://127.0.0.1:8000 — create an account
at `/accounts/signup/` (use `manage.py createsuperuser` for a staff account that can open `/operations/`).

Background jobs run with `manage.py run_worker --with-scheduler` (ArangoDB job queue, ADR-014).

Full stack in containers (web + worker + scheduler + ArangoDB):

```bash
docker compose up -d --build              # web on http://127.0.0.1:8000, health at /health/ready
```

### Operator commands
| Command | Purpose |
|---|---|
| `manage.py arango_migrate` | idempotent schema reconciliation + versioned data migrations |
| `manage.py sync_feed [--feed all_day]` | one feed sync (same code path as the scheduled task) |
| `manage.py backfill --start … --end … [--min-magnitude] [--window-days] [--enqueue] [--resume ID]` | bounded, checkpointed catalog import |
| `manage.py enrich_event <event_key>` | fetch detail-feed product summaries for one event |
| `manage.py aql_catalog [--write]` | EXPLAIN every named AQL query; regenerate docs/AQL_QUERIES.md |
| `manage.py arango_benchmark [--sizes 500,10000,100000] [--write]` | index before/after benchmark on a disposable `*_bench_test` database; regenerate docs/BENCHMARKS.md |

### Tests
```bash
.venv/Scripts/python -m pytest                 # unit, contract, resilience, integration, architecture
.venv/Scripts/python -m playwright install chromium   # once, for the browser suite
.venv/Scripts/python -m pytest tests/e2e -m e2e      # browser flows + WCAG 2.2 AA audit (axe-core)
.venv/Scripts/python -m pytest -m live         # opt-in: real USGS API contract checks
```
Integration and browser tests use a real ArangoDB (`<db>_test`, created and dropped per run) —
nothing in those suites mocks the database. CI (`.github/workflows/ci.yml`) runs lint → unit →
integration (coverage ≥ 90 %) → browser/a11y → dependency audit + deploy checks → container build.

## Implementation Status

| Layer | Scope | State |
|---|---|---|
| L0 Harness | repo, Docker, Claude tooling (CLAUDE.md, agents, skills, hooks), Graphify | done |
| L1 Foundations | typed config, logging, errors, metrics, ArangoDB schema/migrations/transactions, health | done |
| L2 Ingestion | USGS adapters, normaliser, revision policy, identity claims, pipeline, backfill, enrichment, background jobs | done |
| L3 Query & API | event search/map/detail/revisions/provenance/graph, analytics, freshness, ops API, 47 catalogued AQL queries | done |
| L4 User features | explainable alert rules + in-transaction matching, saved searches, reproducible research snapshots, admin actions, audit trail, login throttling | done |
| L5 UI | design system (light/dark), dashboard, live map, explorer, event detail, analytics, alerts, research lab, status, operations, about, accounts | done |
| L6 Hardening | index benchmarks (500/10k/100k) with a fixed list-query regression, Playwright E2E, WCAG 2.2 AA audit and fixes, GitHub Actions CI, runbook | done |

Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · UI: [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) · Progress: [docs/PROGRESS.md](docs/PROGRESS.md) · AQL: [docs/AQL_QUERIES.md](docs/AQL_QUERIES.md) · Benchmarks: [docs/BENCHMARKS.md](docs/BENCHMARKS.md) ·
Accessibility: [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md) · Operations: [docs/RUNBOOK.md](docs/RUNBOOK.md) · Rubric: [docs/RUBRIC.md](docs/RUBRIC.md) · Decisions: [docs/adr/](docs/adr/) · Dependencies: [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)

## Primary Data Source

### U.S. Geological Survey (USGS)

Official real-time earthquake feeds:

https://earthquake.usgs.gov/earthquakes/feed/

GeoJSON summary format:

https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

GeoJSON event detail format:

https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson_detail.php

Earthquake Catalog API:

https://earthquake.usgs.gov/fdsnws/event/1/

USGS should be credited as the data source. USGS-produced information is generally public domain in the United States, while third-party material must be handled according to its own rights/attribution requirements.

## Core Workflow

```text
USGS Real-Time / Catalog APIs
            │
            ▼
    Django Source Adapters
            │
            ▼
 Validate + Normalize + Hash
            │
            ▼
   Idempotent Event Upsert
       │            │
       │ changed?   │ new?
       ▼            ▼
Revision Store   Canonical Event
       └──────┬─────┘
              ▼
          ArangoDB
    Documents + Graph + Geo
              │
       ┌──────┼────────┐
       ▼      ▼        ▼
     Search Analytics Alerts
       │      │        │
       └──────┼────────┘
              ▼
     Django Web Application
              │
  Dashboard / Map / Explorer
  Detail / Research / Admin
```

## Technology Stack

### Core
- **Database:** ArangoDB Community Edition
- **Backend:** Python + Django
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Repository:** GitHub

### Recommended
- **Map:** Leaflet.js
- **Charts:** Chart.js
- **Background jobs:** ArangoDB-backed job queue + scheduler (`apps.jobs`; replaced Celery, ADR-014)
- **Cache / sessions / accounts:** ArangoDB (replaced Redis and SQLite, ADR-014/015)
- **Testing:** pytest + pytest-django
- **Containers:** Docker / Docker Compose
- **CI:** GitHub Actions

The architecture intentionally starts as a modular monolith instead of unnecessary microservices.

## Major Features

### Real-Time Situational Dashboard
- current source freshness,
- recent event count,
- strongest recent events,
- significant events,
- magnitude/depth summaries,
- activity timeline.

### Live Earthquake Map
- interactive map,
- marker clustering,
- magnitude-aware visualization,
- viewport filtering,
- event quick view.

### Earthquake Explorer
Filter by:
- date/time,
- magnitude,
- depth,
- location,
- geographic radius/bounding box,
- alert level,
- tsunami flag,
- status,
- network.

### Event Detail
- canonical current data,
- source metadata,
- revision timeline,
- related region/network,
- scientific-product availability,
- provenance/raw-source metadata.

### Revision Intelligence
QuakeWatch keeps meaningful changes rather than silently overwriting them:
- magnitude changes,
- depth changes,
- epicenter updates,
- status changes,
- alert changes,
- product updates.

### Alerts / Watch Rules
Users can create deterministic rules such as:

```text
Magnitude >= 5.5
AND within 300 km of selected location
AND depth <= 100 km
```

Every match explains exactly why it triggered.

### Analytics
- magnitude distribution,
- depth distribution,
- events over time,
- region/network statistics,
- revision-frequency analysis,
- ingestion-latency analysis.

### Research Lab
- freeze filtered datasets,
- export CSV/JSON,
- generate metadata manifest,
- record source/query/schema/app version,
- checksum exports for reproducibility.

### Operations Dashboard
- sync history,
- upstream failures,
- retries,
- rejected records,
- freshness,
- DB/query performance.

## Proposed ArangoDB Model

### Document Collections

```text
events
event_revisions
regions
networks
alert_rules
alert_matches
saved_searches
research_snapshots
ingestion_runs
dead_letters
```

### Edge Collections

```text
event_in_region
event_reported_by_network
user_owns_rule
rule_matched_event
```

Graph edges are created only when they support a real product or research query.

## Example Event Document

```json
{
  "_key": "usgs_us7000xxxx",
  "source": "USGS",
  "source_event_id": "us7000xxxx",
  "magnitude": 5.9,
  "magnitude_type": "mww",
  "place": "Example region",
  "occurred_at": "2026-09-21T00:00:00Z",
  "source_updated_at": "2026-09-21T00:04:00Z",
  "longitude": 80.1,
  "latitude": 15.4,
  "depth_km": 18.2,
  "coordinates": [80.1, 15.4],
  "alert": "green",
  "status": "reviewed",
  "tsunami": false,
  "significance": 0,
  "first_seen_at": "2026-09-21T00:01:30Z",
  "last_ingested_at": "2026-09-21T00:05:00Z",
  "schema_version": 1
}
```

## Repository Layout

```text
quakewatch/
├─ apps/
│  ├─ accounts/
│  ├─ earthquakes/
│  ├─ ingestion/
│  ├─ geo/
│  ├─ alerts/
│  ├─ analytics/
│  ├─ research/
│  └─ operations/
├─ config/
├─ templates/
├─ static/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ contract/
│  └─ e2e/
├─ scripts/
├─ docs/
│  ├─ PRD.md
│  ├─ ESD.md
│  └─ adr/
├─ docker/
├─ docker-compose.yml
├─ requirements.txt
├─ manage.py
└─ README.md
```

## Development Phases

### Phase 1 — Database + Ingestion Spine
- set up ArangoDB,
- create collections/indexes,
- implement USGS summary adapter,
- historical catalog importer,
- idempotent upserts,
- ingestion-run logs.

### Phase 2 — Core Application
- dashboard,
- explorer,
- live map,
- detail page,
- pagination and filtering.

### Phase 3 — Database Depth
- graph edges,
- geospatial queries,
- 15+ documented AQL queries,
- transactions,
- index benchmarking,
- query-plan analysis.

### Phase 4 — Product Differentiators
- revision timeline,
- saved searches,
- alert/watch rules,
- research snapshots,
- provenance.

### Phase 5 — Hardening
- retries/backoff,
- dead-letter handling,
- caching,
- security,
- observability,
- automated tests.

### Phase 6 — Research Extension
Choose one focused research question and build a reproducible experiment rather than adding random AI.

## Research Directions

A publication should contain a measurable research contribution, not just the software.

### 1. Earthquake Record Revision Dynamics
Study how magnitude, location, depth, and review status change between initial and later reports.

### 2. Multi-Source Consistency
Add EMSC as a second open source and measure:
- first-report latency,
- magnitude disagreement,
- epicentral disagreement,
- convergence over time.

EMSC FDSN Event API:

https://www.seismicportal.eu/fdsn-wsevent.html

### 3. Revision-Likelihood Modeling
Predict whether an early event record will later receive a material metadata revision.

This is a data-quality problem and must **not** be described as earthquake prediction.

### 4. Spatiotemporal Sequence Analysis
Study event clustering with explicit, scientifically justified temporal/spatial criteria.

## Academic Requirements Covered

QuakeWatch demonstrates:

- open-source NoSQL DBMS,
- schema and graph design,
- 500+ database records,
- frontend ↔ backend ↔ database connectivity,
- CRUD,
- complex AQL,
- aggregation,
- graph traversal,
- geospatial queries,
- transactions,
- indexes,
- query optimization,
- security,
- testing,
- performance tuning,
- dashboards/reports,
- GitHub repository,
- demo-ready web application.

For relational wording in the academic rubric, document the correct ArangoDB equivalent instead of pretending ArangoDB is SQL.

## Example AQL Questions

The final project should include at least 15 meaningful queries:

1. strongest events in a date range,
2. events within a geographic radius,
3. average magnitude by region,
4. magnitude distribution by month,
5. deepest events,
6. tsunami-flagged events,
7. reviewed vs automatic status counts,
8. events with the most revisions,
9. average time from first seen to reviewed,
10. graph traversal from region to associated events,
11. network-specific event statistics,
12. significant events by period,
13. watch-rule matched events,
14. events whose magnitude changed beyond a threshold,
15. ingestion latency percentiles.

## Data Integrity Rules

- Source + event ID defines external identity.
- Repeat ingestion is idempotent.
- Canonical data reflects the latest accepted source revision.
- Meaningful source changes create immutable revision records.
- Application-derived values never overwrite source values.
- Every research export is traceable to filters and generation metadata.
- Upstream failure is visible through freshness/status indicators.

## Safety and Scientific Integrity

QuakeWatch must clearly state:

- it does not reliably predict earthquakes,
- application notifications are not emergency early warnings,
- official emergency agencies remain authoritative,
- derived analytics may contain uncertainty,
- users should follow official local emergency guidance.

## Competitor / Reference Systems

### USGS
- real-time feeds/catalog,
- ShakeMap,
- PAGER,
- DYFI,
- ENS,
- ShakeAlert.

https://earthquake.usgs.gov/

### EMSC LastQuake
- earthquake information,
- crowdsourced felt/damage testimony,
- user comments/media.

https://www.emsc-csem.org/lastquake/

QuakeWatch's differentiation is **revision-aware data engineering + provenance + NoSQL graph/geospatial exploration + reproducible research workflows**, not a claim to be more authoritative than these organizations.

## License

Choose the repository license deliberately.

MIT or Apache-2.0 are common choices for the application source code. Data attribution and third-party licenses remain separate from the code license.

Suggested acknowledgment:

> Earthquake data courtesy of the U.S. Geological Survey (USGS).

## Documentation

- `docs/PRD.md` — product scope, users, differentiation, requirements, research potential.
- `docs/ESD.md` — architecture, data model, ingestion, reliability, security, testing, deployment.
- `docs/ARCHITECTURE.md` — as-built architecture, data model, rubric mapping, ingestion flow.
- `docs/adr/` — architecture decision records (ADR-001 … ADR-013).
- `docs/RENDER_DEPLOY.md` — deploying to Render (`render.yaml` Blueprint).
- `docs/DEPENDENCIES.md` — why each dependency exists.
- `docs/AQL_QUERIES.md` — the 47 named AQL queries with live EXPLAIN plans (generated).
- `docs/BENCHMARKS.md` — index before/after benchmark at 500 / 10k / 100k records (generated).
- `docs/DESIGN_SYSTEM.md` and `docs/ACCESSIBILITY.md` — UI tokens, components, states; WCAG 2.2 AA audit.
- `docs/SECURITY_REVIEW.md` — security reviews per milestone and their fixes.
- `docs/RUNBOOK.md` — operating, troubleshooting, backup/restore, release checklist.
- `docs/RUBRIC.md` — academic rubric mapped to implementation and evidence.
- `docs/PROGRESS.md` — milestone checklist (`python scripts/dashboard.py` renders the dashboard).

## Current Recommended Milestone

All planned milestones (L0–L6) are complete — see [docs/PROGRESS.md](docs/PROGRESS.md). The original
recommendation was followed: the build started with

> Historical backfill + live USGS synchronization + idempotent ArangoDB storage + revision tracking + system-health dashboard.

(L1–L2), and the map, analytics, alerts and research layers were built on that foundation. The
natural next step is a research extension (ESD §20), e.g. EMSC multi-source concordance.
