"""Django settings for QuakeWatch.

Values come from :mod:`config.env` (typed, validated). ArangoDB holds all domain data;
the ORM database below stores only Django auth/sessions/admin (ADR-009).
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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
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
    "apps.accounts",
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
# Auth/sessions only (ADR-009). Domain data lives in ArangoDB (apps.core.arango).
APP.auth_db_path.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": APP.auth_db_path,
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": APP.redis_url,
        "KEY_PREFIX": "qw-test" if IS_TEST else "qw",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

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
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "expensive": "20/min",
        "export": "10/hour",
        "admin_action": "30/hour",
    },
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    # JSON-only API: free the ``format`` query parameter for our own use (research exports).
    "URL_FORMAT_OVERRIDE": None,
}

# --- Celery --------------------------------------------------------------------------------
CELERY_BROKER_URL = APP.redis_url
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 15 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 14 * 60
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 20 * 60}
CELERY_TIMEZONE = "UTC"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False  # keep structlog formatting in workers
CELERY_BEAT_SCHEDULE = {
    "sync-usgs-feed": {
        "task": "ingestion.sync_feed",
        "schedule": APP.sync_interval_seconds,
        "options": {"expires": APP.sync_interval_seconds},  # drop stale ticks, never pile up
    },
    "ingestion-recovery": {"task": "ingestion.recover", "schedule": 600},
}

# Observers participating in the ingestion transaction (dotted paths; see apps.ingestion.observers)
QUAKEWATCH_EVENT_OBSERVERS: list[str] = ["apps.alerts.observer.AlertRuleObserver"]

# --- Logging -------------------------------------------------------------------------------
LOGGING = build_logging_config(level=APP.log_level, json_output=APP.log_json)

QUAKEWATCH = APP
