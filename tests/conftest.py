"""Shared pytest fixtures.

Integration tests run against a real ArangoDB (``docker compose up -d arangodb redis``) using the
isolated ``<db>_test`` database, which is created and migrated once per session and truncated
between tests. Nothing in the integration suite mocks the database.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from arango.database import StandardDatabase

from apps.core import metrics
from apps.core.arango import schema as s
from apps.core.arango.client import database_name, drop_database, ensure_database, get_db
from apps.core.arango.migrate import apply_schema

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath)).as_posix()
        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
        elif "/tests/performance/" in path:
            item.add_marker(pytest.mark.perf)


@pytest.fixture(scope="session")
def arango_session_db() -> Iterator[StandardDatabase]:
    name = database_name()
    assert name.endswith("_test"), "integration tests must never touch a non-test database"
    drop_database(name)
    db = ensure_database(name)
    apply_schema(db)
    yield db
    drop_database(name)


@pytest.fixture
def arango_db(arango_session_db: StandardDatabase) -> StandardDatabase:
    """Clean database per test (collections truncated, schema/indexes kept)."""
    db = get_db()
    for spec in s.COLLECTIONS:
        if spec.name != s.SCHEMA_META:
            db.collection(spec.name).truncate()
    return db


@pytest.fixture
def clean_metrics() -> Iterator[None]:
    metrics.reset()
    yield
    metrics.reset()


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
