"""Browser end-to-end fixtures (Playwright + pytest-django live server).

The live server runs the real Django app in-process against the real ArangoDB test database, seeded
from the recorded USGS feed. Only two things are stubbed at the browser's network edge:

* OpenStreetMap tiles (third-party, not ours to load in CI) are answered with a blank tile;
* individual tests deliberately break ``/api/v1`` responses to exercise the UI error states.

Every page is also checked for console errors, uncaught exceptions and CSP violations.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from arango.database import StandardDatabase
from django.core.cache import cache
from playwright.sync_api import ConsoleMessage, Page, Route
from pytest_django.live_server_helper import LiveServer

from apps.accounts.identity import ArangoUser, create_user
from apps.ingestion.normalizer import parse_feed
from apps.ingestion.pipeline import IngestionPipeline
from tests.conftest import load_fixture

PASSWORD = "correct-horse-battery-9"
BLANK_TILE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@dataclass
class BrowserErrors:
    messages: list[str] = field(default_factory=list)
    allowed: list[str] = field(default_factory=list)

    def allow(self, fragment: str) -> None:
        """Expect console errors containing ``fragment`` (tests that break things on purpose)."""
        self.allowed.append(fragment)

    def unexpected(self) -> list[str]:
        return [m for m in self.messages if not any(a in m for a in self.allowed)]


@pytest.fixture(scope="session", autouse=True)
def _allow_sync_orm_under_playwright() -> Iterator[None]:
    """Playwright's sync API runs an event loop in the main thread, so Django's async-safety guard
    would refuse the fixtures' (synchronous) ORM calls, including the session-scoped test-database
    setup. Session-scoped so it precedes that setup; this conftest applies to browser tests only."""
    previous = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    yield
    if previous is None:
        os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
    else:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = previous


@pytest.fixture
def seeded(arango_db: StandardDatabase) -> Iterator[StandardDatabase]:
    cache.clear()
    IngestionPipeline(arango_db).ingest(parse_feed(load_fixture("usgs/all_day.geojson")).records)
    yield arango_db
    cache.clear()


@pytest.fixture
def transactional_db() -> None:
    """pytest-django's live_server requests this to flush the ORM test database between tests.
    There is no ORM database (ADR-015); accounts, sessions and data live in ArangoDB and are reset
    by the ArangoDB fixtures instead."""
    return


@pytest.fixture(scope="session")
def base_url(live_server: LiveServer) -> str:
    """Relative ``page.goto("/path")`` resolves against the live server (pytest-base-url)."""
    return str(live_server.url)


@pytest.fixture
def browser_errors(page: Page) -> Iterator[BrowserErrors]:
    errors = BrowserErrors()

    def on_console(msg: ConsoleMessage) -> None:
        if msg.type == "error":
            errors.messages.append(msg.text)

    page.on("console", on_console)
    page.on("pageerror", lambda exc: errors.messages.append(f"pageerror: {exc}"))
    page.route(
        "https://*.tile.openstreetmap.org/**",
        lambda route: route.fulfill(status=200, content_type="image/png", body=BLANK_TILE),
    )
    yield errors
    assert not errors.unexpected(), errors.unexpected()


@pytest.fixture
def ui(page: Page, seeded: StandardDatabase, browser_errors: BrowserErrors) -> Page:
    """A page on the live server over seeded data, with error collection and stubbed tiles."""
    page.set_default_timeout(10_000)
    return page


def settle(page: Page) -> None:
    """Wait until no data region is still loading."""
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => !document.querySelector('[aria-busy=\"true\"]')")


@pytest.fixture
def user(seeded: StandardDatabase) -> ArangoUser:
    return create_user("e2e_user", password=PASSWORD)


@pytest.fixture
def staff(seeded: StandardDatabase) -> ArangoUser:
    return create_user("e2e_staff", password=PASSWORD, is_staff=True)


def log_in(page: Page, username: str) -> None:
    page.goto("/accounts/login/")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/")


def break_api(page: Page, pattern: str, *, status: int, body: str | None = None) -> None:
    def handler(route: Route) -> None:
        if status == 0:
            route.abort("connectionrefused")
        else:
            route.fulfill(
                status=status,
                content_type="application/json",
                body=body
                or '{"error": {"code": "internal_error", "message": "Server failure",'
                ' "correlation_id": "e2e-corr-1"}}',
            )

    page.route(pattern, handler)
