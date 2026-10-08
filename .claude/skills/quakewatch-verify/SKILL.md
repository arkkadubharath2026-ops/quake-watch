---
name: quakewatch-verify
description: Milestone verification gate for QuakeWatch. Use after finishing any layer/feature and before committing or claiming work is done. Runs lint, types, unit/contract/integration tests against real ArangoDB, boundary checks, security checks, and refreshes the Graphify graph.
---

# QuakeWatch verification gate

Run from the repository root. All commands use the project venv. Stop and fix at the first failing phase.

## 0. Infrastructure up
```bash
docker compose ps arangodb              # must be healthy (the only stateful service)
```
If not: `docker compose up -d arangodb`.

## 1. Lint + format
```bash
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m ruff check .
```

## 2. Types
```bash
.venv/Scripts/python -m mypy apps config
```

## 3. Django system checks (incl. deploy checks with production settings)
```bash
.venv/Scripts/python manage.py check
QW_ENV=production QW_DEBUG=false .venv/Scripts/python manage.py check --deploy --fail-level WARNING
```

## 4. Tests (real ArangoDB — integration tests use an isolated `<db>_test` database)
```bash
.venv/Scripts/python -m pytest -m "not e2e and not perf" --cov=apps --cov-report=term-missing:skip-covered
```
Unit, contract (recorded USGS fixtures), resilience and integration suites all run here.
E2E (`-m e2e`) needs a running server + `playwright install chromium`; run it at UI milestones.

## 5. Architectural boundaries
```bash
.venv/Scripts/python -m pytest tests/architecture -q
```
Enforces: domain/service modules import no Django HTTP/DRF; only `repository.py` / `apps/core/arango` touch python-arango; only `apps/ingestion/adapters` touch httpx.

## 6. Security
```bash
.venv/Scripts/python -m pip_audit -r requirements.txt
```
Then consider delegating to the `security-reviewer` agent for changes touching auth, input handling, exports or admin actions, and to `arangodb-reviewer` for AQL/schema/transaction changes.

## 7. Graph refresh + impact check
```bash
graphify update .
graphify query "what depends on <changed module>"
```

## 8. Docs
Update README.md, docs/ARCHITECTURE.md, docs/AQL_QUERIES.md and add/adjust an ADR in docs/adr/ when a decision changed. Then commit.

Report results honestly: list each phase as pass/fail with the relevant output; never claim a phase passed that was skipped.
