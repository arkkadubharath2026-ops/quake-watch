"""Server-rendered pages (L5, ADR-011): routing, auth gating, error pages, CSP and page contract.

Browser behaviour (JS rendering of every UI state) is covered by the Playwright suite; these
tests pin the server side each page relies on, against the real ArangoDB test database.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from arango.database import StandardDatabase
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.test import Client

from apps.accounts import security
from apps.accounts.identity import ArangoUser, create_user, get_by_username
from apps.ingestion.normalizer import parse_feed
from apps.ingestion.pipeline import IngestionPipeline
from tests.conftest import load_fixture

PUBLIC_PAGES = ["/", "/map/", "/explorer/", "/analytics/", "/status/", "/about/"]
USER_PAGES = ["/alerts/", "/research/"]
ATTRIBUTION = "Earthquake data courtesy of the U.S. Geological Survey (USGS)."
PASSWORD = "correct-horse-battery-9"


@pytest.fixture
def events(arango_db: StandardDatabase) -> Iterator[StandardDatabase]:
    cache.clear()
    IngestionPipeline(arango_db).ingest(parse_feed(load_fixture("usgs/all_day.geojson")).records)
    yield arango_db
    cache.clear()


@pytest.fixture
def user(arango_db: StandardDatabase) -> ArangoUser:
    return create_user("pageuser", password=PASSWORD)


@pytest.fixture
def staff(arango_db: StandardDatabase) -> ArangoUser:
    return create_user("pagestaff", password=PASSWORD, is_staff=True)


def html(response: Any) -> str:
    return response.content.decode()


def _nonce(response: Any) -> str:
    match = re.search(r"'nonce-([^']+)'", response.headers["Content-Security-Policy"])
    assert match, "CSP must carry a nonce"
    return match.group(1)


class TestPageContract:
    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_public_pages_render_with_shared_layout(
        self, client: Client, arango_db: StandardDatabase, path: str
    ) -> None:
        r = client.get(path)
        assert r.status_code == 200
        page = html(r)
        assert ATTRIBUTION in page
        assert "does not predict earthquakes" in page
        assert 'href="#main"' in page  # skip link target
        assert 'id="main"' in page
        assert 'name="csrf-token"' in page

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_every_inline_script_carries_the_csp_nonce(
        self, client: Client, arango_db: StandardDatabase, path: str
    ) -> None:
        r = client.get(path)
        nonce = _nonce(r)
        for tag in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html(r)):
            if 'type="application/json"' in tag:
                continue  # json_script data blocks are not executed
            assert f'nonce="{nonce}"' in tag, tag
        assert "script-src 'self' 'nonce-" in r.headers["Content-Security-Policy"]
        assert "unsafe-inline" not in r.headers["Content-Security-Policy"]

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_referenced_static_files_exist(
        self, client: Client, arango_db: StandardDatabase, path: str
    ) -> None:
        for ref in re.findall(r'(?:src|href)="/static/([^"]+)"', html(client.get(path))):
            assert finders.find(ref), f"missing static file {ref}"

    def test_active_nav_item_is_marked(self, client: Client, arango_db: StandardDatabase) -> None:
        page = html(client.get("/analytics/"))
        assert re.search(r'href="/analytics/"\s+aria-current="page"', page)

    def test_nav_hides_user_and_staff_items_from_anonymous(
        self, client: Client, arango_db: StandardDatabase
    ) -> None:
        page = html(client.get("/"))
        assert 'href="/alerts/"' not in page
        assert 'href="/operations/"' not in page


class TestEventDetail:
    def test_renders_source_values_server_side(
        self, client: Client, events: StandardDatabase
    ) -> None:
        doc = next(iter(events.aql.execute("FOR e IN events SORT e._key LIMIT 1 RETURN e")))
        r = client.get(f"/events/{doc['_key']}/")
        assert r.status_code == 200
        page = html(r)
        assert "Source values (USGS)" in page
        assert "Derived by QuakeWatch" in page
        assert 'id="event-data"' in page  # JSON for the tab scripts, escaped by json_script
        if doc.get("place"):
            assert doc["place"].replace("'", "&#x27;") in page

    def test_raw_usgs_id_redirects_to_canonical_url(
        self, client: Client, events: StandardDatabase
    ) -> None:
        doc = next(iter(events.aql.execute("FOR e IN events LIMIT 1 RETURN e")))
        r = client.get(f"/events/{doc['source_event_id']}/")
        assert r.status_code == 302
        assert r.headers["Location"] == f"/events/{doc['_key']}/"

    def test_unknown_event_is_404_with_navigation(
        self, client: Client, events: StandardDatabase
    ) -> None:
        r = client.get("/events/usgs_does_not_exist/")
        assert r.status_code == 404


class TestAuthGating:
    @pytest.mark.parametrize("path", [*USER_PAGES, "/operations/"])
    def test_anonymous_is_redirected_to_login(
        self, client: Client, arango_db: StandardDatabase, path: str
    ) -> None:
        r = client.get(path)
        assert r.status_code == 302
        assert r.headers["Location"] == f"/accounts/login/?next={path}"

    @pytest.mark.parametrize("path", USER_PAGES)
    def test_signed_in_user_sees_user_pages(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser, path: str
    ) -> None:
        client.force_login(user)
        assert client.get(path).status_code == 200

    def test_operations_is_403_for_non_staff(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser
    ) -> None:
        client.force_login(user)
        r = client.get("/operations/")
        assert r.status_code == 403
        assert "staff only" in html(r)

    def test_operations_for_staff_and_nav_shows_it(
        self, client: Client, arango_db: StandardDatabase, staff: ArangoUser
    ) -> None:
        client.force_login(staff)
        r = client.get("/operations/")
        assert r.status_code == 200
        assert 'href="/operations/"' in html(r)


class TestAccounts:
    def test_signup_creates_account_and_signs_in(
        self, client: Client, arango_db: StandardDatabase
    ) -> None:
        r = client.post(
            "/accounts/signup/",
            {"username": "newperson", "password1": PASSWORD, "password2": PASSWORD},
        )
        assert r.status_code == 302
        assert r.headers["Location"] == "/"
        assert get_by_username("newperson") is not None
        assert "_auth_user_id" in client.session

    def test_signup_validation_errors_are_linked_to_fields(
        self, client: Client, arango_db: StandardDatabase
    ) -> None:
        r = client.post(
            "/accounts/signup/", {"username": "x", "password1": "short", "password2": "other"}
        )
        assert r.status_code == 400
        page = html(r)
        assert 'aria-invalid="true"' in page
        assert 'aria-describedby="id_password2-error' in page
        assert get_by_username("x") is None

    def test_login_and_post_only_logout(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser
    ) -> None:
        cache.clear()
        r = client.post(
            "/accounts/login/", {"username": "pageuser", "password": PASSWORD, "next": "/alerts/"}
        )
        assert r.status_code == 302
        assert r.headers["Location"] == "/alerts/"
        assert client.get("/accounts/logout/").status_code == 405  # GET must not log out
        assert client.post("/accounts/logout/").status_code == 302
        assert "_auth_user_id" not in client.session

    def test_login_rejects_offsite_next(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser
    ) -> None:
        cache.clear()
        r = client.post(
            "/accounts/login/",
            {"username": "pageuser", "password": PASSWORD, "next": "https://evil.example/"},
        )
        assert r.status_code == 302
        assert r.headers["Location"] == "/"

    def test_lockout_is_explained_to_the_user(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser
    ) -> None:
        cache.clear()
        for _ in range(security.PAIR_LIMIT):
            client.post("/accounts/login/", {"username": "pageuser", "password": "wrong"})
        r = client.post("/accounts/login/", {"username": "pageuser", "password": PASSWORD})
        assert r.status_code == 200
        assert "Too many sign-in attempts" in html(r)
        assert "_auth_user_id" not in client.session
        cache.clear()

    def test_wrong_password_shows_generic_error(
        self, client: Client, arango_db: StandardDatabase, user: ArangoUser
    ) -> None:
        cache.clear()
        r = client.post("/accounts/login/", {"username": "pageuser", "password": "wrong"})
        assert r.status_code == 200
        page = html(r)
        assert "Please enter a correct username and password" in page
        assert "Too many" not in page
