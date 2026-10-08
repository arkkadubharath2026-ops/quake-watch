"""Django session engine on ArangoDB (``SESSION_ENGINE = "apps.accounts.sessions"``, ADR-015).

Mirrors ``django.contrib.sessions.backends.db`` exactly, with the ``sessions`` collection in
place of the ``django_session`` table:

* session data is Django's own signed encoding (``SessionBase.encode``), so sessions migrated
  from SQLite keep working unchanged;
* a load ignores sessions past ``expire_at`` (application clock, as the db backend does); the TTL
  index only garbage-collects them;
* ``save(must_create=True)`` is an insert that fails on an existing key (``CreateError`` -> a new
  key is drawn); a plain ``save`` only updates an existing session, so a session deleted
  concurrently (logout elsewhere) raises ``UpdateError`` instead of being resurrected.
"""

from __future__ import annotations

import time
from typing import Any

from django.contrib.sessions.backends.base import CreateError, SessionBase, UpdateError

from apps.accounts.repository import SessionRepository
from apps.core.arango.client import get_db


def _repo() -> SessionRepository:
    return SessionRepository(get_db())


class SessionStore(SessionBase):
    def load(self) -> dict[str, Any]:
        data = _repo().load(self.session_key, time.time()) if self.session_key else None
        if data is None:
            self._session_key = None
            return {}
        return self.decode(data)

    def exists(self, session_key: str) -> bool:
        return _repo().exists(session_key)

    def create(self) -> None:
        while True:
            self._session_key = self._get_new_session_key()  # type: ignore[attr-defined]
            try:
                self.save(must_create=True)
            except CreateError:
                continue  # key collision: draw another
            self.modified = True
            return

    def save(self, must_create: bool = False) -> None:
        if self.session_key is None:
            return self.create()
        data = self.encode(self._get_session(no_load=must_create))  # type: ignore[attr-defined]
        expire_at = self.get_expiry_date().timestamp()
        repo = _repo()
        if must_create:
            if not repo.insert(self.session_key, data, expire_at):
                raise CreateError
        elif not repo.update(self.session_key, data, expire_at):
            raise UpdateError
        return None

    def delete(self, session_key: str | None = None) -> None:
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        _repo().delete(session_key)

    @classmethod
    def clear_expired(cls) -> None:
        _repo().clear_expired(time.time())
