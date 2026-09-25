# ADR-001: ArangoDB as the primary database

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
QuakeWatch needs document storage for evolving event records, graph relationships
(event→region, event→network, user→rule→event), geospatial queries (radius, bounding box),
full-text search over place names, and multi-document transactions for canonical update +
revision append. The academic brief also requires an open-source NoSQL DBMS.

## Decision
Use ArangoDB (Community, 3.12) as the primary store for all domain data. Access it only through
repositories using AQL with bind variables (python-arango driver). Schema, validation rules,
indexes, the ArangoSearch view and the named graph are declared in `apps/core/arango/schema.py`
and reconciled idempotently by `manage.py arango_migrate`.

## Consequences
- One engine covers documents, graph traversal, geo indexes, ArangoSearch and stream transactions,
  so there is no second datastore to synchronise.
- Collection-level JSON-schema rules give DB-enforced integrity comparable to SQL constraints.
- The Django ORM cannot target ArangoDB; see ADR-009 for auth storage.
- Relational rubric vocabulary (PK, FK, views, triggers) is mapped explicitly in
  docs/ARCHITECTURE.md rather than claimed literally.
