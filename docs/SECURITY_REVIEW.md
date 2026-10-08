# Security Review Log

## 2026-09-25 — L4 user features (alerts, saved searches, research, operations, accounts)

Independent review (agent following `.claude/agents/security-reviewer.md`). No critical findings.
All findings fixed; each has a regression test in
`tests/integration/test_user_features.py::TestSecurityReviewFixes`.

| # | Severity | Finding | Fix |
|---|---|---|---|
| M1 | Medium | DRF throttles and login lockout keyed on spoofable `X-Forwarded-For` (first hop) | `QW_NUM_PROXIES` → DRF `NUM_PROXIES`; `client_ip` uses the proxy-appended right-most hop, else `REMOTE_ADDR` |
| M2 | Medium | Lockout: anyone could lock any account; no per-address cap (spraying); check-then-count race | Atomic count-before-verify (Redis INCR at the time; since ADR-014 an atomic ArangoDB `incr` with the same semantics, re-tested in `test_shared_state.py`); per-address cap across usernames; per-username cap skipped for addresses the user recently logged in from |
| L1 | Low | Unlimited research snapshots per user | 20 per user (serialised cap) + `snapshot_create` throttle 10/hour |
| L2 | Low | Admin actions audited only after success; failures/denials unaudited; raw request stored | `requested` entry before acting, `ok`/`failed` after; `operations.permission_denied` audited; only validated fields stored |
| L3 | Low | 5xx envelope exposed driver text (host, database) | Clients get a fixed `public_message`; details logged only |
| L4 | Low | Per-user caps bypassable by concurrent requests | Count-then-insert under an exclusive collection lock (`exclusive_query`) |
| L5 | Low | User deletion left ArangoDB data behind | `post_delete` signal deletes rules, edges, matches, searches, snapshots, user vertex atomically |

Verified safe by the reviewer: object-level authorization on every user-owned object (404, no
existence leak), AQL injection (bind variables only), mass assignment (`extra="forbid"`,
server-set ownership), staff-only operations, CSRF on all unsafe methods, request size limits,
pagination bounds, Content-Disposition, no unsafe deserialisation, append-only audit, CSP/HSTS/cookies.

## 2026-09-25 — L5 user interface

Self-review during the milestone gate (web pages, browser runtime, templates).

| # | Severity | Finding | Fix |
|---|---|---|---|
| U1 | Medium | Event Detail rendered the upstream `url` property as a link; a tampered USGS payload could plant a `javascript:` link | Links rendered only for `https://` on `usgs.gov` hosts (`safe_usgs_url`); stored source value unchanged; unit tests cover scheme/host bypasses |
| U2 | Low | Research manifests labelled the event document version as `database_schema_version` (reproducibility metadata wrong) | Manifest records `database_schema_version` and `event_document_version` separately; integration test asserts both |

Verified: CSP with nonce on the only inline script (view test checks every inline script on every
page), no `unsafe-inline`; API data inserted with `textContent` only (no `innerHTML`/`eval` in
`static/qw/js`); CSRF header on all unsafe fetches; logout POST-only; off-site `next` rejected
after login (test); protected pages gated server-side (302 to login, 403 for non-staff);
`json_script` for page data; `rel="noopener noreferrer"` on external links.

## 2026-09-25 — L6 hardening (benchmarks, browser tests, CI)

Self-review during the milestone gate (benchmark tooling, test harness, CI workflow, runbook).

| # | Severity | Finding | Fix |
|---|---|---|---|
| H1 | Low (dev only) | `pip-audit` flagged pytest 8.4.2 (PYSEC-2026-1845: predictable `/tmp/pytest-of-{user}` directories allow local DoS or privilege gain on shared UNIX hosts) | Dev requirement raised to `pytest>=9.0.3`; the full suite passes on pytest 9; CI runs `pip-audit` on runtime and dev requirements |
| H2 | Low (test only) | The browser-test conftest set `DJANGO_ALLOW_ASYNC_UNSAFE` at import time. pytest imports it during every collection, so the async-safety guard was off for the whole test process | Session-scoped fixture limited to `tests/e2e`; the previous value is restored afterwards |

Verified:
- **Benchmark tool:** it can only create and drop a database whose name ends in `_test`, guarded
  in both `prepare_database` and `drop_database`, with a test. Application data is never touched,
  and every value is a bind variable.
- **CI workflow:** `permissions: contents: read`; no `pull_request_target`; no repository secrets
  (the service credentials are CI-only values); services bound to the runner only.
- **Container:** the image runs as uid 10001, checked in CI.
- **Deploy check:** `check --deploy --fail-level WARNING` is clean with production settings.
- **Browser tests:** they load no third-party code into the app. Map tiles are answered locally,
  and axe-core is injected only by the test harness.

Accepted risk: third-party GitHub Actions are pinned to major-version tags (`actions/*@v4/v5`,
`docker/*@v3/v6`), not commit SHAs. Pin to SHAs if the repository becomes public or receives
outside pull requests.
