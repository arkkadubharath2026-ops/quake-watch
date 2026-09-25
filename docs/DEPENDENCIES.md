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
| celery[redis] | Scheduled sync, backfill, alert evaluation with retries/time limits (ESD §3) | cron + scripts |
| redis | Celery broker, cache, throttle counters, metrics, circuit-breaker state | — |
| gunicorn | Production WSGI server | runserver |
| whitenoise | Serve hashed, compressed static files from the app container | extra nginx container |

## Development / test
| Package | Purpose |
|---|---|
| pytest, pytest-django, pytest-cov | Test runner, Django integration, coverage |
| freezegun | Deterministic time for cooldown / freshness tests |
| playwright, pytest-playwright | Browser end-to-end tests |
| ruff | Lint + format (also run by the Claude PostToolUse hook) |
| mypy, django-stubs | Strict static typing |
| pip-audit | Dependency vulnerability scan (CI) |

## Frontend (vendored under `static/vendor`, no build step, no CDN at runtime)
Recorded when added in the UI layer.
