# ADR-007: Raw-data retention policy

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
ESD §12 requires, for reproducibility, either raw payloads for a justified retention period or
payload hashes + source-request manifests + normalised revisions. Storing every poll's raw feed
would grow without bound (≈ 200 features × 288 polls/day).

## Decision
Both, with bounded cost:
1. **Content-addressed raw payloads**: each distinct feature payload is stored once in
   `raw_payloads` with `_key = SHA-256` of its canonical JSON. Identical payloads from later polls
   only bump `last_fetched_at`/`expires_at`. Only *new or changed* payloads are written (fast path).
2. **TTL retention**: `expires_at` (epoch seconds) is indexed by an ArangoDB TTL index; payloads
   expire `QW_RAW_PAYLOAD_RETENTION_DAYS` (default 90) after they were last fetched.
3. **Permanent provenance**: every canonical event and revision keeps its `payload_hash`; every
   ingestion run keeps its request manifest (URL, params, status, attempts, bytes, response SHA-256)
   and the feed's `generated` timestamp; revisions keep the full normalised source state.

## Consequences
- Within 90 days any revision can be traced to its exact raw payload; after that, the hash and the
  normalised state still prove what was ingested.
- Research snapshots (ADR-006) depend on revisions, not on raw payloads, so they remain exportable
  after raw data expires.
