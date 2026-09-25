# ADR-008: Multi-source canonicalization (research track)

- **Status:** Proposed (design constraint for the MVP; implementation is research-track scope)
- **Date:** 2026-09-25

## Context
The research track adds EMSC (SeismicPortal FDSN) as a second source to study first-report
latency, magnitude/location disagreement and convergence (PRD RQ2, ESD §20A). The MVP must not
make that addition require a redesign.

## Decision
- Each source keeps **its own canonical events**: identity is `(source, source_event_id)` and
  `_key = <source>_<id>`; identity claims (ADR-003) are namespaced by source (`usgs_<id>`,
  `emsc_<id>`). No record from one source ever overwrites another source's values.
- A second source gets its own adapter (`apps/ingestion/adapters/emsc.py`) normalising into the same
  source-neutral `CanonicalEventInput` (the `source` literal is widened) and runs through the same
  pipeline, revision policy and provenance machinery.
- Cross-source association is a **derived relationship**, stored as an edge collection
  (`same_physical_event`) with the matching method, parameters (time window, distance, magnitude
  tolerance), method version and scores. It never merges or edits source records.
- Concordance metrics (first-report latency, magnitude/epicentre discrepancy, convergence time) are
  computed from the two sources' revision histories, so they are reproducible from stored data.

## Consequences
- MVP already satisfies the constraints: `source` is part of identity keys, claims and indexes; the
  pipeline is source-agnostic apart from the adapter; derived values live under `derived`.
- Association thresholds are a research choice and must be documented with the experiment.
