"""Alert rules end to end: API CRUD + authorization, observer inside ingestion, feed, graph."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from arango.database import StandardDatabase
from django.test import Client

from apps.accounts.identity import ArangoUser, create_user
from apps.alerts.observer import AlertRuleObserver
from apps.core.arango import schema as s
from apps.ingestion.normalizer import NormalizedRecord, normalize_feature
from apps.ingestion.pipeline import IngestionPipeline
from tests.conftest import load_fixture

API = "/api/v1"
# Rule centre = location of the first recorded fixture event, so tests survive re-recording.
_FIRST = json.loads(load_fixture("usgs/all_day.geojson"))["features"][0]
CENTER = [round(c, 3) for c in _FIRST["geometry"]["coordinates"][:2]]  # [lon, lat]
PASSWORD = "a-long-password-123"


def body(response: Any) -> Any:
    return json.loads(response.content) if response.content else None


def recent_feature(index: int = 0, *, minutes_ago: int = 10, **props: Any) -> dict[str, Any]:
    """A real recorded feature re-timed relative to now (keeps tests time-independent)."""
    feed = json.loads(load_fixture("usgs/all_day.geojson"))
    raw = copy.deepcopy(feed["features"][index])
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    raw["properties"]["time"] = now_ms - minutes_ago * 60_000
    raw["properties"]["updated"] = now_ms - minutes_ago * 60_000 + 30_000
    raw["properties"].update(props)
    return raw


def record(raw: dict[str, Any]) -> NormalizedRecord:
    result = normalize_feature(raw)
    assert isinstance(result, NormalizedRecord), result
    return result


def ingest(db: StandardDatabase, *raws: dict[str, Any], mode: str = "feed") -> None:
    IngestionPipeline(db, observers=[AlertRuleObserver()], mode=mode).ingest(  # type: ignore[arg-type]
        [record(r) for r in raws]
    )


@pytest.fixture
def alice(client: Client) -> ArangoUser:
    user = create_user("alice", password=PASSWORD)
    client.force_login(user)
    return user


def create_rule(client: Client, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Near first event",
        "conditions": {"minimum_magnitude": 1.0, "center": CENTER, "radius_km": 100},
        "cooldown_minutes": 30,
    }
    payload.update(overrides)
    response = client.post(f"{API}/alert-rules", payload, content_type="application/json")
    assert response.status_code == 201, body(response)
    return body(response)  # type: ignore[no-any-return]


class TestRuleCrud:
    def test_create_list_get_patch_delete(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        assert rule["enabled"] is True
        assert rule["conditions"]["center"] == CENTER

        listing = body(client.get(f"{API}/alert-rules"))["results"]
        assert [r["id"] for r in listing] == [rule["id"]]
        assert listing[0]["match_count"] == 0

        patched = body(
            client.patch(
                f"{API}/alert-rules/{rule['id']}",
                {"enabled": False, "cooldown_minutes": 5},
                content_type="application/json",
            )
        )
        assert (patched["enabled"], patched["cooldown_minutes"]) == (False, 5)
        assert patched["name"] == "Near first event"

        assert client.delete(f"{API}/alert-rules/{rule['id']}").status_code == 204
        assert client.get(f"{API}/alert-rules/{rule['id']}").status_code == 404
        assert arango_db.collection(s.USER_OWNS_RULE).count() == 0

    def test_graph_edges_and_user_vertex_created(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        (edge,) = list(arango_db.collection(s.USER_OWNS_RULE).all())
        assert edge["_from"] == f"users/{alice.pk}"
        assert edge["_to"] == f"alert_rules/{rule['id']}"
        assert arango_db.collection(s.USERS).get(str(alice.pk))["username"] == "alice"

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            ({"name": "x", "conditions": {}}, "conditions"),
            ({"name": "", "conditions": {"tsunami_only": True}}, "name"),
            ({"name": "x", "conditions": {"center": CENTER}}, "conditions"),
            ({"name": "x", "conditions": {"minimum_magnitude": 99}},
             "conditions.minimum_magnitude"),
            ({"name": "x", "conditions": {"tsunami_only": True}, "evil": 1}, "evil"),
            ({"name": "x", "conditions": {"tsunami_only": True}, "cooldown_minutes": -1},
             "cooldown_minutes"),
        ],
    )  # fmt: skip
    def test_validation(
        self,
        client: Client,
        arango_db: StandardDatabase,
        alice: ArangoUser,
        payload: dict[str, Any],
        field: str,
    ) -> None:
        response = client.post(f"{API}/alert-rules", payload, content_type="application/json")
        assert response.status_code == 400
        fields = body(response)["error"]["details"]["fields"]
        assert any(key == field or key.startswith(field) for key in fields), fields

    def test_other_users_rules_are_invisible(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        mallory = create_user("mallory", password=PASSWORD)
        other = Client()
        other.force_login(mallory)
        assert body(other.get(f"{API}/alert-rules"))["results"] == []
        for method in ("get", "delete"):
            assert getattr(other, method)(f"{API}/alert-rules/{rule['id']}").status_code == 404
        response = other.patch(
            f"{API}/alert-rules/{rule['id']}", {"enabled": False}, content_type="application/json"
        )
        assert response.status_code == 404
        assert body(client.get(f"{API}/alert-rules/{rule['id']}"))["enabled"] is True

    def test_anonymous_rejected(self, client: Client, arango_db: StandardDatabase) -> None:
        assert client.get(f"{API}/alert-rules").status_code == 403

    def test_rule_limit(
        self,
        client: Client,
        arango_db: StandardDatabase,
        alice: ArangoUser,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("apps.alerts.repository.MAX_RULES_PER_USER", 2)
        create_rule(client)
        create_rule(client, name="second")
        response = client.post(
            f"{API}/alert-rules",
            {"name": "third", "conditions": {"tsunami_only": True}},
            content_type="application/json",
        )
        assert response.status_code == 409
        assert arango_db.collection(s.ALERT_RULES).count() == 2


class TestMatching:
    def test_live_event_matches_with_explanation(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        ingest(arango_db, recent_feature(0))

        feed = body(client.get(f"{API}/alerts/matches"))
        assert feed["total"] == 1
        match = feed["results"][0]
        assert match["rule_key"] == rule["id"]
        assert match["notify"] is True
        assert match["trigger"] == "inserted"
        reasons = match["explanation"]["reason"]
        assert any(r.startswith("magnitude ") and ">= 1" in r for r in reasons)
        assert any(r.startswith("distance ") and "<= 100 km" in r for r in reasons)
        assert match["rule_snapshot"]["name"] == "Near first event"

        assert body(client.get(f"{API}/alerts/unread-count"))["unread"] == 1
        graph = body(client.get(f"{API}/alerts/matched-events"))["results"]
        assert graph[0]["rule_id"] == rule["id"]
        assert body(client.get(f"{API}/alert-rules"))["results"][0]["match_count"] == 1

        client.post(f"{API}/alerts/matches/read", {}, content_type="application/json")
        assert body(client.get(f"{API}/alerts/unread-count"))["unread"] == 0

    def test_replays_and_revisions_never_duplicate_matches(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        create_rule(client)
        raw = recent_feature(0)
        ingest(arango_db, raw)
        ingest(arango_db, raw)
        revised = copy.deepcopy(raw)
        revised["properties"]["mag"] += 0.5
        revised["properties"]["updated"] += 60_000
        ingest(arango_db, revised)
        assert arango_db.collection(s.ALERT_MATCHES).count() == 1
        assert arango_db.collection(s.RULE_MATCHED_EVENT).count() == 1

    def test_revision_that_newly_satisfies_rule_creates_match(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        create_rule(client, conditions={"minimum_magnitude": 4.5, "center": CENTER,
                                        "radius_km": 100})  # fmt: skip
        raw = recent_feature(0, mag=2.0)
        ingest(arango_db, raw)
        assert arango_db.collection(s.ALERT_MATCHES).count() == 0
        upgraded = copy.deepcopy(raw)
        upgraded["properties"].update(mag=4.8, updated=raw["properties"]["updated"] + 60_000)
        ingest(arango_db, upgraded)
        (match,) = list(arango_db.collection(s.ALERT_MATCHES).all())
        assert match["trigger"] == "revised"
        assert match["changed_fields"] == ["magnitude"]
        assert "magnitude 4.8 >= 4.5" in match["explanation"]["reason"]

    def test_cooldown_suppresses_repeat_notifications(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        create_rule(client, conditions={"minimum_magnitude": 0.1})  # any two recent events
        ingest(arango_db, recent_feature(0), recent_feature(1))
        matches = sorted(arango_db.collection(s.ALERT_MATCHES).all(), key=lambda m: m["notify"])
        assert [m["notify"] for m in matches] == [False, True]
        assert matches[0]["suppressed_reason"] == "cooldown"

    @pytest.mark.parametrize(
        ("kwargs", "mode"),
        [
            ({"minutes_ago": 60 * 72}, "feed"),  # too old to notify
            ({}, "backfill"),  # historical imports never notify
        ],
    )
    def test_no_notification_for_historical_data(
        self,
        client: Client,
        arango_db: StandardDatabase,
        alice: ArangoUser,
        kwargs: dict[str, Any],
        mode: str,
    ) -> None:
        create_rule(client)
        ingest(arango_db, recent_feature(0, **kwargs), mode=mode)
        assert arango_db.collection(s.ALERT_MATCHES).count() == 0

    def test_rule_does_not_match_events_before_it_existed(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        arango_db.collection(s.ALERT_RULES).update(
            {"_key": rule["id"], "created_at": datetime.now(UTC).isoformat()[:23] + "Z"}
        )
        ingest(arango_db, recent_feature(0, minutes_ago=180))  # 3 h before the rule (> 1 h grace)
        assert arango_db.collection(s.ALERT_MATCHES).count() == 0

    def test_disabled_rule_does_not_match(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        create_rule(client, enabled=False)
        ingest(arango_db, recent_feature(0))
        assert arango_db.collection(s.ALERT_MATCHES).count() == 0

    def test_feed_is_private(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        create_rule(client)
        ingest(arango_db, recent_feature(0))
        bob = Client()
        bob.force_login(create_user("bob", password=PASSWORD))
        assert body(bob.get(f"{API}/alerts/matches"))["total"] == 0
        assert (
            body(bob.post(f"{API}/alerts/matches/read", {}, content_type="application/json"))[
                "marked_read"
            ]
            == 0
        )
        assert body(client.get(f"{API}/alerts/unread-count"))["unread"] == 1

    def test_delete_rule_keeps_match_history(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        rule = create_rule(client)
        ingest(arango_db, recent_feature(0))
        client.delete(f"{API}/alert-rules/{rule['id']}")
        assert arango_db.collection(s.ALERT_MATCHES).count() == 1
        assert arango_db.collection(s.RULE_MATCHED_EVENT).count() == 0
        assert body(client.get(f"{API}/alerts/matches"))["results"][0]["rule_snapshot"]["name"]

    def test_preview_explains_would_be_matches(
        self, client: Client, arango_db: StandardDatabase, alice: ArangoUser
    ) -> None:
        ingest(arango_db, recent_feature(0), mode="backfill")
        rule = create_rule(client)
        preview = body(client.get(f"{API}/alert-rules/{rule['id']}/preview"))
        assert preview["count"] == 1
        assert preview["would_match"][0]["explanation"]["matched"] is True
        assert arango_db.collection(s.ALERT_MATCHES).count() == 0  # preview has no side effects


def test_time_helpers_are_consistent() -> None:
    raw = recent_feature(0, minutes_ago=5)
    occurred = datetime.fromtimestamp(raw["properties"]["time"] / 1000, tz=UTC)
    assert timedelta(minutes=4) < datetime.now(UTC) - occurred < timedelta(minutes=6)
