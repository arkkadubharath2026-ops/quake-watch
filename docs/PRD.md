# QuakeWatch — Product Requirements Document (PRD)

**Version:** 1.0  
**Status:** Build-ready draft  
**Product:** QuakeWatch  
**Primary stack:** ArangoDB + Python/Django + HTML/CSS/JavaScript/Bootstrap  
**Primary data source:** U.S. Geological Survey (USGS) Earthquake Hazards Program

## 1. Product Vision

QuakeWatch is a real-time earthquake intelligence platform that continuously ingests authoritative earthquake data, preserves how event information changes over time, organizes the data as both documents and relationships, and turns it into understandable dashboards, maps, alerts, and reproducible research datasets.

It is **not** an earthquake prediction system and is **not** a replacement for official emergency-warning systems.

Its core differentiator is that every earthquake is treated as an evolving scientific record with provenance, revisions, related products, geographic context, and user-defined monitoring rules.

## 2. Why This Product Should Exist

Existing systems solve different parts of the problem:

- **USGS feeds/catalog** provide authoritative earthquake event information.
- **USGS ShakeMap** provides near-real-time shaking intensity products.
- **USGS PAGER** estimates population exposure and possible losses.
- **USGS ENS** provides notification subscriptions.
- **USGS ShakeAlert** provides early warning in supported U.S. regions.
- **EMSC LastQuake** focuses strongly on rapid public communication and crowdsourced felt reports.

QuakeWatch should not copy these systems. It should provide a unified engineering and research workspace for:

1. ingesting and normalizing event data,
2. tracking revisions,
3. exposing provenance,
4. combining document, graph, temporal, and geospatial exploration,
5. creating transparent alert rules,
6. producing reproducible research exports,
7. demonstrating a serious NoSQL architecture.

## 3. Target Users

### Students and researchers
- Explore historical and recent seismic events.
- Build reproducible datasets from explicit filters.
- Study revision dynamics, spatial clusters, magnitude/depth distributions, and source latency.
- Export analysis-ready CSV/JSON.

### Disaster-management learners and analysts
- Monitor recent significant earthquakes.
- Inspect magnitude, depth, region, source status, and available scientific products.
- Save watch regions and threshold-based rules.

### General users
- Understand what happened, where, when, and how strong.
- Search without using raw APIs.

### Administrators
- Monitor ingestion health, API failures, stale data, duplicates, and query performance.

## 4. User Problems and Product Responses

### P1 — Data is available but fragmented
**Response:** Normalize feeds, event details, related products, and metadata around one event-centric record.

### P2 — Earthquake records change after first publication
Magnitude, depth, coordinates, status, and products can be revised.

**Response:** Preserve meaningful revision history instead of silently overwriting changes.

### P3 — Maps alone are not enough
**Response:** Combine map, table, charts, advanced filters, saved queries, and exports.

### P4 — Alerts can be opaque
**Response:** Use deterministic rules with explanations, for example:  
`Matched because magnitude 6.4 >= 6.0 AND distance 132 km <= 250 km`.

### P5 — Research datasets are difficult to reproduce
**Response:** Store query definition, retrieval time, source, record count, schema version, application version, and checksum.

### P6 — Data trust is invisible
**Response:** Clearly separate source values from derived values and display source/update timestamps.

## 5. Product Principles

1. Source truth first.
2. Preserve revisions.
3. Explain derived values.
4. Never invent missing scientific values.
5. No earthquake-prediction claims.
6. Fast overview with deep drill-down.
7. Research reproducibility by design.
8. Graceful degradation when upstream APIs are unavailable.

## 6. Scope

### MVP
- USGS GeoJSON summary-feed ingestion.
- Historical backfill through USGS Catalog API.
- ArangoDB event storage.
- Event revision history.
- Interactive map.
- Event explorer.
- Event detail page.
- Analytics dashboard.
- User accounts.
- Saved searches.
- User-defined alert rules.
- Admin ingestion-health dashboard.
- CSV/JSON research export.
- 15+ meaningful AQL queries.
- Indexes, transactions, testing, and performance benchmarks.

### Version 1.1
- Lazy USGS detail-feed enrichment.
- ShakeMap/PAGER/DYFI availability indicators where exposed.
- Event comparison.
- Research dataset snapshots.
- Revision-diff visualization.
- Email/webhook notification adapters.

### Research Track
- Multi-source comparison with EMSC SeismicPortal.
- Cross-source latency/disagreement analysis.
- Spatiotemporal clustering.
- Record-revision modeling.
- Graph-based regional/source relationships.
- Reproducible experiment registry.

### Out of Scope
- Earthquake prediction claims.
- Replacing official early-warning systems.
- Issuing evacuation instructions as an authority.
- Unvalidated proprietary “risk scores.”
- Scraping copyrighted media unnecessarily.

## 7. Core User Journeys

### A. What is happening now?
Dashboard → recent events → map → event detail → source/revision/product information.

### B. Find earthquakes matching a condition
Explorer → filters → table/map → save search or export.

### C. Watch an area
Create watch region → set magnitude/depth/distance rule → new event ingested → rule evaluated → in-app notification with explanation.

### D. See how an event changed
Event Detail → Revision Timeline → compare initial and later magnitude/depth/location/status.

### E. Create a research dataset
Define fixed query → freeze snapshot → store manifest → export CSV/JSON.

## 8. Functional Requirements

- **FR-01:** Scheduled USGS feed ingestion.
- **FR-02:** Bounded historical backfill through Catalog API.
- **FR-03:** Idempotent upserts using source + event ID.
- **FR-04:** Meaningful revision tracking.
- **FR-05:** Provenance for every sourced event.
- **FR-06:** Filters by time, magnitude, depth, geography, alert, tsunami, status, network, and location text.
- **FR-07:** Geospatial map with clustering and viewport-aware loading.
- **FR-08:** Event detail with canonical record, revisions, provenance, relationships, and product availability.
- **FR-09:** Analytics for magnitude, depth, time, region, revisions, and ingestion latency.
- **FR-10:** CRUD for user alert rules.
- **FR-11:** Explainable alert matches.
- **FR-12:** Saved searches.
- **FR-13:** Research exports with metadata manifests.
- **FR-14:** Admin ingestion and health dashboard.
- **FR-15:** Audit trail for important administrative actions.

## 9. Non-Functional Requirements

### Reliability
- No duplicate canonical records for the same source event.
- Retryable/idempotent ingestion.
- Detail enrichment failure must not block basic ingestion.

### Performance
Targets for the academic/demo deployment:
- p95 common filtered API query < 500 ms where practical.
- dashboard API < 800 ms under normal demo load.
- map endpoints must use bounded queries/clustering.

### Security
- Django authentication.
- CSRF protection.
- secure production cookies.
- role-based admin authorization.
- server-side validation.
- rate limits for expensive operations.
- secrets outside source control.

### Observability
- structured logs,
- ingestion metrics,
- API latency,
- error rate,
- database query timings,
- source freshness.

### Reproducibility
Exports must include:
- source,
- query definition,
- generated timestamp,
- schema version,
- application version/commit SHA where available,
- checksum.

## 10. Information Architecture

1. Home / Situational Dashboard
2. Live Map
3. Earthquake Explorer
4. Earthquake Detail
5. Analytics
6. Watchlists & Alerts
7. Research Lab / Exports
8. System Status
9. Admin Data Operations
10. About Data & Methodology

## 11. Competitive Positioning

### USGS
Authoritative source with mature scientific products.  
**QuakeWatch adds:** unified exploration, revision history, research exports, transparent NoSQL architecture.

### EMSC LastQuake
Strong crowdsourced felt reports and public communication.  
**QuakeWatch adds:** provenance, structured analytics, revision comparison, reproducibility.

### USGS ENS
Mature notifications.  
**QuakeWatch adds:** explainable rules tied to saved analytical context.

### ShakeAlert
Real early warning in supported regions.  
**QuakeWatch must not claim to replace it.**

### PAGER / ShakeMap
Mature impact and shaking products.  
**QuakeWatch should surface and contextualize them, not invent competing estimates without validation.**

## 12. Research-Paper Potential

A publishable paper needs a measurable research question, baseline, experiment, and contribution. The software alone is not the paper.

### RQ1 — Event Revision Dynamics
How often and how substantially do initially published event parameters change?

Metrics:
- magnitude delta,
- depth delta,
- epicenter displacement,
- time-to-reviewed status,
- revision count.

### RQ2 — Multi-Source Latency and Consistency
With a second open catalogue:
- first-observed latency,
- magnitude disagreement,
- location disagreement,
- convergence time.

### RQ3 — Revision-Likelihood Modeling
Can early metadata predict whether an event record will later receive a material revision?

This predicts **record revision**, not earthquakes.

### RQ4 — Spatiotemporal Sequence Characterization
Study clusters/sequences using transparent spatial and temporal methods and established seismological definitions.

Research requirements:
- immutable/raw manifests,
- versioned feature pipeline,
- reproducible scripts,
- temporal splits for ML,
- strong baselines,
- confidence intervals,
- no leakage,
- explicit limitations.

## 13. Success Metrics

### Product
- 99%+ successful sync runs during evaluation where upstream is available.
- Zero duplicate canonical records in controlled testing.
- Correct revision reconstruction.
- Appropriate indexes on core query paths.

### Academic
- 500+ records.
- 15+ meaningful AQL queries.
- CRUD on genuine user-owned data.
- Graph traversal.
- Geospatial querying.
- Transactions.
- Index before/after benchmark.
- 5+ frontend pages.
- Test and performance evidence.

### Research Readiness
- deterministic export manifests,
- version/source metadata,
- repeatable analyses,
- documented limitations.

## 14. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Upstream API unavailable | retries, cached/local data, freshness indicator |
| Source record revised | revision store + canonical current record |
| Duplicate ingestion | unique source-event identity + idempotent upsert |
| Map overloaded | viewport queries, clustering, pagination |
| Misleading risk claims | rely on authoritative products and transparent methods |
| Research leakage | temporal splits and versioned datasets |
| SQL wording in NoSQL rubric | document ArangoDB equivalents explicitly |
| Alert spam | deduplication, cooldowns, match history |
| Source schema changes | source adapter + contract tests |

## 15. Official References

- USGS real-time feeds: https://earthquake.usgs.gov/earthquakes/feed/
- USGS GeoJSON summary: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- USGS GeoJSON detail: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson_detail.php
- USGS Catalog API: https://earthquake.usgs.gov/fdsnws/event/1/
- USGS ShakeMap: https://earthquake.usgs.gov/data/shakemap/
- USGS PAGER: https://earthquake.usgs.gov/data/pager/
- USGS DYFI: https://earthquake.usgs.gov/data/dyfi/
- USGS ShakeAlert: https://earthquake.usgs.gov/data/shakealert/
- EMSC LastQuake: https://www.emsc-csem.org/lastquake/
- EMSC FDSN event API: https://www.seismicportal.eu/fdsn-wsevent.html

Credit the U.S. Geological Survey as the primary source. USGS-produced information is generally public domain in the United States; third-party content must be handled according to its own rights and attribution requirements.
