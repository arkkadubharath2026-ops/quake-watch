"""Saved searches, research snapshots (reproducibility), admin actions + audit, login throttling."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import zipfile
from typing import Any

import httpx
import pytest
from arango.database import StandardDatabase
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, RequestFactory

from apps.accounts import security
from apps.core.arango import schema as s
from apps.core.resilience import CircuitBreaker
from apps.ingestion.adapters.http import ResilientHttpClient
from apps.ingestion.adapters.usgs import UsgsClient
from apps.ingestion.normalizer import NormalizedRecord, normalize_feature, parse_feed
from apps.ingestion.pipeline import IngestionPipeline
from apps.research import manifest as m
from tests.conftest import load_fixture

API = "/api/v1"
PASSWORD = "a-long-password-123"
pytestmark = pytest.mark.django_db


def body(response: Any) -> Any:
    return json.loads(response.content) if response.content else None


@pytest.fixture
def events(arango_db: StandardDatabase) -> StandardDatabase:
    IngestionPipeline(arango_db).ingest(parse_feed(load_fixture("usgs/all_day.geojson")).records)
    return arango_db


@pytest.fixture
def user_client(client: Client) -> Client:
    client.force_login(User.objects.create_user("researcher", password=PASSWORD))
    return client


@pytest.fixture
def staff_client(client: Client) -> Client:
    client.force_login(User.objects.create_user("ops", password=PASSWORD, is_staff=True))
    return client


class TestSavedSearches:
    def test_crud_and_run(self, user_client: Client, events: StandardDatabase) -> None:
        created = body(
            user_client.post(
                f"{API}/saved-searches",
                {"name": "  CA quakes ", "filters": {"q": "california", "min_magnitude": "1"}},
                content_type="application/json",
            )
        )
        assert created["name"] == "CA quakes"
        assert created["filters"] == {
            "direction": "desc", "min_magnitude": 1.0, "q": "california", "sort": "occurred_at"
        }  # fmt: skip
        assert "location matches" in created["summary"]

        run = body(user_client.get(f"{API}/saved-searches/{created['id']}/events"))
        assert run["total"] > 0
        assert all(r["magnitude"] >= 1 for r in run["results"])

        renamed = body(
            user_client.patch(
                f"{API}/saved-searches/{created['id']}",
                {"name": "CA"},
                content_type="application/json",
            )
        )
        assert renamed["name"] == "CA"
        assert user_client.delete(f"{API}/saved-searches/{created['id']}").status_code == 204
        assert body(user_client.get(f"{API}/saved-searches"))["results"] == []

    def test_invalid_filters_rejected(self, user_client: Client, events: StandardDatabase) -> None:
        response = user_client.post(
            f"{API}/saved-searches",
            {"name": "bad", "filters": {"sort": "hack"}},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "sort" in body(response)["error"]["details"]["fields"]

    def test_private_to_owner(self, user_client: Client, events: StandardDatabase) -> None:
        created = body(
            user_client.post(
                f"{API}/saved-searches",
                {"name": "mine", "filters": {}},
                content_type="application/json",
            )
        )
        other = Client()
        other.force_login(User.objects.create_user("other", password=PASSWORD))
        assert other.get(f"{API}/saved-searches/{created['id']}").status_code == 404
        assert other.get(f"{API}/saved-searches/{created['id']}/events").status_code == 404


class TestResearchSnapshots:
    def create(self, client: Client, **filters: str) -> dict[str, Any]:
        response = client.post(
            f"{API}/research/snapshots",
            {"title": "Test dataset", "notes": "unit test", "filters": filters},
            content_type="application/json",
        )
        assert response.status_code == 201, body(response)
        return body(response)  # type: ignore[no-any-return]

    def test_snapshot_is_reproducible_after_source_revision(
        self, user_client: Client, events: StandardDatabase
    ) -> None:
        snapshot = self.create(user_client, min_magnitude="1")
        first = user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export?format=zip")
        assert first.status_code == 200
        assert first["X-Content-SHA256"] == snapshot["content_sha256"]

        # USGS revises one of the pinned events afterwards...
        feed = json.loads(load_fixture("usgs/all_day.geojson"))
        raw = copy.deepcopy(next(f for f in feed["features"] if f["properties"]["mag"] >= 1))
        raw["properties"]["mag"] += 1.5
        raw["properties"]["updated"] += 3_600_000
        rec = normalize_feature(raw)
        assert isinstance(rec, NormalizedRecord)
        assert IngestionPipeline(events).ingest([rec]).counts["revised"] == 1

        # ...the snapshot still exports the exact same bytes.
        second = user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export?format=zip")
        assert second.content == first.content
        assert second["X-Content-SHA256"] == snapshot["content_sha256"]

    def test_bundle_contents_and_checksums(
        self, user_client: Client, events: StandardDatabase
    ) -> None:
        snapshot = self.create(user_client, min_magnitude="2")
        archive = zipfile.ZipFile(
            io.BytesIO(user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export").content)
        )
        assert sorted(archive.namelist()) == [
            "SHA256SUMS",
            "data.csv",
            "data.json",
            "manifest.json",
        ]
        sums = dict(
            reversed(line.split("  ")) for line in archive.read("SHA256SUMS").decode().splitlines()
        )
        for name in ("data.csv", "data.json", "manifest.json"):
            assert hashlib.sha256(archive.read(name)).hexdigest() == sums[name]

        manifest = json.loads(archive.read("manifest.json"))
        rows = list(csv.DictReader(io.StringIO(archive.read("data.csv").decode())))
        assert manifest["row_count"] == len(rows) == snapshot["row_count"]
        assert manifest["query_definition"]["filters"]["min_magnitude"] == 2.0
        assert manifest["application_version"]
        assert manifest["source"] == "USGS"
        assert all(float(r["magnitude"]) >= 2 for r in rows)
        assert [c["name"] for c in manifest["columns"]] == list(m.COLUMN_NAMES)
        json_rows = json.loads(archive.read("data.json"))["rows"]
        assert m.content_sha256(json_rows) == manifest["content_sha256"]

    def test_csv_and_json_formats(self, user_client: Client, events: StandardDatabase) -> None:
        snapshot = self.create(user_client, min_magnitude="3")
        csv_resp = user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export?format=csv")
        assert csv_resp["Content-Type"].startswith("text/csv")
        assert csv_resp.content.decode().splitlines()[0].startswith("event_key,source,")
        json_resp = user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export?format=json")
        assert body(json_resp)["manifest"]["snapshot_id"] == snapshot["id"]
        bad = user_client.get(f"{API}/research/snapshots/{snapshot['id']}/export?format=xls")
        assert bad.status_code == 400

    def test_list_detail_privacy_delete(
        self, user_client: Client, events: StandardDatabase
    ) -> None:
        snapshot = self.create(user_client)
        listing = body(user_client.get(f"{API}/research/snapshots"))["results"]
        assert [s_["id"] for s_ in listing] == [snapshot["id"]]
        assert "members" not in listing[0]
        other = Client()
        other.force_login(User.objects.create_user("peer", password=PASSWORD))
        assert other.get(f"{API}/research/snapshots/{snapshot['id']}").status_code == 404
        assert other.get(f"{API}/research/snapshots/{snapshot['id']}/export").status_code == 404
        assert user_client.delete(f"{API}/research/snapshots/{snapshot['id']}").status_code == 204

    def test_too_large_selection_rejected(
        self, user_client: Client, events: StandardDatabase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.research.services.MAX_SNAPSHOT_ROWS", 5)
        response = user_client.post(
            f"{API}/research/snapshots",
            {"title": "big", "filters": {}},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "narrow" in body(response)["error"]["message"]

    def test_title_required(self, user_client: Client, events: StandardDatabase) -> None:
        response = user_client.post(
            f"{API}/research/snapshots", {"filters": {}}, content_type="application/json"
        )
        assert response.status_code == 400


class TestAdminActionsAndAudit:
    @pytest.fixture(autouse=True)
    def _fake_usgs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        feed = load_fixture("usgs/all_day.geojson")
        breaker = CircuitBreaker("USGS-ADMIN", failure_threshold=50, reset_seconds=60)

        def build() -> UsgsClient:
            http = ResilientHttpClient(
                source="USGS",
                breaker=breaker,
                connect_timeout=1,
                read_timeout=1,
                max_retries=0,
                user_agent="t",
                transport=httpx.MockTransport(
                    lambda r: (
                        httpx.Response(200, json={"count": 0, "maxAllowed": 20000})
                        if r.url.path.endswith("/count")
                        else httpx.Response(200, content=feed)
                    )
                ),
            )
            return UsgsClient(http, "https://usgs.test")

        for module in ("apps.ingestion.tasks", "apps.operations.api"):
            monkeypatch.setattr(f"{module}.build_usgs_client", build)

    def test_trigger_sync_is_audited(
        self, staff_client: Client, arango_db: StandardDatabase
    ) -> None:
        response = staff_client.post(
            f"{API}/operations/sync", {"feed": "all_day"}, content_type="application/json"
        )
        assert response.status_code == 202
        assert arango_db.collection(s.EVENTS).count() > 0  # eager Celery ran the real task
        entries = body(staff_client.get(f"{API}/operations/audit"))["results"]
        sync_entries = [e for e in entries if e["action"] == "ingestion.sync_triggered"]
        assert sync_entries[0]["actor_username"] == "ops"
        assert sync_entries[0]["target"] == "all_day"
        assert sync_entries[0]["correlation_id"] == response["X-Request-ID"]

    def test_invalid_feed_rejected(self, staff_client: Client, arango_db: StandardDatabase) -> None:
        response = staff_client.post(
            f"{API}/operations/sync", {"feed": "../../x"}, content_type="application/json"
        )
        assert response.status_code == 400

    def test_create_backfill_is_audited(
        self, staff_client: Client, arango_db: StandardDatabase
    ) -> None:
        response = staff_client.post(
            f"{API}/operations/backfill",
            {"start": "2026-09-01", "end": "2026-09-02", "min_magnitude": 4.5, "window_days": 1},
            content_type="application/json",
        )
        assert response.status_code == 202, body(response)
        jobs = body(staff_client.get(f"{API}/operations/backfill"))["results"]
        assert jobs[0]["_key"] == body(response)["job_id"]
        assert jobs[0]["status"] == "completed"  # eager run with count 0
        audit = body(staff_client.get(f"{API}/operations/audit?action=ingestion.backfill_created"))
        assert audit["total"] == 1

    def test_backfill_validation(self, staff_client: Client, arango_db: StandardDatabase) -> None:
        response = staff_client.post(
            f"{API}/operations/backfill",
            {"start": "2026-09-02", "end": "2026-09-01"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_retry_dead_letter(self, staff_client: Client, arango_db: StandardDatabase) -> None:
        feed = json.loads(load_fixture("usgs/all_day.geojson"))
        bad = copy.deepcopy(feed["features"][0])
        bad["properties"]["status"] = "bogus"
        IngestionPipeline(arango_db).ingest([], [normalize_feature(bad)])  # type: ignore[list-item]
        (letter,) = list(arango_db.collection(s.DEAD_LETTERS).all())

        still = body(staff_client.post(f"{API}/operations/dead-letters/{letter['_key']}/retry"))
        assert still["outcome"] == "still_rejected"
        assert arango_db.collection(s.DEAD_LETTERS).get(letter["_key"])["retry_count"] == 2

        fixed = {k: v for k, v in copy.deepcopy(letter).items() if k != "_rev"}
        fixed["payload"]["properties"]["status"] = "reviewed"
        arango_db.collection(s.DEAD_LETTERS).replace(fixed)
        done = body(staff_client.post(f"{API}/operations/dead-letters/{letter['_key']}/retry"))
        assert done["outcome"] == "reingested"
        assert arango_db.collection(s.DEAD_LETTERS).get(letter["_key"])["resolved_at"]

    @pytest.mark.parametrize(
        ("method", "path"),
        [("post", "operations/sync"), ("post", "operations/backfill"), ("get", "operations/audit")],
    )
    def test_non_staff_forbidden(
        self, user_client: Client, arango_db: StandardDatabase, method: str, path: str
    ) -> None:
        assert getattr(user_client, method)(f"{API}/{path}").status_code == 403

    def test_audit_has_no_write_api(
        self, staff_client: Client, arango_db: StandardDatabase
    ) -> None:
        assert staff_client.delete(f"{API}/operations/audit").status_code == 405
        assert staff_client.post(f"{API}/operations/audit").status_code == 405


class TestLoginThrottling:
    @pytest.fixture(autouse=True)
    def _clean(self, arango_db: StandardDatabase) -> None:
        cache.clear()

    def test_lockout_after_repeated_failures(self) -> None:
        User.objects.create_user("victim", password=PASSWORD)
        request = RequestFactory().post("/login", REMOTE_ADDR="203.0.113.7")
        for _ in range(security.LOCK_THRESHOLD):
            assert authenticate(request, username="victim", password="wrong") is None
        # The correct password is refused while locked.
        assert authenticate(request, username="victim", password=PASSWORD) is None
        # A different client address is not locked by this attacker's failures.
        other = RequestFactory().post("/login", REMOTE_ADDR="198.51.100.9")
        assert authenticate(other, username="victim", password=PASSWORD) is not None

    def test_success_resets_and_is_audited(self, arango_db: StandardDatabase) -> None:
        User.objects.create_user("normal", password=PASSWORD)
        client = Client()
        assert not client.login(username="normal", password="wrong")
        assert client.login(username="normal", password=PASSWORD)
        actions = [a["action"] for a in arango_db.collection(s.AUDIT_LOG).all()]
        assert "auth.login_failed" in actions
        assert "auth.login_succeeded" in actions
        assert not security.is_locked("normal", None)
