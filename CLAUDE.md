# QuakeWatch — instructions for Claude

Source of truth: `docs/PRD.md` (product), `docs/ESD.md` (engineering), `README.md` (overview).
Do not silently alter PRD/ESD requirements — surface genuine conflicts to the user first and record the
resolution as an ADR in `docs/adr/`.

## Standing instructions from the project owner (always follow)

1. **Use Graphify for codebase context.** Before broad file reading, query the graph
   (`graphify query "<question>"`, `graphify explain "<Symbol>"`, `graphify path "A" "B"`) and read
   `graphify-out/GRAPH_REPORT.md`. After code changes run `graphify update .` (the git post-commit hook
   also rebuilds it). Graph context assists reasoning; still read critical implementation code directly.
2. **Build layer by layer**: Understand → Design → Implement → Test → Fix → Validate → Integrate →
   Commit → Continue. Do not jump between unrelated features or rush UI while backend foundations are incomplete.
3. **After every major milestone**: run tests, lint/type checks, architecture-boundary tests, security
   review, edge cases, frontend↔backend integration check, remove dead code, update docs, record ADRs —
   use the `quakewatch-verify` skill. Only then continue.
4. **No fake implementations**, placeholder production logic, excessive TODOs, or mocked paths presented
   as finished. Never claim something works because it compiles or mocked tests pass — verify real behaviour
   (real ArangoDB, real HTTP where appropriate).
5. **Every dependency must solve a concrete problem**; record it in `docs/DEPENDENCIES.md`.
6. **Keep README.md and docs/ (ARCHITECTURE.md, AQL_QUERIES.md, ADRs) current** as the implementation evolves.
7. **End every work report with a status bar** showing per-layer progress, e.g.
   `L1 Foundations ██████████ 100%`.
8. Store new important standing instructions from the owner in this file.

## Architecture (see docs/ARCHITECTURE.md)

Modular Django monolith + Celery worker/beat + ArangoDB (all domain data) + SQLite (Django auth/sessions
only, ADR-009) + Redis (broker/cache only).

```
config/            settings (typed env via pydantic-settings), urls, celery app
apps/core/         shared kernel: arango/ (client, schema, migrations, transactions), logging,
                   errors, middleware (correlation id, timing), pagination, clock
apps/geo/          geodesic math, bbox/radius validation, region normalisation (pure)
apps/earthquakes/  event domain, EventRepository (AQL), query service, API + pages
apps/ingestion/    adapters/ (USGS summary/catalog/detail, httpx only here), normalizer,
                   revision_policy + differ, pipeline (transactional upsert), resilience, tasks
apps/alerts/       rule domain + matcher (pure), repository, API, evaluation tasks
apps/analytics/    aggregate AQL + API
apps/research/     snapshots, manifests, checksums, exports
apps/operations/   health/freshness, ingestion dashboard, audit log, admin actions
apps/accounts/     Django auth (ORM, SQLite)
```

### Boundary rules (enforced by tests/architecture)
- `domain.py` / `services.py` / pure modules import no Django HTTP, DRF, httpx, or python-arango.
- Only `repository.py` files and `apps/core/arango/` import `arango`.
- Only `apps/ingestion/adapters/` imports `httpx`.
- AQL always uses bind variables; sort fields come from allow-lists.
- Source values are never overwritten by derived values.

## Commands

```bash
docker compose up -d arangodb redis                 # infra for dev/tests
.venv/Scripts/python manage.py arango_migrate       # idempotent collections/indexes/views/graph
.venv/Scripts/python manage.py runserver
.venv/Scripts/python -m pytest -m "not e2e and not perf"
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m mypy apps config
```

## Project tooling (.claude/)
- Agents: `arangodb-reviewer` (project-specific), `python-reviewer`, `django-reviewer` (ORM advice
  applies only to `apps/accounts`), `security-reviewer`, `silent-failure-hunter`, `a11y-architect` (ECC).
- Skills: `quakewatch-verify` (milestone gate), `architecture-decision-records`, `django-security`,
  `django-celery`, `frontend-a11y` (ECC).
- Hooks: ruff format/fix on every edited .py file; writes to `.env`/key files are blocked.

## Safety wording
QuakeWatch never claims to predict earthquakes; alerts are application notifications, not official
emergency warnings. Credit: "Earthquake data courtesy of the U.S. Geological Survey (USGS)."

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
