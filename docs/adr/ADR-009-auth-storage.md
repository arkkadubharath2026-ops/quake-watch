# ADR-009: Django auth and sessions on SQLite; domain data in ArangoDB

- **Status:** Superseded by ADR-015 (2026-10-07). Accepted 2026-09-25 (decided by project owner).

## Context
PRD requires Django authentication, CSRF and secure cookies. Django's auth, session and admin
frameworks require a relational ORM backend; there is no maintained ArangoDB backend for the
Django ORM. ESD states ArangoDB is the primary database and Redis is support-only.

Options considered: (1) SQLite for auth only, (2) PostgreSQL for auth only, (3) a custom ArangoDB
user store with hand-written auth backend and session engine.

## Decision
Option 1. Django's built-in `auth`, `sessions` (`cached_db` engine), `admin` and `contenttypes`
tables live in a small SQLite file (`QW_AUTH_DB_PATH`, volume-mounted in Docker). **All domain data**
— events, revisions, rules, matches, saved searches, snapshots, runs, audit log — lives in ArangoDB.

User-owned ArangoDB documents reference the Django user by integer `user_id`. For the graph
(`user_owns_rule`), a minimal `users` vertex collection mirrors `{_key: str(user_id), username}` and
is upserted when a user first creates a rule/search; it contains no credentials.

## Consequences
- Security-critical code (password hashing, session handling, CSRF) stays in Django's audited
  implementation.
- Two stores to back up; the SQLite file is small and only holds accounts.
- Authorization checks for ArangoDB documents compare `user_id` server-side in repositories.
