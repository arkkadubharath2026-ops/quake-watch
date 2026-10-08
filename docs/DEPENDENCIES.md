# Dependencies and why each exists

Every dependency must solve a concrete problem. Versions are pinned to compatible ranges in
`requirements*.txt`.

## Runtime (Python)
| Package | Problem it solves | Alternatives rejected |
|---|---|---|
| Django 6.0 | Web framework, auth, CSRF, sessions, admin; **native CSP middleware** (no django-csp) | Django 5.2 LTS would need django-csp |
| djangorestframework | Versioned JSON API, serializer validation, throttling scopes | hand-written JSON views |
| python-arango | Official-quality ArangoDB driver: AQL, stream transactions, index/view/graph management | raw HTTP |
| httpx | Upstream HTTP with separate connect/read timeouts; transport injectable in tests (`httpx.MockTransport`) | requests (banned by lint rule) |
| pydantic | Strict validation of USGS payloads and domain DTOs (`CanonicalEventInput`) | ad-hoc dict checks |
| pydantic-settings | Typed, validated env configuration with production guards | django-environ |
| structlog | Structured logs with contextvar correlation IDs | stdlib only |
| gunicorn | Production WSGI server | runserver |
| whitenoise | Serve hashed, compressed static files from the app container | extra nginx container |

## Development / test
| Package | Purpose |
|---|---|
| pytest, pytest-django, pytest-cov | Test runner, Django integration, coverage |
| freezegun | Deterministic time for cooldown / freshness tests |
| playwright, pytest-playwright | Browser end-to-end tests (browser binary: `python -m playwright install chromium`, not a Python dependency) |
| axe-playwright-python | Bundles axe-core (4.12, WCAG 2.2 AA rules) and injects it through Playwright for the automated accessibility audit (`tests/e2e/test_accessibility.py`); dev/test only, never served to users |
| ruff | Lint + format (also run by the Claude PostToolUse hook) |
| mypy, django-stubs, djangorestframework-stubs | Strict static typing, including the DRF API boundary |
| pip-audit | Dependency vulnerability scan (CI) |

## Frontend (vendored under `static/vendor`, no build step, no CDN at runtime)
Pinned and hash-locked in `static/vendor/VENDOR_LOCK.json` by `scripts/vendor_assets.py`.

| Library | Version | Problem it solves | Alternatives rejected |
|---|---|---|---|
| Bootstrap | 5.3.8 | Accessible component primitives (modals, toasts, tabs, forms, tables), grid, native dark mode | Tailwind (needs a build step), component frameworks (no SPA needed) |
| Bootstrap Icons | 1.13.1 | Icon set matching Bootstrap (woff2 only) | Font Awesome (heavier) |
| Leaflet | 1.9.4 | Interactive map (ESD stack) | Mapbox GL (token, WebGL weight) |
| Leaflet.markercluster | 1.5.3 | Client-side marker clustering (FR-07) complementing server-side grid clusters | custom clustering |
| Chart.js | 4.5.1 | Charts (ESD stack): time series, histograms, scatter | D3 (lower-level, more code) |

Deliberately not added: jQuery, DataTables (server-side pagination + plain accessible tables
suffice), date-picker libraries (native `<input type="date">`).

## Removed (2026-10-07, ADR-014 / ADR-015)

| Package | Was used for | Replaced by |
|---|---|---|
| celery[redis] (+ kombu, billiard, vine, amqp) | background jobs, beat schedule | `apps.jobs` (ArangoDB queue, worker, scheduler) |
| redis | Celery broker, Django cache, throttles, login counters, metrics, breaker state, job locks | ArangoDB collections (`cache_entries`, `metric_*`, `circuit_breakers`, `job_leases`, `jobs`) |
| SQLite (stdlib, Django ORM backend) | accounts and sessions | `auth_users`, `sessions` (`apps.accounts`); stdlib `sqlite3` is now used only read-only by `migrate_auth_to_arango` |
