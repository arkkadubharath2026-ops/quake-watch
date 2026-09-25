# ADR-004: Polling and freshness strategy

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
USGS summary feeds regenerate about every minute; the catalog API serves history. The product must
degrade gracefully when USGS is unavailable (PRD principle 8) and make data trust visible (P6).

## Decision
- Celery beat enqueues `ingestion.sync_feed` every `QW_SYNC_INTERVAL_SECONDS` (default 300 s) for
  `QW_SYNC_FEED` (default `all_day`). Using the *day* feed on a 5-minute cadence tolerates missed
  ticks and worker restarts of up to ~24 h without gaps; longer outages are repaired with a bounded
  catalog backfill. Ticks expire after one interval so a backlog never piles up.
- A Redis lock prevents overlapping syncs of the same feed.
- HTTP: 5 s connect / 20 s read timeouts, up to 4 retries with full-jitter exponential backoff on
  timeouts, transport errors, 429 (honouring Retry-After) and 5xx only.
- A Redis-backed circuit breaker opens after 5 consecutive failed calls for 300 s; while open,
  syncs are recorded as `skipped` without calling USGS, and stored data continues to be served.
- Freshness is derived from the latest *successful* `feed_sync` run: **fresh** within
  `QW_FRESHNESS_DEGRADED_MINUTES` (20), **degraded** until `QW_FRESHNESS_STALE_MINUTES` (120),
  **stale** afterwards; the circuit state and the feed's own `generated` timestamp are reported
  alongside. The UI shows this indicator on every data page.

## Consequences
- Worst-case latency from USGS publication to QuakeWatch is one interval (+ fetch time).
- `recover` (every 10 min) marks runs left `running` by dead workers as `abandoned` and resumes
  stalled/idle backfill jobs.
