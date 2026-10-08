# ADR-015: Accounts and sessions in ArangoDB (no relational database)

- **Status:** Accepted — approved by the project owner 2026-10-08, including replacing the Django
  admin user pages with management commands (owner directive: "eliminate relational DB persistence"; "Do not delete the
  old database until the ArangoDB data is verified")
- **Date:** 2026-10-07
- **Supersedes:** ADR-009 (Django auth and sessions on SQLite)

## Context
ADR-009 kept Django's `auth_user`, sessions and admin in SQLite because there is no maintained
ArangoDB backend for the Django ORM. The owner now requires ArangoDB to be the only database.
Rejected alternative: a third-party Django ORM backend for ArangoDB (none maintained; would put an
unaudited translation layer under security-critical code).

## Decision
Keep Django's security machinery and replace only the storage underneath it:

- **Accounts:** `auth_users` collection (`_key` = the integer user id, unique `username`), managed by
  `apps/accounts/repository.py`. `ArangoUser` (`apps/accounts/identity.py`) implements what
  `django.contrib.auth` needs: `login()`/`get_user()`, Django's own password hashing (`make_password`
  / `check_password` with transparent hash upgrades) and the *identical* session-auth-hash recipe,
  so a password change still logs out other sessions. New ids come from `id_sequences` in the same
  statement as the insert.
- **Sessions:** `SESSION_ENGINE = "apps.accounts.sessions"` mirrors Django's `db` backend on the
  `sessions` collection (Django's signed encoding; create = insert-or-CreateError; save = update-
  or-UpdateError; TTL index GC).
- **Authentication:** `apps.accounts.backends.ThrottledModelBackend` (historical name kept so
  pre-migration sessions validate) keeps the brute-force throttle before password verification and
  equalises timing for unknown usernames.
- **No ORM:** `DATABASES = {}`; `django.contrib.admin` and `django.contrib.sessions` removed;
  `django.contrib.auth`/`contenttypes` stay installed for hashers, views, forms and signals only.
- **Administration:** the Django admin's user pages are replaced by `manage.py createsuperuser`
  (same name/conventions) and `manage.py users list|set-staff|set-active|set-password|delete`,
  all audited.
- **Migration:** `manage.py migrate_auth_to_arango --sqlite PATH` opens the old file read-only,
  keeps ids/usernames/hashes/flags/timestamps (and names), copies unexpired sessions, refuses
  identity conflicts, is idempotent and verifies every user. The SQLite volume stays mounted
  read-only until the owner retires it.

## Consequences
- One database; user ids and every `user_id` reference are unchanged.
- Groups and per-object permissions are not supported (never used: authorisation is `is_staff` and
  ownership checks); the migration reports any such rows instead of dropping them silently.
- The Django admin UI is gone (it required the ORM); account administration is CLI-only.
- Account deletion is one ArangoDB transaction covering the account and all user-owned data.

## Deployment order (owner decision 2026-10-08)
1. Deploy the new release, **web first** (its entrypoint runs `arango_migrate`, creating `auth_users`,
   `sessions`, `jobs` …), then worker and scheduler.
2. **Account migration second:** `manage.py migrate_auth_to_arango --sqlite <old file> --dry-run`, then
   without `--dry-run`; it must report `"verified": true`; then sign in with a real account.
3. **Retire the old SQLite volume last**, only after step 2 is verified and a copy of the file is
   stored as a backup. Until then it stays mounted read-only (`docker-compose.yml`).

## Relation to ESD / PRD
PRD security requirements (Django authentication, CSRF, secure cookies, lockout) are unchanged and
still implemented by Django's own code; only the storage moved. ESD's mention of SQLite/ADR-009 is
superseded by this ADR; no new persistence technology was introduced.

## Retained references to SQLite
The only remaining SQLite code is the read-only migration command; the `auth_data` volume stays mounted
read-only and `/data/auth` stays in the Dockerfile until the retirement criteria are met (see
`RUNBOOK.md`, "Migrating accounts from the pre-ADR-015 SQLite file"). Other mentions are historical; see
ADR-014, "Intentionally retained historical wording".

