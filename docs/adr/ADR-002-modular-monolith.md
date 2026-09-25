# ADR-002: Modular Django monolith with background workers

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
The hard problems are data correctness, revision handling, provenance, reproducibility, geo query
performance and ingestion reliability — not independent scaling of services.

## Decision
One Django project with domain apps (`core`, `geo`, `earthquakes`, `ingestion`, `alerts`,
`analytics`, `research`, `operations`, `accounts`). Background work (feed sync, backfill, alert
evaluation) runs in Celery workers scheduled by Celery beat, with Redis as broker/cache only.

Layering inside apps: pure domain/policy modules → repositories (AQL) → services → API/views.
Boundaries are enforced by `tests/architecture/test_boundaries.py`:
python-arango only in repositories/`apps/core/arango`, httpx only in `apps/ingestion/adapters`,
pure modules free of framework and I/O imports.

## Consequences
- Single deployable image (web/worker/beat are the same image with different commands).
- In-process calls between modules; no network contracts to version internally.
- Can later split ingestion into its own service along the adapter/pipeline boundary if needed.
- No Kubernetes (ESD §18).
