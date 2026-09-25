"""Real-ArangoDB tests for schema reconciliation, validation rules and transactions."""

from __future__ import annotations

import contextlib
import threading

import pytest
from arango.database import StandardDatabase
from arango.exceptions import DocumentInsertError

from apps.core.arango import schema as s
from apps.core.arango.migrate import apply_schema
from apps.core.arango.query import ERR_UNIQUE_CONSTRAINT, run_query
from apps.core.arango.transactions import run_in_transaction

VALID_EVENT = {
    "_key": "usgs_test1",
    "source": "USGS",
    "source_event_id": "test1",
    "associated_ids": ["test1"],
    "event_type": "earthquake",
    "magnitude": 4.2,
    "magnitude_type": "mb",
    "place": "10 km N of Somewhere, Chile",
    "occurred_at": "2026-09-21T00:00:00.000Z",
    "source_updated_at": "2026-09-21T00:04:00.000Z",
    "latitude": -33.0,
    "longitude": -70.0,
    "depth_km": 10.0,
    "coordinates": [-70.0, -33.0],
    "status": "automatic",
    "tsunami": False,
    "alert": None,
    "first_seen_at": "2026-09-21T00:05:00.000Z",
    "last_seen_at": "2026-09-21T00:05:00.000Z",
    "last_ingested_at": "2026-09-21T00:05:00.000Z",
    "revision_count": 1,
    "payload_hash": "a" * 64,
    "schema_version": 1,
    "revision_policy_version": 1,
}


class TestMigrations:
    def test_reapply_is_noop(self, arango_db: StandardDatabase) -> None:
        report = apply_schema(arango_db)
        assert not report.changed

    def test_all_declared_collections_and_indexes_exist(self, arango_db: StandardDatabase) -> None:
        for spec in s.COLLECTIONS:
            assert arango_db.has_collection(spec.name), spec.name
            names = {ix.get("name") for ix in arango_db.collection(spec.name).indexes()}
            for ix in spec.indexes:
                assert ix.name in names, f"{spec.name}.{ix.name}"
        assert arango_db.has_graph(s.GRAPH_NAME)
        assert s.EVENTS_SEARCH_VIEW in {v["name"] for v in arango_db.views()}

    def test_drifted_index_is_replaced_and_stray_dropped(self, arango_db: StandardDatabase) -> None:
        events = arango_db.collection(s.EVENTS)
        drifted = next(ix for ix in events.indexes() if ix.get("name") == "qw_events_magnitude")
        events.delete_index(drifted["id"])
        events.add_index(
            {
                "type": "persistent",
                "fields": ["magnitude", "depth_km"],
                "name": "qw_events_magnitude",
            }
        )
        events.add_index({"type": "persistent", "fields": ["network"], "name": "qw_stray_index"})

        report = apply_schema(arango_db)

        assert "events.qw_events_magnitude" in report.replaced_indexes
        assert "events.qw_stray_index" in report.dropped_indexes
        current = {ix["name"]: ix for ix in events.indexes()}
        assert current["qw_events_magnitude"]["fields"] == ["magnitude", "_key"]
        assert "qw_stray_index" not in current

    def test_missing_stored_values_count_as_drift(self, arango_db: StandardDatabase) -> None:
        events = arango_db.collection(s.EVENTS)
        declared = next(ix for ix in events.indexes() if ix.get("name") == "qw_events_occurred_at")
        assert declared["storedValues"] == ["merged_into", "magnitude"]
        events.delete_index(declared["id"])
        events.add_index(
            {
                "type": "persistent",
                "fields": ["occurred_at", "_key"],
                "name": "qw_events_occurred_at",
            }
        )

        report = apply_schema(arango_db)

        assert report.replaced_indexes == ["events.qw_events_occurred_at"]
        current = {ix["name"]: ix for ix in events.indexes()}
        assert current["qw_events_occurred_at"]["storedValues"] == ["merged_into", "magnitude"]
        assert apply_schema(arango_db).replaced_indexes == []  # idempotent once repaired


class TestDataMigrations:
    def test_v2_builds_identity_claims_following_merge_chains(
        self, arango_db: StandardDatabase
    ) -> None:
        events = arango_db.collection(s.EVENTS)
        live = {**VALID_EVENT, "associated_ids": ["test1", "x1"]}
        middle = {
            **VALID_EVENT,
            "_key": "usgs_mid",
            "source_event_id": "mid",
            "associated_ids": ["mid", "x2"],
            "merged_into": "usgs_old",
        }
        old = {
            **VALID_EVENT,
            "_key": "usgs_old",
            "source_event_id": "old",
            "associated_ids": ["old"],
            "merged_into": "usgs_test1",
        }
        for doc in (live, middle, old):
            events.insert(doc)
        arango_db.collection(s.SCHEMA_META).update({"_key": "current", "version": 1})

        report = apply_schema(arango_db)

        assert report.data_migrations == ["v2:identity_claims (5 documents)"]
        claims = {c["_key"]: c["event_key"] for c in arango_db.collection(s.EVENT_IDENTITIES)}
        expected = ("usgs_test1", "usgs_x1", "usgs_mid", "usgs_x2", "usgs_old")
        assert claims == dict.fromkeys(expected, "usgs_test1")
        assert not apply_schema(arango_db).changed  # migration ran exactly once


class TestCollectionRules:
    def test_valid_event_accepted(self, arango_db: StandardDatabase) -> None:
        arango_db.collection(s.EVENTS).insert(VALID_EVENT)
        assert arango_db.collection(s.EVENTS).get("usgs_test1")["magnitude"] == 4.2

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("latitude", 123.0),
            ("status", "bogus"),
            ("occurred_at", "2026-09-21 00:00"),
            ("alert", "purple"),
            ("payload_hash", "not-a-hash"),
            ("associated_ids", []),
            ("event_type", ""),
        ],
    )
    def test_invalid_event_rejected_by_db(
        self, arango_db: StandardDatabase, field: str, value: object
    ) -> None:
        with pytest.raises(DocumentInsertError):
            arango_db.collection(s.EVENTS).insert({**VALID_EVENT, field: value})

    def test_source_identity_is_unique(self, arango_db: StandardDatabase) -> None:
        events = arango_db.collection(s.EVENTS)
        events.insert(VALID_EVENT)
        with pytest.raises(DocumentInsertError) as exc_info:
            events.insert({**VALID_EVENT, "_key": "different_key"})
        assert exc_info.value.error_code == ERR_UNIQUE_CONSTRAINT


class TestTransactions:
    def test_commit_writes_all_collections(self, arango_db: StandardDatabase) -> None:
        def work(txn):  # type: ignore[no-untyped-def]
            txn.collection(s.EVENTS).insert(VALID_EVENT)
            txn.collection(s.AUDIT_LOG).insert({"_key": "a1", "at": "x"})
            return "done"

        result = run_in_transaction(arango_db, work, write=[s.EVENTS, s.AUDIT_LOG])
        assert result == "done"
        assert arango_db.collection(s.EVENTS).count() == 1
        assert arango_db.collection(s.AUDIT_LOG).count() == 1

    def test_exception_rolls_back_everything(self, arango_db: StandardDatabase) -> None:
        def work(txn):  # type: ignore[no-untyped-def]
            txn.collection(s.AUDIT_LOG).insert({"_key": "a1", "at": "x"})
            txn.collection(s.EVENTS).insert({**VALID_EVENT, "latitude": 999})  # rejected

        with pytest.raises(DocumentInsertError):
            run_in_transaction(arango_db, work, write=[s.EVENTS, s.AUDIT_LOG])
        assert arango_db.collection(s.AUDIT_LOG).count() == 0
        assert arango_db.collection(s.EVENTS).count() == 0

    def test_concurrent_conflicting_updates_are_retried(self, arango_db: StandardDatabase) -> None:
        """Two writers increment the same doc; conflict retries must not lose an update."""
        arango_db.collection(s.AUDIT_LOG).insert({"_key": "counter", "at": "x", "n": 0})
        barrier = threading.Barrier(2)

        def work(txn):  # type: ignore[no-untyped-def]
            doc = txn.collection(s.AUDIT_LOG).get("counter")
            with contextlib.suppress(threading.BrokenBarrierError):  # retries run solo
                barrier.wait(timeout=2)
            txn.collection(s.AUDIT_LOG).update({"_key": "counter", "n": doc["n"] + 1})

        errors: list[BaseException] = []

        def runner() -> None:
            try:
                run_in_transaction(arango_db, work, write=[s.AUDIT_LOG], max_attempts=6)
            except BaseException as exc:  # noqa: BLE001 - surfaced via assertion below
                errors.append(exc)

        threads = [threading.Thread(target=runner) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert arango_db.collection(s.AUDIT_LOG).get("counter")["n"] == 2


class TestQueryRunner:
    def test_full_count_and_timing(self, arango_db: StandardDatabase, clean_metrics: None) -> None:
        for i in range(5):
            arango_db.collection(s.AUDIT_LOG).insert({"_key": f"k{i}", "at": f"{i}"})
        result = run_query(
            arango_db,
            "test_limit",
            "FOR d IN @@c SORT d.at LIMIT 2 RETURN d._key",
            {"@c": s.AUDIT_LOG},
            full_count=True,
        )
        assert result.rows == ["k0", "k1"]
        assert result.full_count == 5
        assert result.duration_ms >= 0
