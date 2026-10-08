# QuakeWatch build progress

This checklist is the single source for `scripts/dashboard.py`. A task is ticked only when it is
implemented, verified (tests + milestone gate) and committed. Milestone percentage = ticked tasks /
tasks in that milestone; overall percentage = mean of milestone percentages (every milestone weighs
the same). Never edit percentages by hand — they are computed.

## L0 Harness
- [x] Repository layout, pyproject (ruff, mypy strict, pytest markers), requirements pinned
- [x] Docker Compose: ArangoDB, shared app image for web/worker/scheduler (Redis removed by ADR-014)
- [x] Claude tooling: CLAUDE.md, agents, skills, hooks (secrets guard, ruff on edit)
- [x] Graphify knowledge graph + post-commit rebuild
- [x] Dependency register (docs/DEPENDENCIES.md) and LF line-ending policy

## L1 Foundations
- [x] Typed settings (pydantic-settings, QW_ prefix) and split test settings
- [x] Structured logging with correlation IDs, error envelope, metrics
- [x] ArangoDB client, declarative schema, idempotent migrations with index-drift repair
- [x] Stream transactions with conflict retry; exclusive-lock helper
- [x] Health endpoints (liveness/readiness) and architecture-boundary tests

## L2 Ingestion
- [x] USGS adapters (summary, catalog, detail) behind httpx-only boundary, recorded contract fixtures
- [x] Normaliser and versioned revision policy with tolerances
- [x] Transactional pipeline: identity claims, revisions, merges, dead letters, fast path
- [x] Resilience: jittered backoff, Retry-After, shared circuit breaker (ArangoDB, ADR-014), provenance manifests
- [x] Background sync/backfill/enrichment jobs with checkpoints, split windows, idempotency (Celery, since ADR-014 the ArangoDB job queue `apps.jobs`)
- [x] Verified against real USGS data (live feed + 30-day backfill)

## L3 Query & API
- [x] Event search with filters, allow-listed sort, pagination; map viewport + server clusters
- [x] Event detail, revisions, provenance, graph relationships
- [x] Analytics aggregates (15+ AQL questions) with caching
- [x] Operations: freshness, ingestion runs, dead letters
- [x] Named AQL catalogue with EXPLAIN plan checks; generated docs/AQL_QUERIES.md

## L4 User features
- [x] Alert rules: pure matcher, in-transaction observer, cooldown, notification feed
- [x] Saved searches
- [x] Research snapshots: pinned revisions, SHA-256 manifests, deterministic zip export
- [x] Staff admin actions with append-only audit log
- [x] Accounts: throttled login backend, lockout, user-deletion cleanup
- [x] Independent security review; all findings fixed with regression tests

## L5 User interface
- [x] Frontend libraries vendored and hash-locked (no CDN, strict CSP)
- [x] Design system: tokens, typography, light/dark themes, component states
- [x] Base layout: navigation, freshness indicator, attribution, safety disclaimer, error pages
- [x] Dashboard page
- [x] Live Map page (clusters, viewport loading, side panel, legend)
- [x] Explorer page (filters, sortable table, map toggle, saved searches, export)
- [x] Event Detail page (overview, revision timeline, products, relationships, provenance)
- [x] Analytics page (charts with accessible table fallbacks)
- [x] Alerts page (rule CRUD with preview, notification feed)
- [x] Research Lab page (snapshots, manifests, downloads)
- [x] Operations and System Status pages
- [x] Accounts pages (sign up, log in, log out) and About Data & Methodology

## L6 Hardening
- [x] Index benchmarks before/after at 500, 10k and 100k records
- [x] Playwright end-to-end tests for the main flows
- [x] Accessibility audit (WCAG 2.2 AA) and fixes
- [x] GitHub Actions CI: lint, types, unit, integration, pip-audit, container build
- [x] Final documentation pass: README, architecture, runbook, rubric mapping
