"""Test settings: forces QW_ENV=test so ArangoDB uses the isolated ``<db>_test`` database."""

import os

os.environ["QW_ENV"] = "test"
os.environ.setdefault("QW_DEBUG", "false")

from config.env import get_settings

get_settings.cache_clear()

from config.settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only; tests
JOBS_EAGER = True  # .delay() runs inline (apps.jobs.registry); worker tests use the queue
