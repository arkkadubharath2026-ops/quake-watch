# Security Review Log

## 2026-09-25 — L4 user features (alerts, saved searches, research, operations, accounts)

Independent review (agent following `.claude/agents/security-reviewer.md`). No critical findings.
All findings fixed; each has a regression test in
`tests/integration/test_user_features.py::TestSecurityReviewFixes`.

| # | Severity | Finding | Fix |
|---|---|---|---|
| M1 | Medium | DRF throttles and login lockout keyed on spoofable `X-Forwarded-For` (first hop) | `QW_NUM_PROXIES` → DRF `NUM_PROXIES`; `client_ip` uses the proxy-appended right-most hop, else `REMOTE_ADDR` |
| M2 | Medium | Lockout: anyone could lock any account; no per-address cap (spraying); check-then-count race | Atomic count-before-verify (Redis INCR); per-address cap across usernames; per-username cap skipped for addresses the user recently logged in from |
| L1 | Low | Unlimited research snapshots per user | 20 per user (serialised cap) + `snapshot_create` throttle 10/hour |
| L2 | Low | Admin actions audited only after success; failures/denials unaudited; raw request stored | `requested` entry before acting, `ok`/`failed` after; `operations.permission_denied` audited; only validated fields stored |
| L3 | Low | 5xx envelope exposed driver text (host, database) | Clients get a fixed `public_message`; details logged only |
| L4 | Low | Per-user caps bypassable by concurrent requests | Count-then-insert under an exclusive collection lock (`exclusive_query`) |
| L5 | Low | User deletion left ArangoDB data behind | `post_delete` signal deletes rules, edges, matches, searches, snapshots, user vertex atomically |

Verified safe by the reviewer: object-level authorization on every user-owned object (404, no
existence leak), AQL injection (bind variables only), mass assignment (`extra="forbid"`,
server-set ownership), staff-only operations, CSRF on all unsafe methods, request size limits,
pagination bounds, Content-Disposition, no unsafe deserialisation, append-only audit, CSP/HSTS/cookies.
