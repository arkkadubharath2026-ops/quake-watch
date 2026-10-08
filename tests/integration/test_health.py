from __future__ import annotations

from arango.database import StandardDatabase
from django.test import Client

from apps.core.arango.schema import SCHEMA_VERSION


def test_live_is_always_ok(client: Client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["X-Request-ID"]


def test_ready_checks_dependencies(client: Client, arango_db: StandardDatabase) -> None:
    response = client.get("/health/ready")
    body = response.json()
    assert response.status_code == 200, body
    assert body["checks"]["arangodb"]["ok"] is True
    assert body["checks"]["schema"]["ok"] is True
    assert set(body["checks"]) == {"arangodb", "schema"}  # ArangoDB is the only dependency


def test_ready_reports_schema_drift(client: Client, arango_db: StandardDatabase) -> None:
    arango_db.collection("schema_meta").update({"_key": "current", "version": 0})
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["schema"] == {
            "ok": False,
            "applied": 0,
            "expected": SCHEMA_VERSION,
        }
    finally:
        arango_db.collection("schema_meta").update({"_key": "current", "version": SCHEMA_VERSION})


def test_inbound_request_id_propagates(client: Client) -> None:
    response = client.get("/health/live", HTTP_X_REQUEST_ID="trace-abc-12345")
    assert response["X-Request-ID"] == "trace-abc-12345"


def test_malformed_request_id_replaced(client: Client) -> None:
    response = client.get("/health/live", HTTP_X_REQUEST_ID="bad id with spaces\n")
    assert response["X-Request-ID"] != "bad id with spaces\n"
    assert len(response["X-Request-ID"]) == 32
