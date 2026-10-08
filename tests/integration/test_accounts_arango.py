"""Accounts and sessions in ArangoDB (ADR-015): identity, authentication, session lifecycle,
authorization, administration commands and the SQLite -> ArangoDB migration.

The migration tests build a real SQLite file with Django's auth/session schema (as written by
Django 6's migrations), fill it with users whose hashes come from Django's hashers, and migrate it.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from arango.database import StandardDatabase
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.base import CreateError, UpdateError
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory

from apps.accounts.identity import ArangoUser, create_user, get_by_username, get_user
from apps.accounts.sessions import SessionStore
from apps.core.arango import schema as s
from apps.core.errors import Conflict

PASSWORD = "a-long-password-123"
API = "/api/v1"


@pytest.fixture(autouse=True)
def _clean(arango_db: StandardDatabase) -> None:
    from django.core.cache import cache

    cache.clear()  # login throttle counters


class TestIdentity:
    def test_create_and_load(self, arango_db: StandardDatabase) -> None:
        user = create_user("ada", PASSWORD, email="ada@example.org", is_staff=True)
        loaded = get_user(user.id)
        assert loaded == user
        assert loaded is not None
        assert (loaded.username, loaded.email, loaded.is_staff, loaded.is_superuser) == (
            "ada", "ada@example.org", True, False,
        )  # fmt: skip
        assert loaded.check_password(PASSWORD)
        assert not loaded.check_password("wrong")
        doc = arango_db.collection(s.AUTH_USERS).get(str(user.id))
        assert doc["password"] != PASSWORD
        assert doc["password"].startswith("md5$")  # Django's hasher (test settings: fast MD5)

    def test_ids_are_sequential_and_unique_under_concurrency(
        self, arango_db: StandardDatabase
    ) -> None:
        barrier = threading.Barrier(10)
        ids: list[int] = []

        def make(n: int) -> None:
            barrier.wait()
            ids.append(create_user(f"u{n}", PASSWORD).id)

        threads = [threading.Thread(target=make, args=(n,)) for n in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(ids) == list(range(min(ids), min(ids) + 10))

    def test_duplicate_username_conflicts_without_consuming_an_id(
        self, arango_db: StandardDatabase
    ) -> None:
        first = create_user("dup", PASSWORD)
        with pytest.raises(Conflict):
            create_user("dup", PASSWORD)
        assert create_user("next", PASSWORD).id == first.id + 1

    def test_concurrent_same_username_creates_exactly_one(
        self, arango_db: StandardDatabase
    ) -> None:
        barrier = threading.Barrier(8)
        outcomes: list[Any] = []

        def make() -> None:
            barrier.wait()
            try:
                outcomes.append(create_user("race", PASSWORD))
            except Conflict as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=make) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(isinstance(o, ArangoUser) for o in outcomes) == 1
        assert sum(isinstance(o, Conflict) for o in outcomes) == 7

    def test_hash_upgrade_on_login(self, arango_db: StandardDatabase, settings: Any) -> None:
        settings.PASSWORD_HASHERS = [
            "django.contrib.auth.hashers.MD5PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        ]
        user = create_user("legacy", None)
        user.password = make_password(PASSWORD, hasher="pbkdf2_sha256")
        user.save(update_fields=["password"])
        assert authenticate(RequestFactory().post("/"), username="legacy", password=PASSWORD)
        stored = get_by_username("legacy")
        assert stored is not None
        assert stored.password.startswith("md5$")  # re-hashed with the preferred hasher

    def test_orm_is_gone(self) -> None:
        from django.contrib.auth.models import User

        # DATABASES = {}: Django substitutes its dummy backend, which refuses every query.
        assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"
        with pytest.raises(ImproperlyConfigured):
            User.objects.count()


class TestAuthentication:
    def test_authenticate(self, arango_db: StandardDatabase) -> None:
        create_user("bea", PASSWORD)
        request = RequestFactory().post("/login", REMOTE_ADDR="203.0.113.1")
        user = authenticate(request, username="bea", password=PASSWORD)
        assert isinstance(user, ArangoUser)
        assert authenticate(request, username="bea", password="nope") is None
        assert authenticate(request, username="nobody", password=PASSWORD) is None

    def test_inactive_user_cannot_authenticate_or_keep_a_session(
        self, arango_db: StandardDatabase
    ) -> None:
        user = create_user("gone", PASSWORD)
        client = Client()
        client.force_login(user)
        assert client.get(f"{API}/saved-searches").status_code == 200
        user.is_active = False
        user.save(update_fields=["is_active"])
        assert authenticate(None, username="gone", password=PASSWORD) is None
        assert client.get(f"{API}/saved-searches").status_code == 403


class TestSessions:
    def test_login_logout_lifecycle_through_the_views(self, arango_db: StandardDatabase) -> None:
        user = create_user("cyd", PASSWORD)
        client = Client()
        r = client.post("/accounts/login/", {"username": "cyd", "password": PASSWORD})
        assert r.status_code == 302
        key = client.cookies[settings.SESSION_COOKIE_NAME].value
        doc = arango_db.collection(s.SESSIONS).get(key)
        assert doc is not None
        assert doc["expire_at"] > time.time() + settings.SESSION_COOKIE_AGE - 60
        assert client.session["_auth_user_id"] == str(user.id)
        reloaded = get_user(user.id)
        assert reloaded is not None
        assert reloaded.last_login is not None
        assert client.post("/accounts/logout/").status_code == 302
        assert arango_db.collection(s.SESSIONS).get(key) is None
        assert client.get(f"{API}/saved-searches").status_code == 403

    def test_login_rotates_the_session_key(self, arango_db: StandardDatabase) -> None:
        create_user("dee", PASSWORD)
        client = Client()
        session = client.session
        session["pre"] = 1
        session.save()
        before = session.session_key
        client.cookies[settings.SESSION_COOKIE_NAME] = str(before)
        client.post("/accounts/login/", {"username": "dee", "password": PASSWORD})
        after = client.cookies[settings.SESSION_COOKIE_NAME].value
        assert after != before  # no session fixation
        assert arango_db.collection(s.SESSIONS).get(str(before)) is None

    def test_expired_session_is_anonymous(self, arango_db: StandardDatabase) -> None:
        client = Client()
        client.force_login(create_user("eve", PASSWORD))
        key = client.cookies[settings.SESSION_COOKIE_NAME].value
        arango_db.collection(s.SESSIONS).update({"_key": key, "expire_at": time.time() - 1})
        assert client.get(f"{API}/saved-searches").status_code == 403

    def test_password_change_ends_other_sessions(self, arango_db: StandardDatabase) -> None:
        user = create_user("fay", PASSWORD)
        laptop, phone = Client(), Client()
        laptop.force_login(user)
        phone.force_login(user)
        assert phone.get(f"{API}/saved-searches").status_code == 200
        user.set_password("another-long-password-456")
        user.save(update_fields=["password"])
        assert phone.get(f"{API}/saved-searches").status_code == 403
        assert laptop.get(f"{API}/saved-searches").status_code == 403

    def test_session_store_semantics(self, arango_db: StandardDatabase) -> None:
        store = SessionStore()
        store["k"] = "v"
        store.save()
        key = store.session_key
        assert key is not None
        assert SessionStore(key)["k"] == "v"
        assert store.exists(key)
        clash = SessionStore(key)
        clash._session_cache = {}
        with pytest.raises(CreateError):
            clash.save(must_create=True)
        store.delete()
        resurrect = SessionStore(key)
        resurrect._session_cache = {"k": "again"}
        with pytest.raises(UpdateError):
            resurrect.save()  # deleted elsewhere (logout): not silently recreated

    def test_clear_expired(self, arango_db: StandardDatabase) -> None:
        live, old = SessionStore(), SessionStore()
        live["a"] = 1
        live.save()
        old["a"] = 1
        old.set_expiry(-10)
        old.save()
        SessionStore.clear_expired()
        assert arango_db.collection(s.SESSIONS).count() == 1


class TestAuthorization:
    def test_staff_only_endpoints(self, arango_db: StandardDatabase) -> None:
        plain, staff = Client(), Client()
        plain.force_login(create_user("pat", PASSWORD))
        staff.force_login(create_user("sam", PASSWORD, is_staff=True))
        assert plain.get(f"{API}/operations/audit").status_code == 403
        assert staff.get(f"{API}/operations/audit").status_code == 200
        assert Client().get(f"{API}/operations/audit").status_code == 403

    def test_csrf_still_enforced_for_session_auth(self, arango_db: StandardDatabase) -> None:
        create_user("cora", PASSWORD)
        client = Client(enforce_csrf_checks=True)
        assert client.login(username="cora", password=PASSWORD)
        r = client.post(
            f"{API}/saved-searches", {"name": "x", "filters": {}}, content_type="application/json"
        )
        assert r.status_code == 403


class TestCommands:
    def test_createsuperuser_noinput(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)
        call_command("createsuperuser", "--noinput", "--username", "root-admin")
        user = get_by_username("root-admin")
        assert user is not None
        assert (user.is_staff, user.is_superuser) == (True, True)
        assert user.check_password(PASSWORD)
        with pytest.raises(CommandError, match="already exists"):
            call_command("createsuperuser", "--noinput", "--username", "root-admin")

    def test_users_commands(
        self, arango_db: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = create_user("ops2", PASSWORD)
        call_command("users", "set-staff", "ops2", "--on")
        staffed = get_by_username("ops2")
        assert staffed is not None
        assert staffed.is_staff
        monkeypatch.setenv("QW_NEW_PASSWORD", "brand-new-password-789")
        call_command("users", "set-password", "ops2", "--noinput")
        changed = get_by_username("ops2")
        assert changed is not None
        assert changed.check_password("brand-new-password-789")
        with pytest.raises(CommandError, match="--yes"):
            call_command("users", "delete", "ops2")
        call_command("users", "delete", "ops2", "--yes")
        assert get_user(user.id) is None
        actions = {a["action"] for a in arango_db.collection(s.AUDIT_LOG).all()}
        expected = {"accounts.is_staff_changed", "accounts.password_changed", "accounts.deleted"}
        assert expected <= actions


# --- SQLite -> ArangoDB migration ------------------------------------------------------------

_DJANGO_AUTH_SCHEMA = """
CREATE TABLE "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL,
  "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL,
  "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL,
  "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL);
CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY,
  "session_data" text NOT NULL, "expire_date" datetime NOT NULL);
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(150) NOT NULL UNIQUE);
CREATE TABLE "auth_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "user_id" integer NOT NULL, "group_id" integer NOT NULL);
CREATE TABLE "auth_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "user_id" integer NOT NULL, "permission_id" integer NOT NULL);
"""
LIVE_KEY = "livesessionkey0000000000000000aa"
OLD_KEY = "oldsessionkey00000000000000000bb"


def _sqlite_ts(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(tzinfo=None).isoformat(sep=" ")


def _legacy_session_hash(password_hash: str) -> str:
    from django.utils.crypto import salted_hmac

    return salted_hmac(
        "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash",
        password_hash,
        algorithm="sha256",
    ).hexdigest()


@pytest.fixture
def legacy_db(tmp_path: Path) -> Path:
    path = tmp_path / "auth.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(_DJANGO_AUTH_SCHEMA)
    joined = _sqlite_ts(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    bob_hash = make_password("pw-bob-1234567")
    users = [
        (5, make_password("pw-alice-123456"), None, 0, "alice", "", "a@x.org", 0, 1, joined, "Al"),
        (9, bob_hash, joined, 1, "bob", "B", "", 1, 1, joined, ""),
        (12, make_password("pw-carl-123456"), None, 0, "carl", "", "", 1, 0, joined, ""),
    ]
    conn.executemany("INSERT INTO auth_user VALUES (?,?,?,?,?,?,?,?,?,?,?)", users)
    live = SessionStore().encode(
        {
            "_auth_user_id": "9",
            "_auth_user_backend": "apps.accounts.backends.ThrottledModelBackend",
            "_auth_user_hash": _legacy_session_hash(bob_hash),
        }
    )
    future = _sqlite_ts(datetime.now(UTC) + timedelta(days=3))
    past = _sqlite_ts(datetime.now(UTC) - timedelta(days=1))
    conn.executemany(
        "INSERT INTO django_session VALUES (?,?,?)",
        [(LIVE_KEY, live, future), (OLD_KEY, live, past)],
    )
    conn.commit()
    conn.close()
    return path


def _fingerprint(path: Path) -> tuple[str, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), os.stat(path).st_mtime_ns


class TestSqliteMigration:
    def test_migrates_identities_passwords_and_sessions(
        self, arango_db: StandardDatabase, legacy_db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        before = _fingerprint(legacy_db)
        call_command("migrate_auth_to_arango", "--sqlite", str(legacy_db))
        assert '"verified": true' in capsys.readouterr().out
        assert _fingerprint(legacy_db) == before  # the source is opened read-only

        alice, bob, carl = get_user(5), get_user(9), get_user(12)
        assert alice is not None
        assert bob is not None
        assert carl is not None
        assert (alice.username, alice.email, alice.is_staff) == ("alice", "a@x.org", False)
        assert (bob.is_staff, bob.is_superuser, bob.last_login is not None) == (True, True, True)
        assert carl.is_active is False
        assert alice.date_joined == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        assert arango_db.collection(s.AUTH_USERS).get("5")["first_name"] == "Al"
        # same passwords work; the inactive account stays locked out
        assert authenticate(None, username="alice", password="pw-alice-123456") == alice
        assert authenticate(None, username="carl", password="pw-carl-123456") is None
        # new accounts continue after the highest migrated id
        assert create_user("newbie", PASSWORD).id == 13
        # the unexpired session keeps bob signed in; the expired one was not copied
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = LIVE_KEY
        assert client.get(f"{API}/operations/audit").status_code == 200  # bob is staff
        assert arango_db.collection(s.SESSIONS).get(OLD_KEY) is None

    def test_rerun_is_idempotent(self, arango_db: StandardDatabase, legacy_db: Path) -> None:
        call_command("migrate_auth_to_arango", "--sqlite", str(legacy_db))
        call_command("migrate_auth_to_arango", "--sqlite", str(legacy_db))
        assert arango_db.collection(s.AUTH_USERS).count() == 3
        assert arango_db.collection(s.SESSIONS).count() == 1

    def test_dry_run_writes_nothing(
        self, arango_db: StandardDatabase, legacy_db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        call_command("migrate_auth_to_arango", "--sqlite", str(legacy_db), "--dry-run")
        assert '"sqlite_users": 3' in capsys.readouterr().out
        assert arango_db.collection(s.AUTH_USERS).count() == 0

    def test_refuses_identity_conflicts(self, arango_db: StandardDatabase, legacy_db: Path) -> None:
        create_user("alice", PASSWORD)  # id 1, but SQLite says alice is id 5
        with pytest.raises(CommandError, match="identity conflicts"):
            call_command("migrate_auth_to_arango", "--sqlite", str(legacy_db))
        assert arango_db.collection(s.AUTH_USERS).count() == 1
