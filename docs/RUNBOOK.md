# QuakeWatch operations runbook

For whoever runs the local/college-demo deployment (Docker Compose with web, worker, scheduler and
ArangoDB — the only stateful service, ADR-014/015). Commands assume the repository root. Use `.venv/Scripts/python` on Windows
and `.venv/bin/python` on Linux/macOS; inside containers it is `docker compose exec web python`.

## 1. Start, stop, upgrade

| Task | Command |
|---|---|
| First start | `cp .env.example .env`, set `QW_SECRET_KEY`, `QW_ARANGO_PASSWORD`, `QW_ARANGO_ROOT_PASSWORD`, then `docker compose up -d --build` |
| Status | `docker compose ps` (web and arangodb report `healthy`) |
| Logs | `docker compose logs -f web worker scheduler` (structured; every request and job has a `correlation_id`) |
| Stop / start | `docker compose stop` / `docker compose start` (volumes keep data) |
| Upgrade | `git pull`, then `APP_VERSION=$(git rev-parse --short HEAD) docker compose up -d --build`. The web entrypoint runs `arango_migrate` before serving (idempotent) |
| Staff account | `docker compose exec web python manage.py createsuperuser` (unlocks `/operations/`) |
| Accounts | `manage.py users list`, `users set-staff NAME --on/--off`, `users set-active NAME --on/--off`, `users set-password NAME`, `users delete NAME --yes` (deletes the account and all its data; audited) |

web, worker and scheduler run the same image, so they can never run different code versions.

## 2. Health and freshness

| Signal | Where | Meaning |
|---|---|---|
| Liveness | `GET /health/live` | the process is up |
| Readiness | `GET /health/ready` | ArangoDB reachable with the expected schema version. Returns 503 otherwise |
| Data freshness | nav badge, `/status/`, `GET /api/v1/system/freshness` | **fresh**: a successful sync within `QW_FRESHNESS_DEGRADED_MINUTES` (20). **degraded**: past that. **stale**: none within `QW_FRESHNESS_STALE_MINUTES` (120) |
| USGS circuit breaker | `/status/`, `/operations/` | opens after `QW_CIRCUIT_FAILURE_THRESHOLD` consecutive upstream failures. Syncs are skipped until `QW_CIRCUIT_RESET_SECONDS` pass, then one probe is allowed |

The scheduler enqueues `ingestion.sync_feed` every `QW_SYNC_INTERVAL_SECONDS` (300 s; stale ticks expire and
never pile up; several schedulers may run, each tick is enqueued once) and `ingestion.recover`
every 10 minutes. The recovery task:
- marks runs stuck for more than 1 h as abandoned;
- re-queues stalled backfill jobs from their checkpoint.

**Job leases.** `sync_feed` and `run_backfill` hold a lease in the ArangoDB collection `job_leases`
(one document per job name, e.g. `sync:all_day`, `backfill:<job_id>`).
Expiry is decided by the ArangoDB server clock; leases outlive the task's hard time limit
(600 s / 1200 s vs 300 s / 900 s) and are removed when the job ends. If the database cannot be
reached, the job is **skipped, never run unlocked** (result `skipped_lock_unavailable`, log
`job_lock_unavailable`); the next scheduled tick or the recovery task retries it. A lease left by a
crashed worker expires on its own; do not delete one by hand unless its `owner` (`host:pid`) is
verifiably gone. Inspect: `FOR l IN job_leases RETURN l` in the ArangoDB web UI.

**Job queue** (`jobs` collection, `apps.jobs`, ADR-014). Workers claim due jobs atomically, run each
in a child process and heartbeat its lease (60 s). A job whose worker died is re-queued by any live
worker once the lease lapses (`jobs_reaped` log) and dead-lettered after 3 lost runs. Statuses:
`queued`, `running`, `succeeded`, `failed` (permanent error), `dead` (retries exhausted),
`expired` (a schedule tick that waited too long). Finished jobs are purged after 7 days.

| Task | Command |
|---|---|
| Queue overview | `manage.py jobs stats` |
| Recent / dead jobs | `manage.py jobs list [--status dead] [--limit 50]` (with the last error) |
| Re-run a dead/failed job | `manage.py jobs requeue <job_id>` |
| Worker | `manage.py run_worker --concurrency 2` (SIGTERM: finishes running jobs within 25 s, then hands the rest back to the queue) |
| Scheduler | `manage.py run_scheduler` (or `run_worker --with-scheduler` for a single process) |

## 3. Common incidents

| Symptom | Check | Action |
|---|---|---|
| Freshness **degraded/stale** | `/operations/`: latest runs and their error. `docker compose logs worker scheduler`, `manage.py jobs stats` | If the scheduler or worker is down: `docker compose restart scheduler worker`. If the breaker is open, USGS is failing: wait for the probe, or press **Sync the live feed now** on `/operations/` (audited) once the upstream is back |
| `/health/ready` 503, database down | `docker compose ps arangodb`, `docker compose logs arangodb` | Restart ArangoDB. Pages show a 503 page and API callers get `database_unavailable`; no data is lost because ingestion is transactional |
| `/health/ready` 503, schema version | log line `arango_schema_applied` missing | `docker compose exec web python manage.py arango_migrate` |
| Records in **dead letters** | `/operations/` Dead letters panel (reason, detail, retry count) | Fix the cause (usually an upstream payload that fails validation), then **Retry** the record. Every retry is written to the audit log |
| Gap in history (outage, first install) | `/operations/` backfill jobs | Start a bounded backfill (next section). It is checkpointed and safe to repeat |
| An event looks outdated | Event Detail → Provenance | **Refresh from USGS** (staff) or `manage.py enrich_event <event_key>` |
| Many 429 responses | API logs with `outcome=throttled` | Expected under abuse: DRF throttles (anon 120/min, user 600/min, stricter scopes for exports and snapshots) in `config/settings.py`. Login attempts are throttled per username+IP (`apps/accounts/security.py`) |
| Slow pages | `aql_slow` warnings in the logs (≥ 250 ms), `/operations/` diagnostics | Run `manage.py aql_catalog` against the **populated** database and check that every query still uses its expected index; compare with `docs/BENCHMARKS.md`. On an empty database the optimizer has no selectivity statistics and may pick another candidate index, so `aql_catalog` can report `BAD` there without a real regression |
| Jobs report `skipped_lock_unavailable` | worker logs `job_lock_unavailable` (attempts, cause) | ArangoDB unreachable or `job_leases` missing: restore the database / run `arango_migrate`. Jobs resume on the next tick; nothing ran unlocked |
| Dead jobs | `manage.py jobs list --status dead` | Read `last_error` / `errors`; fix the cause, then `manage.py jobs requeue <job_id>` |
| Jobs stay `queued` | `manage.py jobs stats`, worker logs `job_claim_failed` | Start/restart the worker; check ArangoDB reachability |

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

ArangoDB holds everything: domain data, accounts and sessions (ADR-015), jobs, cache, metrics and
leases. One dump is a complete backup.

```bash
# Backup (consistent dump of the application database)
docker compose exec arangodb sh -c 'arangodump --server.password "$ARANGO_ROOT_PASSWORD" \
  --server.database quakewatch --output-directory /tmp/qw-dump --overwrite true'
docker compose cp arangodb:/tmp/qw-dump ./backups/qw-$(date +%F)

# Restore (stop writers first)
docker compose stop worker scheduler
docker compose cp ./backups/qw-YYYY-MM-DD arangodb:/tmp/qw-dump
docker compose exec arangodb sh -c 'arangorestore --server.password "$ARANGO_ROOT_PASSWORD" \
  --server.database quakewatch --input-directory /tmp/qw-dump --create-database true'
docker compose exec web python manage.py arango_migrate
docker compose start worker scheduler
```

### Migrating accounts from the pre-ADR-015 SQLite file (once)

The old `auth_data` volume is mounted **read-only** at `/data/auth`. With the new release deployed:

```bash
docker compose exec web python manage.py migrate_auth_to_arango --sqlite /data/auth/auth.sqlite3 --dry-run
docker compose exec web python manage.py migrate_auth_to_arango --sqlite /data/auth/auth.sqlite3
```

The second command keeps user ids, usernames, password hashes and flags, copies unexpired sessions
(signed-in users stay signed in) and must print `"verified": true`. Then sign in with a real account.
Only after that, and after a backup copy of the SQLite file is stored safely, remove the
`auth_data` mount and volume. Re-running the command is safe (idempotent); it refuses to overwrite a
different user with the same id or username.

### Rolling back the ArangoDB-only release (ADR-014/015)
Schema v6 is additive (11 new collections, 10 new indexes; nothing removed), so the previous release can run
against the same database:
1. Pause worker and scheduler. Redeploy the previous revision (revert the migration merge on `main`).
2. Its web entrypoint runs `migrate` and `arango_migrate`, which resets `schema_meta.version` to 2; the new
   collections are left untouched and unused, so `/health/ready` passes again.
3. The previous release needs Redis (`QW_REDIS_URL`) and its SQLite auth file again: **keep the Redis service and
   the `auth_data` volume until the new release is accepted** (ADR-015 retirement criteria).
4. Accounts created or changed after the switch exist only in `auth_users`; they are not written back to SQLite.

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
