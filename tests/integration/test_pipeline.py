"""Ingestion pipeline against a real ArangoDB: idempotency, revisions, identity, transactions."""

from __future__ import annotations

import copy
import json
import threading
from typing import Any

import pytest
from arango.database import StandardDatabase

from apps.core.arango import Database
from apps.core.arango import schema as s
from apps.ingestion.normalizer import NormalizedRecord, normalize_feature, parse_feed
from apps.ingestion.pipeline import EventChange, IngestionPipeline
from tests.conftest import load_fixture


@pytest.fixture(scope="module")
def feed_doc() -> dict[str, Any]:
    return json.loads(load_fixture("usgs/all_day.geojson"))  # type: ignore[no-any-return]


def feature(feed_doc: dict[str, Any], index: int = 0, **prop_overrides: Any) -> dict[str, Any]:
    raw = copy.deepcopy(feed_doc["features"][index])
    raw["properties"].update(prop_overrides)
    return raw


def record(raw: dict[str, Any]) -> NormalizedRecord:
    result = normalize_feature(raw)
    assert isinstance(result, NormalizedRecord), result
    return result


def count(db: StandardDatabase, collection: str, aql_filter: str = "") -> int:
    query = f"RETURN LENGTH(FOR d IN {collection} {aql_filter} RETURN 1)"  # test-only literal
    return int(next(iter(db.aql.execute(query))))  # type: ignore[arg-type]


def revisions(db: StandardDatabase, key: str) -> list[dict[str, Any]]:
    cursor = db.aql.execute(
        "FOR r IN event_revisions FILTER r.event_key == @k SORT r.revision_number RETURN r",
        bind_vars={"k": key},
    )
    return list(cursor)  # type: ignore[arg-type]


class TestFullFeed:
    def test_initial_ingest_and_idempotent_replay(self, arango_db: StandardDatabase) -> None:
        parsed = parse_feed(load_fixture("usgs/all_day.geojson"))
        n = len(parsed.records)

        first = IngestionPipeline(arango_db).ingest(parsed.records, parsed.rejected)
        assert first.counts["inserted"] == n
        assert count(arango_db, s.EVENTS) == n
        assert count(arango_db, s.EVENT_REVISIONS) == n
        assert count(arango_db, s.RAW_PAYLOADS) == n
        assert count(arango_db, s.EVENT_IN_REGION) == n
        assert count(arango_db, s.EVENT_REPORTED_BY_NETWORK) == n
        assert count(arango_db, s.REGIONS) > 5

        replay = IngestionPipeline(arango_db).ingest(parsed.records, parsed.rejected)
        assert replay.counts["unchanged"] == n
        assert replay.counts["inserted"] == replay.counts["revised"] == 0
        assert count(arango_db, s.EVENTS) == n
        assert count(arango_db, s.EVENT_REVISIONS) == n  # no duplicate revisions

    def test_first_revision_snapshot_matches_canonical(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        rec = record(feature(feed_doc))
        IngestionPipeline(arango_db).ingest([rec])
        event = arango_db.collection(s.EVENTS).get(rec.event.key)
        (rev,) = revisions(arango_db, rec.event.key)
        assert rev["kind"] == "created"
        assert rev["state"] == rec.event.to_state()
        for field, value in rec.event.to_state().items():
            assert event[field] == value
        assert event["coordinates"] == [rec.event.longitude, rec.event.latitude]
        assert event["derived"]["region_name"] == "California"
        assert event["derived"]["first_seen_via"] == "feed"


class TestRevisions:
    def test_meaningful_change_appends_revision(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        base = feature(feed_doc)
        IngestionPipeline(arango_db).ingest([record(base)])
        props = base["properties"]
        newer = feature(
            feed_doc, mag=props["mag"] + 0.4, status="reviewed", updated=props["updated"] + 60_000
        )
        stats = IngestionPipeline(arango_db).ingest([record(newer)])

        assert stats.counts["revised"] == 1
        key = f"usgs_{base['id']}"
        event = arango_db.collection(s.EVENTS).get(key)
        assert event["revision_count"] == 2
        assert event["magnitude"] == pytest.approx(props["mag"] + 0.4)
        rev = revisions(arango_db, key)[-1]
        assert rev["revision_number"] == 2
        assert rev["changed_fields"] == ["magnitude", "status"]
        assert rev["before"]["status"] == props["status"]
        assert rev["after"]["status"] == "reviewed"

    def test_untracked_change_refreshes_without_revision(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        base = feature(feed_doc)
        IngestionPipeline(arango_db).ingest([record(base)])
        newer = feature(feed_doc, felt=42, updated=base["properties"]["updated"] + 1000)
        stats = IngestionPipeline(arango_db).ingest([record(newer)])
        assert stats.counts["refreshed"] == 1
        key = f"usgs_{base['id']}"
        assert arango_db.collection(s.EVENTS).get(key)["felt"] == 42
        assert len(revisions(arango_db, key)) == 1

    def test_out_of_order_update_is_ignored(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        base = feature(feed_doc)
        IngestionPipeline(arango_db).ingest([record(base)])
        older = feature(feed_doc, mag=9.0, updated=base["properties"]["updated"] - 60_000)
        stats = IngestionPipeline(arango_db).ingest([record(older)])
        assert stats.counts["stale"] == 1
        event = arango_db.collection(s.EVENTS).get(f"usgs_{base['id']}")
        assert event["magnitude"] == base["properties"]["mag"]


class TestIdentity:
    def test_preferred_id_change_keeps_one_canonical_record(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        original = feature(feed_doc)
        old_id = original["id"]
        IngestionPipeline(arango_db).ingest([record(original)])

        rekeyed = feature(
            feed_doc, ids=f",{old_id},us7000zzzz,", updated=original["properties"]["updated"] + 1
        )
        rekeyed["id"] = "us7000zzzz"
        stats = IngestionPipeline(arango_db).ingest([record(rekeyed)])

        assert stats.counts["revised"] == 1
        assert count(arango_db, s.EVENTS) == 1
        event = arango_db.collection(s.EVENTS).get(f"usgs_{old_id}")
        assert event["source_event_id"] == "us7000zzzz"
        assert sorted(event["associated_ids"]) == sorted([old_id, "us7000zzzz"])
        assert revisions(arango_db, event["_key"])[-1]["changed_fields"] == ["source_event_id"]

    def test_two_records_later_associated_are_merged(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        a, b = feature(feed_doc, 0), feature(feed_doc, 1)
        IngestionPipeline(arango_db).ingest([record(a), record(b)])
        merged = feature(feed_doc, 1, ids=f",{a['id']},{b['id']},")
        merged["properties"]["updated"] += 1
        stats = IngestionPipeline(arango_db).ingest([record(merged)])

        assert stats.counts["merged"] == 1
        live = count(arango_db, s.EVENTS, "FILTER d.merged_into == null")
        assert live == 1
        loser = arango_db.collection(s.EVENTS).get(f"usgs_{a['id']}")
        assert loser["merged_into"] == f"usgs_{b['id']}"

    def test_id_flip_back_to_merged_record_id_does_not_violate_uniqueness(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        a, b = feature(feed_doc, 0), feature(feed_doc, 1)
        IngestionPipeline(arango_db).ingest([record(a), record(b)])
        ids = f",{a['id']},{b['id']},"
        step1 = feature(feed_doc, 1, ids=ids)
        step1["properties"]["updated"] += 1
        IngestionPipeline(arango_db).ingest([record(step1)])  # a merged into b
        step2 = feature(feed_doc, 1, ids=ids)
        step2["id"] = a["id"]  # USGS prefers a's id again
        step2["properties"]["updated"] += 2
        stats = IngestionPipeline(arango_db).ingest([record(step2)])
        assert stats.counts["revised"] == 1
        live = arango_db.collection(s.EVENTS).get(f"usgs_{b['id']}")
        assert live["source_event_id"] == a["id"]


class TestDeadLetters:
    def test_rejected_records_are_dead_lettered_and_resolved(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        bad = feature(feed_doc, status="bogus")
        rejected = normalize_feature(bad)
        pipeline = IngestionPipeline(arango_db)
        pipeline.ingest([], [rejected])  # type: ignore[list-item]
        pipeline.ingest([], [rejected])  # type: ignore[list-item]
        (letter,) = list(arango_db.collection(s.DEAD_LETTERS).all())
        assert letter["reason"] == "unknown_status"
        assert letter["retry_count"] == 2
        assert letter["resolved_at"] is None

        stats = pipeline.ingest([record(feature(feed_doc))])
        assert stats.counts["dead_letters_resolved"] == 1
        (letter,) = list(arango_db.collection(s.DEAD_LETTERS).all())
        assert letter["resolved_at"] is not None


class RecordingObserver:
    write_collections = (s.AUDIT_LOG,)
    read_collections: tuple[str, ...] = ()

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.seen: list[str] = []

    def on_event(self, txn: Database, change: EventChange) -> int:
        txn.collection(s.AUDIT_LOG).insert({"_key": change.event["_key"], "at": change.observed_at})
        self.seen.append(change.kind)
        if self.fail:
            raise RuntimeError("observer failed")
        return 1


class TestTransactionsAndObservers:
    def test_observer_writes_in_same_transaction(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        observer = RecordingObserver()
        stats = IngestionPipeline(arango_db, observers=[observer]).ingest(
            [record(feature(feed_doc))]
        )
        assert observer.seen == ["inserted"]
        assert stats.counts["observer_effects"] == 1
        assert count(arango_db, s.AUDIT_LOG) == 1

    def test_failing_record_is_rolled_back_and_dead_lettered_without_aborting_batch(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        bad, good = record(feature(feed_doc, 0)), record(feature(feed_doc, 1))

        class FailFor(RecordingObserver):
            def on_event(self, txn: Database, change: EventChange) -> int:
                if change.event["_key"] == bad.event.key:
                    raise RuntimeError("observer failed")
                return super().on_event(txn, change)

        stats = IngestionPipeline(arango_db, observers=[FailFor()]).ingest([bad, good])

        assert stats.counts["failed"] == 1
        assert stats.counts["inserted"] == 1
        assert arango_db.collection(s.EVENTS).get(bad.event.key) is None  # fully rolled back
        assert arango_db.collection(s.EVENTS).get(good.event.key) is not None
        assert count(arango_db, s.EVENT_IDENTITIES, f"FILTER d.event_key == '{bad.event.key}'") == 0
        (letter,) = list(arango_db.collection(s.DEAD_LETTERS).all())
        assert letter["reason"] == "apply_failed"
        assert "observer failed" in letter["detail"]

    @pytest.mark.parametrize("round_", range(5))
    def test_concurrent_ingest_of_same_new_event_creates_one_record(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any], round_: int
    ) -> None:
        rec = record(feature(feed_doc))
        errors: list[BaseException] = []

        def run() -> None:
            try:
                IngestionPipeline(arango_db).ingest([rec])
            except BaseException as exc:  # noqa: BLE001 - asserted below
                errors.append(exc)

        barrier_threads = 8
        threads = [threading.Thread(target=run) for _ in range(barrier_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert count(arango_db, s.EVENTS) == 1
        assert count(arango_db, s.EVENT_REVISIONS) == 1


class TestIdentityClaims:
    @pytest.mark.parametrize("round_", range(5))
    def test_concurrent_writers_with_different_preferred_ids_create_one_event(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any], round_: int
    ) -> None:
        """Reviewer scenario: feed sees preferred id a, backfill sees b, for the same event."""
        base = feature(feed_doc)
        ids = f",{base['id']},us7000race,"
        as_a = feature(feed_doc, ids=ids)
        as_b = feature(feed_doc, ids=ids)
        as_b["id"] = "us7000race"
        records = [record(as_a), record(as_b)]
        barrier = threading.Barrier(len(records))
        errors: list[BaseException] = []

        def run(rec: NormalizedRecord) -> None:
            barrier.wait()
            try:
                IngestionPipeline(arango_db).ingest([rec])
            except BaseException as exc:  # noqa: BLE001 - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(r,)) for r in records]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert count(arango_db, s.EVENTS, "FILTER d.merged_into == null") == 1
        assert count(arango_db, s.EVENT_REVISIONS, "FILTER d.kind == 'created'") == 1
        claims = list(arango_db.collection(s.EVENT_IDENTITIES).all())
        assert len(claims) == 2
        assert len({c["event_key"] for c in claims}) == 1

    def test_id_dropped_from_ids_still_resolves_to_same_event(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        base = feature(feed_doc)
        first = feature(feed_doc, ids=f",{base['id']},us7000drop,")
        IngestionPipeline(arango_db).ingest([record(first)])
        # USGS stops listing the original id and prefers the other one...
        second = feature(feed_doc, ids=",us7000drop,", updated=base["properties"]["updated"] + 1)
        second["id"] = "us7000drop"
        IngestionPipeline(arango_db).ingest([record(second)])
        # ...then publishes a record under the dropped id again.
        third = feature(feed_doc, ids=f",{base['id']},", updated=base["properties"]["updated"] + 2)
        stats = IngestionPipeline(arango_db).ingest([record(third)])
        assert stats.counts["failed"] == 0
        assert count(arango_db, s.EVENTS) == 1

    def test_merge_repoints_claims_chains_and_removes_loser_edges(
        self, arango_db: StandardDatabase, feed_doc: dict[str, Any]
    ) -> None:
        a, b, c = feature(feed_doc, 0), feature(feed_doc, 1), feature(feed_doc, 2)
        IngestionPipeline(arango_db).ingest([record(a), record(b), record(c)])
        step1 = feature(feed_doc, 1, ids=f",{a['id']},{b['id']},")
        step1["properties"]["updated"] += 1
        IngestionPipeline(arango_db).ingest([record(step1)])  # a -> b
        step2 = feature(feed_doc, 2, ids=f",{a['id']},{b['id']},{c['id']},")
        step2["properties"]["updated"] += 1
        IngestionPipeline(arango_db).ingest([record(step2)])  # b -> c (and chain a -> c)

        live_key = f"usgs_{c['id']}"
        assert count(arango_db, s.EVENTS, "FILTER d.merged_into == null") == 1
        for loser in (a, b):
            doc = arango_db.collection(s.EVENTS).get(f"usgs_{loser['id']}")
            assert doc["merged_into"] == live_key
            assert arango_db.collection(s.EVENT_IN_REGION).get(doc["_key"]) is None
        claim_targets = {d["event_key"] for d in arango_db.collection(s.EVENT_IDENTITIES).all()}
        assert claim_targets == {live_key}
