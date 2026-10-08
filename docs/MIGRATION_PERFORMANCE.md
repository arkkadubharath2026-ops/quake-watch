# Performance of the ArangoDB-only migration (ADR-014 / ADR-015)

Measured 2026-10-08 in the isolated `qwb` sandbox (WSL2 Ubuntu 24.04, Docker 29.1.3,
ArangoDB 3.12.5 capped at 900 MB, Python 3.12, host with ~0.6-0.9 GB free RAM). Historical numbers
in [BENCHMARKS.md](BENCHMARKS.md) are kept unchanged (generated file, different machine).

## 1. Query level — `manage.py arango_benchmark` (unchanged by the migration)

Scanned document counts (full/index) are **identical to BENCHMARKS.md in every cell** at 500, 10k and
100k events: the migration changed no query plan or index. Indexed latency, p50 / p95 ms:

| Workload | 500 | 10,000 | 100,000 |
|---|---|---|---|
| event_list_filtered | 3.16 / 4.88 | 3.08 / 5.37 | 3.52 / 5.18 |
| event_list_latest | 2.59 / 3.14 | 4.87 / 7.16 | 21.89 / 23.07 |
| geo_radius | 2.69 / 3.93 | 5.02 / 7.06 | 21.79 / 97.09 |
| analytics_magnitude_histogram | 2.19 / 2.66 | 8.66 / 11.24 | 4.48 / 5.88 |
| revision_lookup | 1.48 / 1.99 | 2.65 / 3.68 | 1.87 / 2.91 |

Slowest indexed p95: 97.1 ms (geo_radius, 100k; one run of 20 — the Phase 0 run in the same sandbox
measured 53.97 ms, while p50 is lower now: 21.8 vs 25.7 ms). PRD target p95 < 500 ms: met everywhere.

## 2. Request level — A/B, same session, 10k events

Full Django + DRF stack in process (`perf_compare.py`, production settings, real throttles and
sessions; 150 timed requests after 10 warm-ups). S4 = pre-migration code (Redis cache/throttles/
session cache/metrics, SQLite accounts, Celery broker); S5 = ArangoDB only. p50 ms:

| Case | S4 | S5 run 1 | S5 run 2 | Change |
|---|--:|--:|--:|---|
| events default list (anonymous) | 9.97 | 9.46 | 7.97 | parity / faster |
| events filtered (anonymous) | 6.57 | 7.23 | 6.30 | within noise |
| geo radius (anonymous) | 7.33 | 7.83 | 8.45 | +7 % / +15 % |
| event revisions (anonymous) | 6.11 | 8.46 | 6.31 | +39 % / +3 % (noisy) |
| analytics distributions (anonymous) | 5.02 | 7.93 | 8.47 | **+3 ms (+58-69 %)** |
| saved searches (signed in) | 4.37 | 7.23 | 8.87 | **+3-4.5 ms (+65-100 %)** |
| unread count (signed in) | 4.83 | 7.19 | 7.54 | **+2.5 ms (+49-56 %)** |
| login (PBKDF2-bound) | 241.9 | 237.6 | 234.4 | parity |
| `metrics.observe` per call | 0.105 | 0.001 | 0.001 | ~100x faster (buffered) |
| cache get / incr | 0.16 / 0.24 | 0.92 / 1.43 | 0.94 / 1.45 | slower per key |
| job enqueue | 0.56 | 1.63 | 1.59 | +1 ms |

Job queue (S5, trivial jobs, fork per job): enqueue 423-823 jobs/s; drain 57 / 76 / 73 jobs/s at
concurrency 1 / 2 / 4; 200/200 succeeded in each run.

## 3. What the numbers mean

* **Anonymous public reads are at parity.** The first all-AQL cache made them 50-100 % slower
  (four cache round trips per request through DRF's two default throttles, ~1.3 ms each). Fixes:
  single-key cache operations on the document API, and one atomic AQL statement for all rate-limit
  checks of a request (`apps/core/throttling.py`), which also removes DRF's get/set race.
* **Signed-in requests and cached analytics remain ~2.5-4.5 ms slower.** Cause, measured: an ArangoDB
  key operation costs ~0.9 ms vs ~0.16 ms for Redis; a signed-in request needs the session, the user
  (Django's session-hash check) and its rate-limit window. This is inherent to keeping that state in
  ArangoDB instead of Redis/SQLite; absolute latency stays far below the PRD target (p95 < 500 ms).
  Options that would close more of the gap change semantics and need an owner decision: a
  short-lived per-process user cache (delays deactivation/password changes by its TTL), or a user
  snapshot embedded in the session with server-side invalidation on every user change.
* Background work is unaffected in practice: ingestion jobs run for seconds to minutes; queue
  overhead (claim + fork + outcome ≈ 13-17 ms per job) and up to 1 s polling latency are negligible.
