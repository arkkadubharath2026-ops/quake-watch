# ADR-010: Timestamp representation and source/derived separation

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
Events are filtered and sorted by time constantly; values from USGS must be distinguishable from
values QuakeWatch computes (PRD principle "source truth first", README data-integrity rules).

## Decision
1. All timestamps are stored as fixed-width ISO-8601 UTC strings with milliseconds
   (`YYYY-MM-DDTHH:MM:SS.sssZ`, `apps/core/clock.py`). Fixed width makes lexicographic order equal
   chronological order, so persistent indexes serve range filters and sorts, and AQL date functions
   accept the values directly. Collection schema rules enforce the pattern.
2. Source fields sit at the top level of an event with the same names as `CanonicalEventInput`.
   Application-derived values (region, ingestion latency, …) live only under `derived`, and
   operational metadata uses explicit `*_at` / counters (`first_seen_at`, `last_seen_at`,
   `revision_count`). Derived values never overwrite source values.

## Consequences
- The UI can label every value's provenance mechanically (source / derived / operational).
- Converting to epoch values is done in AQL (`DATE_TIMESTAMP`) where arithmetic is needed.
