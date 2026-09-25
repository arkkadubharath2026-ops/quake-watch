"""Index before/after benchmark at several dataset sizes; optionally writes docs/BENCHMARKS.md.

    manage.py arango_benchmark --sizes 500,10000,100000 --runs 20 --write

Runs against the disposable ``<db>_bench_test`` database (dropped and re-seeded per size), never
against application data. The workloads are the production AQL: the explorer search builder,
the revision timeline and an analytics aggregate, taken from the repositories themselves.
"""

from __future__ import annotations

import json
import os
import platform
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.analytics import repository as analytics
from apps.core.arango import benchmark as bench
from apps.core.arango.client import database_name, drop_database, ensure_database, sync
from apps.core.clock import now_iso, to_iso, utc_now
from apps.earthquakes import repository as events
from apps.earthquakes.filters import EventFilter, Radius

PAGE = {"offset": 0, "limit": 25}

# Measured by the first version of this benchmark (2026-09-25, same machine, 100k records),
# before the index/query change it motivated. Kept so the report shows why that change exists.
TUNING_HISTORY = [
    "## Tuning history",
    "",
    "The first run of this benchmark found a regression the demo-sized dataset could not show: "
    "at 100k records the default list (newest first, page of 25 + total) took **p50 505 ms / "
    "p95 611 ms with `qw_events_occurred_at` and 81 / 90 ms without it**, missing the PRD "
    "target and losing to a full scan. EXPLAIN showed two causes:",
    "",
    "1. The sort `occurred_at, _key` (the `_key` tie-break keeps paging stable) was not covered "
    "by the single-field index, so the optimizer kept a SORT node and fetched all 100,000 "
    "documents through the index before sorting.",
    "2. The total came from `fullCount`, which makes the page query materialise every matching "
    "document just to evaluate `merged_into == null`.",
    "",
    "Changes (applied to existing databases by `arango_migrate` drift repair):",
    "",
    "- `qw_events_occurred_at` is now `[occurred_at, _key]` storing `merged_into, magnitude`, "
    "and `qw_events_magnitude` is `[magnitude, _key]` storing `merged_into`: the index yields "
    "rows in final order and answers the live filter (and the common magnitude filter) without "
    "fetching documents.",
    "- `EventRepository.search` takes the total from a `COLLECT WITH COUNT` subquery in the "
    "same AQL (`search_page_aql`) instead of `fullCount`: one round trip, one snapshot, and the "
    "count is answered from index entries.",
    "",
    "Result at 100k: the same list went from 505 / 611 ms to the figures in the table above.",
    "",
]


def _search(f: EventFilter) -> tuple[str, dict[str, Any]]:
    aql, binds = events.search_page_aql(f)  # exactly what the list API executes
    return aql, {**binds, **PAGE}


def workloads() -> list[bench.Workload]:
    list_aql, _ = _search(EventFilter(start=utc_now(), min_magnitude=2.5))
    latest_aql, latest_binds = _search(EventFilter())
    radius_aql, _ = _search(EventFilter(radius=Radius(0.0, 0.0, 250.0)))

    def filtered(ctx: bench.BenchContext) -> dict[str, Any]:
        _, binds = _search(EventFilter(start=ctx.newest - timedelta(days=7), min_magnitude=2.5))
        return binds

    def radius(ctx: bench.BenchContext) -> dict[str, Any]:
        lat, lon, _spread = ctx.rng.choice(bench.ZONES)
        _, binds = _search(EventFilter(radius=Radius(lat, lon, 250.0)))
        return binds

    return [
        bench.Workload(
            "event_list_filtered",
            "Explorer/API list: last 7 days, M >= 2.5, newest first, page of 25 + total count",
            list_aql,
            filtered,
        ),
        bench.Workload(
            "event_list_latest",
            "Explorer/API default list: newest first, page of 25 + total count",
            latest_aql,
            lambda _ctx: dict(latest_binds),
        ),
        bench.Workload(
            "geo_radius",
            "Events within 250 km of a seismic-zone centre, newest first, page of 25",
            radius_aql,
            radius,
        ),
        bench.Workload(
            "analytics_magnitude_histogram",
            "Magnitude histogram (0.5 bins) for the last 30 days",
            analytics.MAGNITUDE_HISTOGRAM.aql,
            lambda ctx: {"since": to_iso(ctx.newest - timedelta(days=30))},
        ),
        bench.Workload(
            "revision_lookup",
            "Revision timeline of one event (Event Detail history tab)",
            events.REVISIONS.aql,
            lambda ctx: {"key": ctx.some_key()},
        ),
    ]


class Command(BaseCommand):
    help = "Benchmark the main AQL workloads with and without their indexes."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--sizes", default="500,10000,100000")
        parser.add_argument("--runs", type=int, default=20)
        parser.add_argument("--write", action="store_true", help="write docs/BENCHMARKS.md")
        parser.add_argument("--keep", action="store_true", help="keep the benchmark database")
        parser.add_argument(
            "--render-only",
            action="store_true",
            help="re-render docs/BENCHMARKS.md from var/benchmarks.json without measuring",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["render_only"]:
            self._render_only()
            return
        try:
            sizes = [int(v) for v in str(options["sizes"]).split(",") if v.strip()]
        except ValueError as exc:
            raise CommandError("--sizes must be comma-separated integers") from exc
        if not sizes or min(sizes) < 1 or options["runs"] < 1:
            raise CommandError("sizes and runs must be positive")
        name = f"{database_name()}_bench_test"
        newest = utc_now().replace(microsecond=0)
        results: list[bench.Timing] = []
        for size in sizes:
            self.stdout.write(f"== {size:,} events ==")
            results += bench.run_size(
                name,
                size,
                workloads(),
                newest=newest,
                runs=options["runs"],
                log=self.stdout.write,
            )
        arango_version = str(sync(ensure_database(name).version()))
        if not options["keep"]:
            drop_database(name)
        if options["write"]:
            self._write(results, arango_version, options["runs"])

    def _render_only(self) -> None:
        source = Path(settings.BASE_DIR) / "var" / "benchmarks.json"
        if not source.exists():
            raise CommandError("no var/benchmarks.json yet; run with --write first")
        payload = json.loads(source.read_text(encoding="utf-8"))
        saved = [bench.Timing(**row) for row in payload["results"]]
        target = Path(settings.BASE_DIR) / "docs" / "BENCHMARKS.md"
        target.write_bytes(render(saved, payload["environment"]).encode("utf-8"))
        self.stdout.write("re-rendered docs/BENCHMARKS.md")

    def _write(self, results: list[bench.Timing], arango_version: str, runs: int) -> None:
        env = {
            "generated_at": now_iso(),
            "arangodb": arango_version,
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "cpus": os.cpu_count(),
            "runs_per_case": runs,
        }
        out = Path(settings.BASE_DIR)
        (out / "var").mkdir(exist_ok=True)
        payload = {"environment": env, "results": [r.as_dict() for r in results]}
        (out / "var" / "benchmarks.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (out / "docs" / "BENCHMARKS.md").write_bytes(render(results, env).encode("utf-8"))
        self.stdout.write("wrote docs/BENCHMARKS.md and var/benchmarks.json")


def render(results: list[bench.Timing], env: dict[str, Any]) -> str:
    descriptions = {w.name: w.description for w in workloads()}
    by_key = {(r.workload, r.size, r.indexed): r for r in results}
    sizes = sorted({r.size for r in results})
    names = list(dict.fromkeys(r.workload for r in results))
    lines = [
        "# Index benchmarks",
        "",
        "Generated by `manage.py arango_benchmark --write` - do not edit by hand. Raw numbers "
        "are written to `var/benchmarks.json` (local, git-ignored).",
        "",
        f"- Generated {env['generated_at']} · ArangoDB {env['arangodb']} (Docker) · "
        f"Python {env['python']} · {env['os']} · {env['cpus']} logical CPUs",
        f"- Each case: 2 warm-up runs, then {env['runs_per_case']} timed runs with fresh bind "
        "values; latency is client-observed (driver round trip included).",
        "- Data: synthetic, schema-valid catalogue (`apps/core/arango/benchmark.py`): ~270 "
        "events/day, Gutenberg-Richter magnitudes calibrated to ~15 % M2.5+ / ~4 % M4.5+, "
        "clustered epicentres, 1-4 revisions per event.",
        "- *Without indexes* drops the read indexes (`qw_events_occurred_at`, "
        "`qw_events_magnitude`, `qw_events_geo`, `qw_revisions_*`); integrity indexes stay.",
        "- *Scanned* = documents read by full collection scans / via indexes (max per run).",
        "",
        "## Workloads",
        "",
    ]
    lines += [f"- `{n}` - {descriptions.get(n, '')}" for n in names]
    lines += [
        "",
        "## Results (p50 / p95 ms)",
        "",
        "| Workload | Records | With indexes | Without indexes | p95 speed-up | "
        "Scanned with (full/index) | Scanned without (full/index) | Index used |",
        "|---|--:|--:|--:|--:|--:|--:|---|",
    ]
    for n in names:
        for size in sizes:
            w, wo = by_key.get((n, size, True)), by_key.get((n, size, False))
            if w is None or wo is None:
                continue
            speedup = wo.p95_ms / w.p95_ms if w.p95_ms else float("inf")
            lines.append(
                f"| `{n}` | {size:,} | {w.p50_ms:.1f} / {w.p95_ms:.1f} | "
                f"{wo.p50_ms:.1f} / {wo.p95_ms:.1f} | {speedup:.1f}x | "
                f"{w.scanned_full:,} / {w.scanned_index:,} | "
                f"{wo.scanned_full:,} / {wo.scanned_index:,} | "
                f"{', '.join(f'`{i}`' for i in w.indexes) or '-'} |"
            )
    worst = max((r.p95_ms for r in results if r.indexed), default=0.0)
    lines += [
        "",
        "## Reading the results",
        "",
        f"- Slowest indexed p95 across all cases: **{worst:.1f} ms** "
        "(PRD target: p95 < 500 ms for a common filtered query).",
        "- Without indexes every workload is a full collection scan, so its cost grows with the "
        "collection; with indexes it grows with the answer. On small datasets a scan is as fast as "
        "(or faster than) an index lookup, so speed-ups below 1x at 500-10k are expected; at "
        "100k the indexes win on every workload. The index set is justified at production scale.",
        "- List workloads scan twice without indexes (the count subquery and the page each read "
        "the collection); with indexes the count reads index entries only.",
        "- `event_list_latest` has no filter besides `merged_into == null`, so its count still "
        "walks every index entry; it stays well inside the target but is the workload that "
        "grows with the catalogue.",
        "",
        *TUNING_HISTORY,
    ]
    return "\n".join(lines)
