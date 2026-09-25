# ADR-006: Research snapshot reproducibility

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
Research datasets must be reproducible (PRD P5, FR-13): an export must record its source, query
definition, generation time, schema version, application version and checksum, and it must remain
the same dataset even though USGS keeps revising events.

## Decision
- **Freeze = pin revisions.** Creating a snapshot evaluates the explorer filter (same
  `EventFilter` and AQL builder as the API) and stores, for every matching live event, the pair
  `[event_key, revision_number]` current at that moment (max 50 000 rows). Revisions are immutable,
  so the pinned set always reconstructs the same rows, regardless of later revisions or raw-payload
  expiry (ADR-007).
- **Rows** are rebuilt from `event_revisions.state` with a fixed column set
  (`apps/research/manifest.py::EXPORT_COLUMNS`), each column labelled source / derived / QuakeWatch.
  Row order: `occurred_at`, then `event_key`.
- **Content checksum** = SHA-256 of the rows as JSON Lines (sorted keys, compact separators,
  UTF-8). It is independent of file format and is recomputed and verified on every export; a
  mismatch is an integrity error (never expected).
- **Manifest**: snapshot id, title/notes, creation time, source + attribution, canonical query
  definition + human summary, row count, checksum (+ its definition), export/DB schema versions,
  revision-policy version, application version (explicit `QW_APP_VERSION` or the checkout's git
  SHA), column dictionary, source-request manifest (the ingestion runs and HTTP requests — URL,
  params, response SHA-256 — that produced the pinned revisions), and stated limitations.
- **Bundle**: zip with `data.csv`, `data.json` (manifest + rows), `manifest.json`, `SHA256SUMS`.
  The zip is byte-reproducible: sorted entries, fixed timestamps and permissions.
- Exports are owner-only and throttled (`export` scope, 10/hour).

## Consequences
- Verified by test: a snapshot exported, then an event revised by USGS, then exported again,
  yields byte-identical bundles with the same checksum.
- Snapshots store member lists (≈30 bytes per row); the list API projects them out.
