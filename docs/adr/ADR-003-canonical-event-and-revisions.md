# ADR-003: Canonical event + immutable revisions, with identity claims

- **Status:** Accepted (revised 2026-09-25 after design review — see "Review history")
- **Date:** 2026-09-25

## Context
USGS revises magnitude, depth, location, status and products after first publication (PRD P2).
The product must preserve meaningful history (FR-04), never duplicate a source event (FR-03,
"zero duplicate canonical records"), and stay idempotent under replays and concurrency (ESD §13).

Recorded payloads showed a further reality: each feature carries `ids` — all ids associated with
the physical event. USGS can change the *preferred* id (e.g. a regional `ci…` id replaced by a
`us…` id), drop ids from the list, and associate two separately published records later.
Keying only on the current id would create duplicate canonical records.

## Decision

### Canonical record
`events` holds one document per physical event. `_key = usgs_<first-seen id>` never changes;
`source_event_id` is the current preferred id; `associated_ids` is the source's current list
(source truth, may shrink).

### Identity claims (`event_identities`)
Every id ever associated with a live event is *claimed*: `_key = usgs_<id>`, value `event_key`.
- **Lookup** resolves incoming `ids` through claims (primary-key lookups only).
- **New events** claim their ids with plain inserts *inside the ingestion transaction*. Two
  workers racing on the same physical event under different preferred ids collide on a claim key
  (write-write conflict or unique violation); the loser's unit is retried and finds the winner.
- **Merges**: when claims resolve to several live events, the one owning the preferred id (else the
  earliest seen) stays canonical; the others get `merged_into`, their claims and any records merged
  into them are re-pointed to the survivor, and their region/network edges are removed. Merged
  records are kept for provenance and excluded from all queries.
- Ids that USGS drops keep their claims, so a later record under a dropped id still resolves.
- The unique index `(source, source_event_id, merged_into)` guarantees one *live* record per id.

### Revisions
`event_revisions` is append-only. Revision 1 (`created`) snapshots the full source state; later
revisions store `changed_fields`, `before`, `after` and the full `state`, plus payload hash, policy
version and run id. Keys are deterministic (`<event_key>_<n:06d>`) and uniquely indexed. Revisions
follow the versioned policy (`apps/ingestion/revision_policy.py`); untracked source changes refresh
the canonical record without a revision. Out-of-order data (older `source_updated_at`) never
regresses the record (identity claims are still recorded).

### Atomicity and failure isolation
Canonical update, identity claims, revision, raw payload, graph edges and observer effects (alert
matches) commit in **one stream transaction**. Write conflicts and unique violations retry the
whole unit, which re-reads committed state. A record that still fails is rolled back, dead-lettered
(`apply_failed`) and counted as `failed`; the rest of the batch continues and the run is `partial`.
Only a database outage aborts a batch.

## Consequences
- Verified: 8 concurrent writers of one record → one event; two writers with different preferred ids
  → one event (the same test fails 5/5 when claims are disabled).
- Revision reconstruction is exact: the state at revision *n* is `revision[n].state`.
- A fast path (payload hash unchanged) skips transactions for the vast majority of feed records.
- Known limitation: the summary feed and the FDSN catalog publish different `detail` URLs, so an
  event touched by both alternates payload hash and is reported `refreshed` (no revision) after a
  backfill; it returns to the fast path on the next poll.

## Review history
An independent review of the first version (claims absent; lookup through a non-unique
`associated_ids[*]` array index) found that (1) concurrent writers with different preferred ids
could both insert, and (2) a dropped id could make an insert collide with an existing `_key` and
abort a whole batch on every poll. Both are fixed by identity claims and per-record failure
isolation; schema v2 migrates existing data (`v2:identity_claims`).
