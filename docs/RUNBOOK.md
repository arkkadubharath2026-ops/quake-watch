# QuakeWatch operations runbook

For whoever runs the local/college-demo deployment (ESD §18: Docker Compose with web, worker, beat,
ArangoDB and Redis). Commands assume the repository root. Use `.venv/Scripts/python` on Windows
and `.venv/bin/python` on Linux/macOS; inside containers it is `docker compose exec web python`.

## 1. Start, stop, upgrade

| Task | Command |
|---|---|
| First start | `cp .env.example .env`, set `QW_SECRET_KEY`, `QW_ARANGO_PASSWORD`, `QW_ARANGO_ROOT_PASSWORD`, then `docker compose up -d --build` |
| Status | `docker compose ps` (web, arangodb and redis report `healthy`) |
| Logs | `docker compose logs -f web worker beat` (structured; every request has a `correlation_id`) |
| Stop / start | `docker compose stop` / `docker compose start` (volumes keep data) |
| Upgrade | `git pull`, then `APP_VERSION=$(git rev-parse --short HEAD) docker compose up -d --build`. The web entrypoint runs `migrate` and `arango_migrate` before serving, and both are idempotent |
| Staff account | `docker compose exec web python manage.py createsuperuser` (unlocks `/operations/`) |

web, worker and beat run the same image, so they can never run different code versions.

## 2. Health and freshness

| Signal | Where | Meaning |
|---|---|---|
| Liveness | `GET /health/live` | the process is up |
| Readiness | `GET /health/ready` | ArangoDB reachable with the expected schema version, and Redis reachable. Returns 503 otherwise |
| Data freshness | nav badge, `/status/`, `GET /api/v1/system/freshness` | **fresh**: a successful sync within `QW_FRESHNESS_DEGRADED_MINUTES` (20). **degraded**: past that. **stale**: none within `QW_FRESHNESS_STALE_MINUTES` (120) |
| USGS circuit breaker | `/status/`, `/operations/` | opens after `QW_CIRCUIT_FAILURE_THRESHOLD` consecutive upstream failures. Syncs are skipped until `QW_CIRCUIT_RESET_SECONDS` pass, then one probe is allowed |

Beat runs `ingestion.sync_feed` every `QW_SYNC_INTERVAL_SECONDS` (300 s; stale ticks expire and
never pile up) and `ingestion.recover` every 10 minutes. The recovery task:
- marks runs stuck for more than 1 h as abandoned;
- re-queues stalled backfill jobs from their checkpoint.

## 3. Common incidents

| Symptom | Check | Action |
|---|---|---|
| Freshness **degraded/stale** | `/operations/`: latest runs and their error. `docker compose logs worker beat` | If beat is down: `docker compose restart beat`. If the breaker is open, USGS is failing: wait for the probe, or press **Sync the live feed now** on `/operations/` (audited) once the upstream is back |
| `/health/ready` 503, database down | `docker compose ps arangodb`, `docker compose logs arangodb` | Restart ArangoDB. Pages show a 503 page and API callers get `database_unavailable`; no data is lost because ingestion is transactional |
| `/health/ready` 503, schema version | log line `arango_schema_applied` missing | `docker compose exec web python manage.py arango_migrate` |
| Records in **dead letters** | `/operations/` Dead letters panel (reason, detail, retry count) | Fix the cause (usually an upstream payload that fails validation), then **Retry** the record. Every retry is written to the audit log |
| Gap in history (outage, first install) | `/operations/` backfill jobs | Start a bounded backfill (next section). It is checkpointed and safe to repeat |
| An event looks outdated | Event Detail → Provenance | **Refresh from USGS** (staff) or `manage.py enrich_event <event_key>` |
| Many 429 responses | API logs with `outcome=throttled` | Expected under abuse: DRF throttles (anon 120/min, user 600/min, stricter scopes for exports and snapshots) in `config/settings.py`. Login attempts are throttled per username+IP (`apps/accounts/security.py`) |
| Slow pages | `aql_slow` warnings in the logs (≥ 250 ms), `/operations/` diagnostics | Run `manage.py aql_catalog` and check that every query still uses its expected index; compare with `docs/BENCHMARKS.md` |

## 4. Data tasks

| Task | Command |
|---|---|
| One feed sync now | `manage.py sync_feed [--feed all_day]` |
| Historical backfill | `manage.py backfill --start 2026-08-26 --end 2026-09-25 --min-magnitude 2.5 [--window-days 7] [--enqueue]` |
| Resume a backfill | `manage.py backfill --resume <job_id>` |
| Enrich one event | `manage.py enrich_event <event_key>` |
| Schema reconcile | `manage.py arango_migrate` (creates missing collections and indexes, replaces drifted ones, drops undeclared `qw_*` indexes) |
| Query plans | `manage.py aql_catalog [--write]` (EXPLAIN every named query; `--write` regenerates `docs/AQL_QUERIES.md`) |
| Index benchmark | `manage.py arango_benchmark --sizes 500,10000,100000 --write`. It runs on a separate, disposable `*_bench_test` database and never touches application data |

Raw USGS payloads expire through the TTL index after `QW_RAW_PAYLOAD_RETENTION_DAYS` (ADR-007).
Canonical events, revisions and research snapshots are kept.

## 5. Backup and restore

ArangoDB holds all domain data; SQLite (`auth_data` volume) holds only accounts and sessions (ADR-009).

```bash
# Backup (consistent dump of the application database)
docker compose exec arangodb sh -c 'arangodump --server.password "$ARANGO_ROOT_PASSWORD" \
  --server.database quakewatch --output-directory /tmp/qw-dump --overwrite true'
docker compose cp arangodb:/tmp/qw-dump ./backups/qw-$(date +%F)
docker compose cp web:/data/auth/auth.sqlite3 ./backups/auth-$(date +%F).sqlite3

# Restore (stop writers first)
docker compose stop worker beat
docker compose cp ./backups/qw-YYYY-MM-DD arangodb:/tmp/qw-dump
docker compose exec arangodb sh -c 'arangorestore --server.password "$ARANGO_ROOT_PASSWORD" \
  --server.database quakewatch --input-directory /tmp/qw-dump --create-database true'
docker compose exec web python manage.py arango_migrate
docker compose start worker beat
```

Keep backups out of the repository (`backups/` is git-ignored; never commit dumps). After a
restore, research snapshots still verify, because each manifest's SHA-256 covers the pinned revisions.

## 6. Secrets and access

- Secrets live only in `.env` (git-ignored) or the host's secret store. Never put them in images,
  logs or the repository.
- **Rotating `QW_SECRET_KEY`** logs every user out. Rotating the ArangoDB password means changing
  it in ArangoDB (`_system`) and in `.env`, then running `docker compose up -d`.
- Staff actions (sync now, backfill, dead-letter retry, event refresh) are recorded in the
  append-only audit log shown on `/operations/`.

## 7. Release checklist

1. CI green (`.github/workflows/ci.yml`: lint → unit → integration → e2e/a11y → dependency audit
   and deploy checks → container build).
2. `docs/PROGRESS.md` ticked; the dashboard is `python scripts/dashboard.py`.
3. `manage.py aql_catalog` reports every query `ok`; if schema or queries changed, re-run the
   benchmark with `--write`.
4. Tag the commit; deploy with `APP_VERSION` set to it (shown in every page footer).
