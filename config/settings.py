"""Django settings for QuakeWatch.

Values come from :mod:`config.env` (typed, validated). ArangoDB is the only database: domain
data, users and sessions (ADR-015), the job queue, cache, metrics and leases. There is no ORM
database (``DATABASES`` is empty, so any accidental ORM query fails loudly).
"""

from __future__ import annotations

from django.utils.csp import CSP

from config.env import BASE_DIR, Environment, get_settings
from config.logging import build_logging_config

APP = get_settings()

SECRET_KEY = APP.secret_key.get_secret_value()
DEBUG = APP.debug
ALLOWED_HOSTS = APP.allowed_hosts
CSRF_TRUSTED_ORIGINS = APP.csrf_trusted_origins
IS_PRODUCTION = APP.env is Environment.PRODUCTION
IS_TEST = APP.env is Environment.TEST

INSTALLED_APPS = [
    # First, so its `createsuperuser` (ArangoDB accounts) overrides django.contrib.auth's ORM one.
    "apps.accounts",
    # auth: hashers, login()/logout(), forms, views, signals; contenttypes: required by auth's
    # (unused) model classes. Neither touches a database here.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.geo",
    "apps.earthquakes",
    "apps.ingestion",
    "apps.alerts",
    "apps.analytics",
    "apps.research",
    "apps.operations",
    "apps.jobs",
    "apps.web",
]

MIDDLEWARE = [
    "apps.core.middleware.CorrelationIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestTimingMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

# --- Databases -----------------------------------------------------------------------------
# None: all persistence is ArangoDB (apps.core.arango). Django's dummy backend raises on any ORM
# query, which tests/architecture also guards against statically.
DATABASES: dict[str, dict[str, object]] = {}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        # ArangoDB-backed (apps.core.arango.cache): document API reads/writes, atomic add/incr.
        "BACKEND": "apps.core.arango.cache.ArangoCache",
        "LOCATION": "",
        "KEY_PREFIX": "qw-test" if IS_TEST else "qw",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "apps.accounts.sessions"  # ArangoDB `sessions` collection (ADR-015)

# --- Auth ----------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.ThrottledModelBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "pages:dashboard"
LOGOUT_REDIRECT_URL = "pages:dashboard"

# --- I18N / time ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static --------------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

# --- Security ------------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REDIRECT_EXEMPT = [r"^health/"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# All JS/CSS is vendored under static/; map tiles are the only third-party origin.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:", "https://*.tile.openstreetmap.org"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}

# --- REST framework ------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + ([] if IS_PRODUCTION else ["rest_framework.renderers.BrowsableAPIRenderer"]),
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "apps.core.api.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        # anon + user rates in one atomic ArangoDB statement per request (apps.core.throttling)
        "apps.core.throttling.DefaultRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "expensive": "20/min",
        "export": "10/hour",
        "snapshot_create": "10/hour",
        "admin_action": "30/hour",
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    # Client identity for throttles: never trust X-Forwarded-For beyond our own proxies.
    "NUM_PROXIES": APP.num_proxies,
    # JSON-only API: free the ``format`` query parameter for our own use (research exports).
    "URL_FORMAT_OVERRIDE": None,
}

# --- Background jobs (apps.jobs: ArangoDB queue, worker, scheduler) ------------------------
# Periodic entries: one job per interval tick however many schedulers run; ``expires`` drops a
# tick that waited too long in the queue (never piles up).
JOBS_EAGER = False
JOBS_SCHEDULE = {
    "sync-usgs-feed": {
        "task": "ingestion.sync_feed",
        "interval": APP.sync_interval_seconds,
        "expires": APP.sync_interval_seconds,
    },
    "ingestion-recovery": {"task": "ingestion.recover", "interval": 600, "expires": 600},
}

# Observers participating in the ingestion transaction (dotted paths; see apps.ingestion.observers)
QUAKEWATCH_EVENT_OBSERVERS: list[str] = ["apps.alerts.observer.AlertRuleObserver"]

# --- Logging -------------------------------------------------------------------------------
LOGGING = build_logging_config(level=APP.log_level, json_output=APP.log_json)

QUAKEWATCH = APP
