"""Users stored in ArangoDB, presented to Django's auth machinery (ADR-015).

:class:`ArangoUser` implements the protocol ``django.contrib.auth`` relies on - ``login()``,
``get_user()``, session-hash verification, ``update_last_login``, DRF's ``IsAuthenticated`` /
``IsAdminUser`` - without the ORM. Password hashing is Django's own (``make_password`` /
``check_password``, with transparent hash upgrades), and the session auth hash is computed exactly
as ``AbstractBaseUser`` does, so sessions issued before the migration stay valid and changing a
password still invalidates the user's other sessions.

There are no groups or per-object permissions: an active superuser has every permission, everyone
else none (the application authorises with ``is_staff`` and ownership checks).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils.crypto import salted_hmac

from apps.accounts.repository import UserRepository
from apps.core.arango.client import get_db
from apps.core.clock import from_iso, to_iso, utc_now

_SESSION_HASH_SALT = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"


class _PrimaryKey:
    """The slice of ``Model._meta.pk`` that ``django.contrib.auth.login`` uses."""

    name = "id"
    attname = "id"

    @staticmethod
    def value_to_string(obj: ArangoUser) -> str:
        return str(obj.pk)

    @staticmethod
    def to_python(value: Any) -> int:
        return int(value)


class _Meta:
    pk = _PrimaryKey()
    app_label = "qw_accounts"
    model_name = "arangouser"
    object_name = "ArangoUser"


class ArangoUser:
    _meta = _Meta()
    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    is_authenticated = True
    is_anonymous = False

    def __init__(self, doc: dict[str, Any]) -> None:
        self.id = int(doc["id"])
        self.username: str = doc["username"]
        self.email: str = doc.get("email") or ""
        self.password: str = doc["password"]
        self.is_active = bool(doc.get("is_active", True))
        self.is_staff = bool(doc.get("is_staff", False))
        self.is_superuser = bool(doc.get("is_superuser", False))
        self.date_joined: datetime | None = _parse(doc.get("date_joined"))
        self.last_login: datetime | None = _parse(doc.get("last_login"))

    # -- identity --------------------------------------------------------------------------------
    @property
    def pk(self) -> int:
        return self.id

    def get_username(self) -> str:
        return self.username

    def natural_key(self) -> tuple[str]:
        return (self.username,)

    def get_full_name(self) -> str:
        return self.username

    def get_short_name(self) -> str:
        return self.username

    def __str__(self) -> str:
        return self.username

    def __repr__(self) -> str:
        return f"<ArangoUser {self.id} {self.username!r}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ArangoUser) and other.id == self.id

    def __hash__(self) -> int:
        return hash(("ArangoUser", self.id))

    # -- passwords -------------------------------------------------------------------------------
    def set_password(self, raw_password: str | None) -> None:
        self.password = make_password(raw_password)

    def set_unusable_password(self) -> None:
        self.password = make_password(None)

    def has_usable_password(self) -> bool:
        return not self.password.startswith("!")

    def check_password(self, raw_password: str) -> bool:
        def upgrade(raw: str) -> None:  # the hasher's work factor changed: re-hash on success
            self.set_password(raw)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, upgrade)

    def _session_auth_hash(self, secret: str | bytes | None = None) -> str:
        return salted_hmac(
            _SESSION_HASH_SALT, self.password, secret=secret, algorithm="sha256"
        ).hexdigest()

    def get_session_auth_hash(self) -> str:
        return self._session_auth_hash()

    def get_session_auth_fallback_hash(self) -> Iterator[str]:
        for fallback in settings.SECRET_KEY_FALLBACKS:
            yield self._session_auth_hash(secret=fallback)

    # -- permissions -----------------------------------------------------------------------------
    def has_perm(self, perm: str, obj: object | None = None) -> bool:
        return self.is_active and self.is_superuser

    def has_perms(self, perm_list: Any, obj: object | None = None) -> bool:
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_active and self.is_superuser

    # -- persistence -----------------------------------------------------------------------------
    def as_fields(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "is_active": self.is_active,
            "is_staff": self.is_staff,
            "is_superuser": self.is_superuser,
            "date_joined": to_iso(self.date_joined or utc_now()),
            "last_login": to_iso(self.last_login) if self.last_login else None,
        }

    def delete(self) -> dict[str, int]:
        """Delete the account and everything it owns in ArangoDB (one transaction)."""
        return delete_user(self.id)

    def save(self, update_fields: list[str] | None = None) -> None:
        """Persist changes (``update_last_login`` and hash upgrades pass ``update_fields``)."""
        fields = self.as_fields()
        if update_fields is not None:
            fields = {k: v for k, v in fields.items() if k in set(update_fields)}
        _repo().update(self.id, fields)


def _parse(value: Any) -> datetime | None:
    return from_iso(value) if value else None


def _repo() -> UserRepository:
    return UserRepository(get_db())


def create_user(
    username: str,
    password: str | None = None,
    *,
    email: str = "",
    is_staff: bool = False,
    is_superuser: bool = False,
    is_active: bool = True,
) -> ArangoUser:
    """Create an account (Conflict if the username exists). ``password=None`` = unusable."""
    doc = {
        "username": username,
        "email": email,
        "password": make_password(password),
        "is_active": is_active,
        "is_staff": is_staff or is_superuser,
        "is_superuser": is_superuser,
        "date_joined": to_iso(utc_now()),
        "last_login": None,
    }
    return ArangoUser(_repo().create(doc))


def create_superuser(username: str, password: str | None, *, email: str = "") -> ArangoUser:
    return create_user(username, password, email=email, is_staff=True, is_superuser=True)


def get_user(user_id: int) -> ArangoUser | None:
    doc = _repo().get(user_id)
    return ArangoUser(doc) if doc else None


def get_by_username(username: str) -> ArangoUser | None:
    doc = _repo().get_by_username(username)
    return ArangoUser(doc) if doc else None


def delete_user(user_id: int) -> dict[str, int]:
    """Delete the account and everything it owns in ArangoDB (one transaction)."""
    return _repo().delete(user_id)
