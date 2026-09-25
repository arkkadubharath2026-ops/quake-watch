"""Index benchmark harness (ESD §16 "Performance", PRD "index before/after benchmark").

Seeds a dedicated ``*_test`` database with a synthetic but schema-valid catalogue, then times
the same named workloads twice: with the declared ``qw_*`` indexes and with the non-essential
ones dropped. Workloads are passed in as data (AQL + bind factory) by the caller, so this module
knows nothing about the domain apps.

The synthetic data follows real catalogue shape, not real events:

* ~270 events/day (the order of the USGS all-magnitude feed), so a larger dataset covers a longer
  period rather than a denser one;
* Gutenberg-Richter magnitudes per reporting tier (~15 % M2.5+, ~4 % M4.5+); 70 % of
  epicentres in a handful of seismic zones and the rest uniform; exponential depths;
* 1-4 revisions per event (created + meaningful updates) like the live revision history.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from arango.database import StandardDatabase

from apps.core.arango import schema as s
from apps.core.arango.client import drop_database, ensure_database, sync
from apps.core.arango.migrate import apply_schema
from apps.core.arango.query import explain, indexes_used
from apps.core.clock import to_iso

EVENTS_PER_DAY = 270
BATCH = 5000
# Indexes that exist only to accelerate reads. Unique/identity and TTL indexes are integrity
# constraints and stay in place for the "without indexes" run.
PERFORMANCE_INDEXES: dict[str, tuple[str, ...]] = {
    s.EVENTS: ("qw_events_geo", "qw_events_occurred_at", "qw_events_magnitude"),
    s.EVENT_REVISIONS: ("qw_revisions_observed_at", "qw_revisions_changed_fields"),
}
# The revision lookup's only index is the unique (event_key, revision_number) constraint; the
# "without" run replaces it with nothing so the lookup shows its cost honestly.
CONSTRAINT_INDEXES_DROPPED: dict[str, tuple[str, ...]] = {
    s.EVENT_REVISIONS: ("qw_revisions_event_rev",),
}
ZONES = (  # (lat, lon, spread in degrees): Alaska, California, Japan, Chile, Indonesia, Italy
    (61.0, -150.0, 3.0),
    (36.0, -119.0, 2.0),
    (37.0, 141.0, 3.0),
    (-30.0, -71.0, 4.0),
    (-4.0, 122.0, 5.0),
    (42.5, 13.0, 1.5),
)
NETWORKS = ("ak", "ci", "us", "nc", "hv", "nn", "uw", "tx")
TRACKED = ("magnitude", "status", "latitude", "longitude", "depth_km", "place", "alert")


@dataclass(frozen=True, slots=True)
class Workload:
    name: str
    description: str
    aql: str
    binds: Callable[[BenchContext], dict[str, Any]]
    full_count: bool = False  # the list API asks for fullCount, which defeats early LIMIT exit


@dataclass(frozen=True, slots=True)
class BenchContext:
    """What a workload may parameterise itself with (latest time, a random real key, ...)."""

    newest: datetime
    rng: random.Random
    event_keys: tuple[str, ...]

    def some_key(self) -> str:
        return self.rng.choice(self.event_keys)


@dataclass(slots=True)
class Timing:
    workload: str
    size: int
    indexed: bool
    runs: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    rows: int
    scanned_full: int
    scanned_index: int
    indexes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workload": self.workload,
            "size": self.size,
            "indexed": self.indexed,
            "runs": self.runs,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "mean_ms": self.mean_ms,
            "rows": self.rows,
            "scanned_full": self.scanned_full,
            "scanned_index": self.scanned_index,
            "indexes": self.indexes,
        }


# ---- synthetic catalogue --------------------------------------------------------------------
def _hash(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def _magnitude(rng: random.Random) -> float:
    """Gutenberg-Richter (b = 1) per reporting tier, mixed like the USGS all-magnitude feed.

    Dense regional networks report down to M0.5, the national network from about M2.5 and the
    global network from about M4.5, so the catalogue is ~15 % M2.5+ and ~4 % M4.5+.
    """
    tier = rng.random()
    floor = 0.5 if tier < 0.86 else 2.5 if tier < 0.96 else 4.5
    return round(min(9.1, floor - math.log10(1.0 - rng.random())), 1)


def _location(rng: random.Random) -> tuple[float, float]:
    if rng.random() < 0.7:
        lat, lon, spread = rng.choice(ZONES)
        lat = max(-89.9, min(89.9, rng.gauss(lat, spread)))
        lon = ((rng.gauss(lon, spread) + 180.0) % 360.0) - 180.0
    else:
        lat = math.degrees(math.asin(rng.uniform(-1.0, 1.0)))  # uniform on the sphere
        lon = rng.uniform(-180.0, 180.0)
    return round(lat, 4), round(lon, 4)


def synthetic_catalogue(
    size: int, newest: datetime, seed: int = 20260925
) -> Iterator[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Yield ``(event, revisions)`` pairs; deterministic for a given seed."""
    rng = random.Random(seed)  # noqa: S311 - reproducible synthetic data, not security
    span = timedelta(days=max(1.0, size / EVENTS_PER_DAY))
    for i in range(size):
        occurred = newest - span * rng.random()
        lat, lon = _location(rng)
        mag = _magnitude(rng)
        network = rng.choice(NETWORKS)
        source_id = f"{network}bench{i:07d}"
        key = f"usgs_{source_id}"
        revisions_n = rng.choices((1, 2, 3, 4), weights=(45, 35, 15, 5))[0]
        reviewed = revisions_n > 1 and rng.random() < 0.8
        significance = int(mag * 100 * (1 + rng.random())) if mag >= 2.5 else int(mag * 10)
        alert = None
        if mag >= 6.5:
            alert = "orange" if mag >= 7.5 else "yellow" if mag >= 7 else "green"
        state: dict[str, Any] = {
            "associated_ids": [source_id],
            "event_type": "earthquake" if rng.random() < 0.97 else "quarry blast",
            "magnitude": mag,
            "magnitude_type": "ml" if mag < 4 else "mww",
            "place": f"{rng.randint(1, 120)} km of synthetic zone {i % 97}",
            "occurred_at": to_iso(occurred),
            "source_updated_at": to_iso(occurred + timedelta(minutes=3)),
            "latitude": lat,
            "longitude": lon,
            "depth_km": round(min(700.0, rng.expovariate(1 / 25)), 2),
            "felt": rng.randint(0, 500) if mag >= 3 and rng.random() < 0.3 else None,
            "cdi": None,
            "mmi": None,
            "alert": alert,
            "status": "automatic",
            "tsunami": mag >= 7 and rng.random() < 0.5,
            "significance": significance,
            "network": network,
            "detail_url": None,
            "event_page_url": None,
            "station_count": rng.randint(4, 120),
            "min_station_distance_deg": round(rng.uniform(0.01, 5), 3),
            "rms_travel_time_residual": round(rng.uniform(0.05, 1.5), 3),
            "azimuthal_gap_deg": round(rng.uniform(20, 300), 1),
            "products": ["origin", "phase-data"],
            "contributors": [network],
        }
        revisions: list[dict[str, Any]] = []
        observed = occurred + timedelta(minutes=rng.randint(2, 20))
        for number in range(1, revisions_n + 1):
            if number == 1:
                kind, changed, before, after = "created", list(TRACKED), {}, {}
            else:
                kind = "updated"
                field_name = "status" if (reviewed and number == revisions_n) else "magnitude"
                before = {field_name: state[field_name]}
                if field_name == "status":
                    state["status"] = "reviewed"
                else:
                    state["magnitude"] = round(
                        max(0.5, state["magnitude"] + rng.choice((-0.1, 0.1))), 1
                    )
                after = {field_name: state[field_name]}
                changed = [field_name]
                observed += timedelta(minutes=rng.randint(10, 600))
                state["source_updated_at"] = to_iso(observed - timedelta(minutes=1))
            revisions.append(
                {
                    "_key": f"{key}_r{number}",
                    "event_key": key,
                    "revision_number": number,
                    "kind": kind,
                    "observed_at": to_iso(observed),
                    "source_updated_at": state["source_updated_at"],
                    "changed_fields": changed,
                    "before": before,
                    "after": after,
                    "state": dict(state),
                    "payload_hash": _hash(key, number),
                    "policy_version": 1,
                    "ingestion_run_id": None,
                }
            )
        first_seen = revisions[0]["observed_at"]
        event = {
            "_key": key,
            "source": "USGS",
            "source_event_id": source_id,
            **state,
            "coordinates": [lon, lat],
            "derived": {"region_name": f"Synthetic zone {i % 97}", "first_seen_via": "benchmark"},
            "first_seen_at": first_seen,
            "last_seen_at": revisions[-1]["observed_at"],
            "last_ingested_at": revisions[-1]["observed_at"],
            "revision_count": revisions_n,
            "payload_hash": _hash(key, revisions_n),
            "schema_version": 1,
            "revision_policy_version": 1,
            "merged_into": None,
        }
        yield event, revisions


# ---- database lifecycle ------------------------------------------------------------------
def prepare_database(name: str) -> StandardDatabase:
    """Recreate the benchmark database from scratch with the full declared schema."""
    if not name.endswith("_test"):
        raise ValueError("benchmarks only run against a disposable *_test database")
    drop_database(name)
    db = ensure_database(name)
    apply_schema(db)
    return db


def seed(db: StandardDatabase, size: int, newest: datetime) -> tuple[str, ...]:
    """Bulk-insert ``size`` events (plus revisions); return the event keys."""
    events, revisions, keys = [], [], []
    for event, event_revisions in synthetic_catalogue(size, newest):
        events.append(event)
        revisions.extend(event_revisions)
        keys.append(event["_key"])
        if len(events) >= BATCH:
            _import(db, events, revisions)
            events, revisions = [], []
    if events:
        _import(db, events, revisions)
    return tuple(keys)


def _import(db: StandardDatabase, events: list[Any], revisions: list[Any]) -> None:
    for collection, docs in ((s.EVENTS, events), (s.EVENT_REVISIONS, revisions)):
        result = sync(db.collection(collection).import_bulk(docs, halt_on_error=True))
        if isinstance(result, dict) and result.get("errors"):
            raise RuntimeError(f"benchmark seed rejected by {collection}: {result}")


def drop_performance_indexes(db: StandardDatabase) -> list[str]:
    dropped: list[str] = []
    for mapping in (PERFORMANCE_INDEXES, CONSTRAINT_INDEXES_DROPPED):
        for collection_name, names in mapping.items():
            collection = db.collection(collection_name)
            for index in sync(collection.indexes()):
                if index.get("name") in names:
                    collection.delete_index(str(index["id"]).split("/")[-1])
                    dropped.append(str(index["name"]))
    return dropped


def restore_indexes(db: StandardDatabase) -> None:
    apply_schema(db)


# ---- timing -------------------------------------------------------------------------------
def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[rank]


def _stat(stats: dict[str, Any], snake: str, camel: str) -> int:
    return int(stats.get(snake, stats.get(camel, 0)) or 0)


def measure(
    db: StandardDatabase,
    workload: Workload,
    ctx: BenchContext,
    *,
    size: int,
    indexed: bool,
    runs: int,
    warmup: int = 2,
) -> Timing:
    """Run a workload ``warmup + runs`` times (fresh binds each run) and summarise latencies."""
    samples: list[float] = []
    rows = scanned_full = scanned_index = 0
    for i in range(warmup + runs):
        binds = workload.binds(ctx)
        started = time.perf_counter()
        cursor = sync(
            db.aql.execute(
                workload.aql,
                bind_vars=binds,
                batch_size=1000,
                full_count=workload.full_count or None,
            )
        )
        result = list(cursor)
        elapsed = (time.perf_counter() - started) * 1000
        if i >= warmup:
            samples.append(elapsed)
            stats = cursor.statistics() or {}
            rows = len(result)
            scanned_full = max(scanned_full, _stat(stats, "scanned_full", "scannedFull"))
            scanned_index = max(scanned_index, _stat(stats, "scanned_index", "scannedIndex"))
    plan = explain(db, workload.aql, workload.binds(ctx))
    return Timing(
        workload=workload.name,
        size=size,
        indexed=indexed,
        runs=runs,
        p50_ms=round(statistics.median(samples), 2),
        p95_ms=round(_percentile(samples, 95), 2),
        mean_ms=round(statistics.fmean(samples), 2),
        rows=rows,
        scanned_full=scanned_full,
        scanned_index=scanned_index,
        indexes=sorted(set(indexes_used(plan))),
    )


def run_size(
    name: str,
    size: int,
    workloads: list[Workload],
    *,
    newest: datetime,
    runs: int,
    log: Callable[[str], None] = lambda _msg: None,
) -> list[Timing]:
    """Seed one dataset size and time every workload with and without the read indexes."""
    db = prepare_database(name)
    started = time.perf_counter()
    keys = seed(db, size, newest)
    log(f"seeded {size:,} events in {time.perf_counter() - started:.1f}s")
    rng = random.Random(size)  # noqa: S311 - reproducible bind values, not security
    ctx = BenchContext(newest=newest, rng=rng, event_keys=keys)
    results: list[Timing] = []
    for indexed in (True, False):
        if not indexed:
            dropped = drop_performance_indexes(db)
            log(f"dropped indexes: {', '.join(dropped)}")
        for workload in workloads:
            ctx.rng.seed(f"{size}:{workload.name}")  # same binds for both index states
            timing = measure(db, workload, ctx, size=size, indexed=indexed, runs=runs)
            log(
                f"{'with' if indexed else 'without':7s} {workload.name:28s} "
                f"p50 {timing.p50_ms:8.2f} ms  p95 {timing.p95_ms:8.2f} ms  "
                f"scanned full/index {timing.scanned_full}/{timing.scanned_index}"
            )
            results.append(timing)
    restore_indexes(db)
    return results
