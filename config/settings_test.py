"""Test settings: forces QW_ENV=test so ArangoDB uses the isolated ``<db>_test`` database."""

import os
from pathlib import Path

os.environ["QW_ENV"] = "test"
os.environ.setdefault("QW_DEBUG", "false")
os.environ["QW_AUTH_DB_PATH"] = str(
    Path(__file__).resolve().parent.parent / "var" / "test-auth.sqlite3"
)

from config.env import get_settings

get_settings.cache_clear()

from config.settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only; tests
CELERY_TASK_ALWAYS_EAGER = True

# File-backed test database for the auth store. With Django's default in-memory SQLite test DB the
# live server (browser tests) shares ONE connection across its request threads; the browser's
# parallel API calls then collide on it (sqlite3.InterfaceError, cross-talk between cursors).
# A file gives every thread its own connection, as gunicorn workers have in production.
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": str(Path(__file__).resolve().parent.parent / "var" / "test-auth-db.sqlite3")
}
