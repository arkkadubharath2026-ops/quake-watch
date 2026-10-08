"""Shared pytest fixtures.

Integration tests run against a real ArangoDB (``docker compose up -d arangodb``) using the
isolated ``<db>_test`` database, which is created and migrated once per session and truncated
between tests. Nothing in the integration suite mocks the database.

``dead_arango_db`` is a handle on a port where nothing listens: outage tests use it to inject a
real connection failure into the shared-state stores (cache, metrics, circuit breaker).
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
def django_db_setup() -> None:
    """No ORM test database to create: DATABASES is empty (ADR-015)."""
    return


@pytest.fixture(scope="session")
def arango_session_db() -> Iterator[StandardDatabase]:
    name = database_name()
    assert name.endswith("_test"), "integration tests must never touch a non-test database"
    drop_database(name)
    db = ensure_database(name)
    apply_schema(db)
    yield db
    metrics.flush()  # write buffered metrics while the database still exists (not at exit)
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
def clean_metrics(arango_session_db: StandardDatabase) -> Iterator[None]:
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def dead_arango_db() -> StandardDatabase:
    from arango.client import ArangoClient
    from arango.http import DefaultHTTPClient

    client = ArangoClient(
        hosts="http://127.0.0.1:9",
        http_client=DefaultHTTPClient(request_timeout=2, retry_attempts=0),
    )
    return client.db("quakewatch_test", username="root", password="unused", verify=False)


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Record the outcome of full runs in var/test-status.json for scripts/dashboard.py."""
    import json
    from datetime import UTC, datetime

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None or session.config.option.collectonly:
        return
    outcomes = ("passed", "failed", "error", "skipped")
    counts = {key: len(reporter.stats.get(key, [])) for key in outcomes}
    status = {
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_status": int(exitstatus),
        "args": session.config.invocation_params.args,
        **counts,
    }
    target = Path(session.config.rootpath) / "var" / "test-status.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(status, indent=2) + "\n")
