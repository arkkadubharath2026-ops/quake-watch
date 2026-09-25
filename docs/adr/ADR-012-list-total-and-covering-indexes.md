# ADR-012: Event list totals from a count subquery, with covering sort indexes

- **Status:** Accepted
- **Date:** 2026-09-25
- **Supersedes:** the single-field `qw_events_occurred_at` / `qw_events_magnitude` index design (ESD §6)

## Context
The event list API (Explorer, Dashboard, `GET /api/v1/events`) returns a page of 25 plus the
total number of matches. It sorts by `(<field>, _key)`, where the `_key` tie-break keeps paging
stable when several events share a timestamp, and it always filters `merged_into == null` (ADR-003).

The L6 index benchmark (`manage.py arango_benchmark`, docs/BENCHMARKS.md) measured the default
newest-first list at 100k synthetic events: **p50 505 ms / p95 611 ms with the index and 81 / 90 ms
without it**. That missed the PRD target (p95 < 500 ms) and was slower than a full scan. EXPLAIN
showed two causes:

1. The single-field index on `occurred_at` cannot supply the order `(occurred_at, _key)`. The
   optimizer kept a SORT node and read all 100,000 documents through the index before sorting.
2. The total used AQL `fullCount`. That forces the sorted page query to produce every matching
   row, fetching each document just to evaluate `merged_into == null`.

## Decision
1. Sort indexes include the tie-break and carry the always-applied filter:
   - `qw_events_occurred_at`: fields `[occurred_at, _key]`, stored values `[merged_into, magnitude]`;
   - `qw_events_magnitude`: fields `[magnitude, _key]`, stored values `[merged_into]`.

   The index returns rows already in final order, so a page reads 25 entries. The live filter,
   and the most common magnitude filter, are answered from the index entries without fetching
   documents.
2. `EventRepository.search` runs one AQL statement (`search_page_aql`):
   `LET total = FIRST(<filters> COLLECT WITH COUNT INTO n RETURN n)` plus the page subquery. It no
   longer uses `fullCount`. Both parts read one snapshot in one round trip, and the count is
   answered from index entries.
3. `IndexSpec` gained `stored_values`, and migration drift detection compares it, so existing
   databases are repaired by `arango_migrate`. No data migration is needed and `SCHEMA_VERSION`
   is unchanged, because document shapes are unchanged.

## Consequences
- At 100k records the same list is p50 27 ms / p95 37 ms. Across all benchmarked workloads, the
  slowest indexed p95 is now 51 ms (docs/BENCHMARKS.md).
- The unfiltered list still counts every live index entry, so it is the workload that grows with
  the catalogue. If the catalogue grows well past 10⁶ events, the next step is an approximate or
  capped total for unfiltered queries.
- The indexes are slightly larger (two stored attributes per entry). Writes pay the same number of
  index updates as before.
- Regression guards:
  - `test_newest_first_list_is_served_in_index_order` asserts no SORT node and the index in the plan;
  - `test_list_total_matches_an_independent_count` checks the total;
  - `test_missing_stored_values_count_as_drift` checks drift repair.

## Alternatives considered
- **Keep `fullCount` and add a hint to force a full scan** — rejected. It would be fast at 100k
  (81 ms) but grows linearly, and it gives up the index for the page itself.
- **Drop the `_key` tie-break** — rejected. Paging becomes unstable for events with identical
  timestamps (common in backfills), and rows could repeat or vanish between pages.
- **Separate count request** — rejected. It costs two round trips, and under concurrent
  ingestion the page and the total could come from different snapshots.
