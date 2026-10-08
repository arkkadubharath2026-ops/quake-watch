"""Declarative ArangoDB schema for QuakeWatch (ESD §5, §6).

This module is the single source of truth for collections, collection-level JSON-schema
validation, named indexes, the ArangoSearch view and the named graph. ``arango_migrate``
applies it idempotently (:mod:`apps.core.arango.migrate`).

Index policy (ESD §6): only indexes that serve a real access path are declared here. Every
index is named ``qw_*`` so migrations can reconcile (create / replace / drop) them safely,
and each is justified with an EXPLAIN plan in docs/AQL_QUERIES.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 6  # v3: leases; v4: cache/metrics/breakers; v5: jobs; v6: auth users, sessions
GRAPH_NAME = "quakewatch_graph"
EVENTS_SEARCH_VIEW = "events_search"

# ---- Collection names (import these instead of string literals) ------------------------
EVENTS = "events"
EVENT_REVISIONS = "event_revisions"
EVENT_IDENTITIES = "event_identities"
RAW_PAYLOADS = "raw_payloads"
REGIONS = "regions"
NETWORKS = "networks"
USERS = "users"
ALERT_RULES = "alert_rules"
ALERT_MATCHES = "alert_matches"
SAVED_SEARCHES = "saved_searches"
RESEARCH_SNAPSHOTS = "research_snapshots"
INGESTION_RUNS = "ingestion_runs"
BACKFILL_JOBS = "backfill_jobs"
DEAD_LETTERS = "dead_letters"
AUDIT_LOG = "audit_log"
JOB_LEASES = "job_leases"
CACHE_ENTRIES = "cache_entries"
METRIC_COUNTERS = "metric_counters"
METRIC_SERIES = "metric_series"
CIRCUIT_BREAKERS = "circuit_breakers"
JOBS = "jobs"
JOB_SCHEDULES = "job_schedules"
AUTH_USERS = "auth_users"
SESSIONS = "sessions"
ID_SEQUENCES = "id_sequences"
RATE_LIMITS = "rate_limits"
SCHEMA_META = "schema_meta"

EVENT_IN_REGION = "event_in_region"
EVENT_REPORTED_BY_NETWORK = "event_reported_by_network"
USER_OWNS_RULE = "user_owns_rule"
RULE_MATCHED_EVENT = "rule_matched_event"

ISO_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"


def _ts(nullable: bool = False) -> dict[str, Any]:
    base: dict[str, Any] = {"type": "string", "pattern": ISO_TS_PATTERN}
    return {"anyOf": [base, {"type": "null"}]} if nullable else base


def _nullable(type_: str, **extra: Any) -> dict[str, Any]:
    return {"anyOf": [{"type": type_, **extra}, {"type": "null"}]}


# ---- JSON-schema rules (DB-level integrity; mirrors the domain DTOs) ----------------------
SOURCE_STATE_PROPERTIES: dict[str, Any] = {
    "associated_ids": {
        "type": "array",
        "minItems": 1,
        "maxItems": 64,
        "items": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
    },
    "event_type": {"type": "string", "minLength": 1, "maxLength": 40},
    "magnitude": _nullable("number", minimum=-2, maximum=11),
    "magnitude_type": _nullable("string", maxLength=16),
    "place": _nullable("string", maxLength=300),
    "occurred_at": _ts(),
    "source_updated_at": _ts(),
    "latitude": {"type": "number", "minimum": -90, "maximum": 90},
    "longitude": {"type": "number", "minimum": -180, "maximum": 180},
    "depth_km": _nullable("number", minimum=-10, maximum=1000),
    "felt": _nullable("integer", minimum=0),
    "cdi": _nullable("number", minimum=0, maximum=12),
    "mmi": _nullable("number", minimum=0, maximum=12),
    "alert": {"enum": ["green", "yellow", "orange", "red", None]},
    "status": {"enum": ["automatic", "reviewed", "deleted"]},
    "tsunami": {"type": "boolean"},
    "significance": _nullable("integer", minimum=0),
    "network": _nullable("string", maxLength=16),
    "detail_url": _nullable("string", maxLength=500),
    "event_page_url": _nullable("string", maxLength=500),
    "station_count": _nullable("integer", minimum=0),
    "min_station_distance_deg": _nullable("number", minimum=0),
    "rms_travel_time_residual": _nullable("number", minimum=0),
    "azimuthal_gap_deg": _nullable("number", minimum=0, maximum=360),
    "products": {"type": "array", "items": {"type": "string", "maxLength": 64}, "maxItems": 64},
    "contributors": {"type": "array", "items": {"type": "string", "maxLength": 16}},
}

EVENT_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source": {"enum": ["USGS"]},
        "source_event_id": {"type": "string", "minLength": 1, "maxLength": 64},
        **SOURCE_STATE_PROPERTIES,
        "coordinates": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {"type": "number"},
        },
        "derived": {"type": "object"},
        "first_seen_at": _ts(),
        "last_seen_at": _ts(),
        "last_ingested_at": _ts(),
        "revision_count": {"type": "integer", "minimum": 1},
        "payload_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "schema_version": {"type": "integer", "minimum": 1},
        "revision_policy_version": {"type": "integer", "minimum": 1},
        "merged_into": _nullable("string"),
    },
    "required": [
        "source",
        "source_event_id",
        "associated_ids",
        "event_type",
        "occurred_at",
        "source_updated_at",
        "latitude",
        "longitude",
        "coordinates",
        "status",
        "tsunami",
        "first_seen_at",
        "last_seen_at",
        "last_ingested_at",
        "revision_count",
        "payload_hash",
        "schema_version",
        "revision_policy_version",
    ],
}

REVISION_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "event_key": {"type": "string"},
        "revision_number": {"type": "integer", "minimum": 1},
        "kind": {"enum": ["created", "updated"]},
        "observed_at": _ts(),
        "source_updated_at": _ts(),
        "changed_fields": {"type": "array", "items": {"type": "string"}},
        "before": {"type": "object"},
        "after": {"type": "object"},
        "state": {"type": "object"},
        "payload_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "policy_version": {"type": "integer", "minimum": 1},
        "ingestion_run_id": _nullable("string"),
    },
    "required": [
        "event_key",
        "revision_number",
        "kind",
        "observed_at",
        "source_updated_at",
        "changed_fields",
        "before",
        "after",
        "state",
        "payload_hash",
        "policy_version",
    ],
}

ALERT_RULE_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "user_id": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1, "maxLength": 120},
        "enabled": {"type": "boolean"},
        "conditions": {"type": "object"},
        "cooldown_minutes": {"type": "integer", "minimum": 0, "maximum": 10080},
        "created_at": _ts(),
        "updated_at": _ts(),
    },
    "required": ["user_id", "name", "enabled", "conditions", "cooldown_minutes", "created_at"],
}


# Lease times are ArangoDB server time in epoch seconds (DATE_NOW() / 1000), the numeric form the
# TTL index expires on; they are never compared with a worker's clock (apps.core.arango.leases).
JOB_LEASE_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "token": {"type": "string", "minLength": 16, "maxLength": 64},
        "owner": {"type": "string", "maxLength": 200},
        "acquired_at": {"type": "number"},
        "renewed_at": {"type": "number"},
        "expires_at": {"type": "number"},
        # Whole number, but typed "number": AQL arithmetic (OLD.fencing + 1) yields a double, which
        # ArangoDB's validator rejects as "integer" even when it is integral.
        "fencing": {"type": "number", "multipleOf": 1, "minimum": 1},
    },
    "required": ["token", "owner", "acquired_at", "renewed_at", "expires_at", "fencing"],
}


AUTH_USER_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "number", "multipleOf": 1, "minimum": 1},
        "username": {"type": "string", "minLength": 1, "maxLength": 150},
        "username_ci": {"type": "string", "minLength": 1, "maxLength": 150},
        "email": {"type": "string", "maxLength": 254},
        "password": {"type": "string", "maxLength": 128},
        "is_active": {"type": "boolean"},
        "is_staff": {"type": "boolean"},
        "is_superuser": {"type": "boolean"},
        "date_joined": {"type": "string"},
        "last_login": {"type": ["string", "null"]},
    },
    "required": [
        "id",
        "username",
        "username_ci",
        "email",
        "password",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    ],
}

JOB_RULE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "minLength": 1, "maxLength": 200},
        "status": {"enum": ["queued", "running", "succeeded", "failed", "dead", "expired"]},
        "args": {"type": "array"},
        "kwargs": {"type": "object"},
        "run_at": {"type": "number"},
        "created_at": {"type": "number"},
        "attempts": {"type": "number", "multipleOf": 1, "minimum": 0},
        "max_attempts": {"type": "number", "multipleOf": 1, "minimum": 1},
        "time_limit": {"type": "number", "minimum": 1},
    },
    "required": [
        "task",
        "status",
        "args",
        "kwargs",
        "run_at",
        "created_at",
        "attempts",
        "max_attempts",
        "time_limit",
    ],
}


@dataclass(frozen=True, slots=True)
class IndexSpec:
    name: str
    type: str
    fields: tuple[str, ...]
    unique: bool = False
    sparse: bool = False
    geo_json: bool = False
    expire_after: int | None = None
    # Extra attributes carried in the index entries (persistent only): filters on them are
    # answered from the index, so a sorted walk or a count never has to fetch the document.
    stored_values: tuple[str, ...] = ()

    def as_arango(self) -> dict[str, Any]:
        spec: dict[str, Any] = {"type": self.type, "fields": list(self.fields), "name": self.name}
        if self.type == "persistent":
            spec["unique"] = self.unique
            spec["sparse"] = self.sparse
            if self.stored_values:
                spec["storedValues"] = list(self.stored_values)
        elif self.type == "geo":
            spec["geoJson"] = self.geo_json
        elif self.type == "ttl":
            spec["expireAfter"] = self.expire_after or 0
        return spec


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    name: str
    edge: bool = False
    rule: dict[str, Any] | None = None
    indexes: tuple[IndexSpec, ...] = field(default_factory=tuple)
    purpose: str = ""


def _p(
    name: str,
    *fields: str,
    unique: bool = False,
    sparse: bool = False,
    stored: tuple[str, ...] = (),
) -> IndexSpec:
    return IndexSpec(
        name=name,
        type="persistent",
        fields=fields,
        unique=unique,
        sparse=sparse,
        stored_values=stored,
    )


COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec(
        EVENTS,
        rule=EVENT_RULE,
        purpose="Latest canonical representation of each source event.",
        indexes=(
            # merged_into is part of the key so a merged (superseded) record may keep its
            # historical id while exactly one live record owns it (ADR-003).
            _p(
                "qw_events_source_identity",
                "source",
                "source_event_id",
                "merged_into",
                unique=True,
            ),
            IndexSpec("qw_events_geo", "geo", ("coordinates",), geo_json=True),
            # _key completes the list's sort order (occurred_at, _key) so the index yields rows
            # already sorted and a page reads only its own entries; the stored values answer the
            # always-present live filter and the most common magnitude filter from the index
            # (before/after numbers: docs/BENCHMARKS.md).
            _p(
                "qw_events_occurred_at",
                "occurred_at",
                "_key",
                stored=("merged_into", "magnitude"),
            ),
            _p("qw_events_magnitude", "magnitude", "_key", stored=("merged_into",)),
        ),
    ),
    CollectionSpec(
        EVENT_REVISIONS,
        rule=REVISION_RULE,
        purpose="Immutable meaningful source changes (append-only).",
        indexes=(
            _p("qw_revisions_event_rev", "event_key", "revision_number", unique=True),
            _p("qw_revisions_observed_at", "observed_at"),
            # revision analytics ("status"/"magnitude" IN changed_fields[*]), see AQL_QUERIES.md
            _p("qw_revisions_changed_fields", "changed_fields[*]"),
        ),
    ),
    CollectionSpec(
        EVENT_IDENTITIES,
        purpose=(
            "Identity claims: _key usgs_<id> -> event_key for every id ever associated with a live "
            "event. Unique keys serialise concurrent writers of the same physical event (ADR-003)."
        ),
        indexes=(_p("qw_identities_event_key", "event_key"),),  # re-pointing claims on merge
    ),
    CollectionSpec(
        RAW_PAYLOADS,
        purpose="Content-addressed raw source payloads with TTL retention (ADR-007).",
        indexes=(IndexSpec("qw_raw_ttl", "ttl", ("expires_at",), expire_after=0),),
    ),
    CollectionSpec(REGIONS, purpose="Application-normalised geographic entities (derived)."),
    CollectionSpec(NETWORKS, purpose="Seismic source networks."),
    CollectionSpec(USERS, purpose="Graph vertex mirror of Django users (id + username only)."),
    CollectionSpec(
        ALERT_RULES,
        rule=ALERT_RULE_RULE,
        purpose="User-owned alert/watch rules.",
        indexes=(_p("qw_rules_user", "user_id"), _p("qw_rules_enabled", "enabled")),
    ),
    CollectionSpec(
        ALERT_MATCHES,
        purpose="Immutable rule-match history with explanations.",
        indexes=(
            _p("qw_matches_rule_event", "rule_key", "event_key", unique=True),
            _p("qw_matches_user_time", "user_id", "matched_at"),
        ),
    ),
    CollectionSpec(
        SAVED_SEARCHES,
        purpose="Saved explorer filters.",
        indexes=(_p("qw_saved_user", "user_id", "created_at"),),
    ),
    CollectionSpec(
        RESEARCH_SNAPSHOTS,
        purpose="Reproducible dataset definitions pinned to revisions.",
        indexes=(_p("qw_snapshots_user", "user_id", "created_at"),),
    ),
    CollectionSpec(
        INGESTION_RUNS,
        purpose="Operational metadata for every sync/import job.",
        indexes=(
            _p("qw_runs_started_at", "started_at"),
            _p("qw_runs_status", "status"),
            _p("qw_runs_kind_started", "kind", "started_at"),
        ),
    ),
    CollectionSpec(
        BACKFILL_JOBS,
        purpose="Checkpointed historical backfill jobs.",
        indexes=(_p("qw_backfill_status", "status"),),
    ),
    CollectionSpec(
        DEAD_LETTERS,
        purpose="Rejected or repeatedly failing source records.",
        indexes=(
            _p("qw_dead_last_failure", "last_failure_at"),
            _p("qw_dead_source_event", "source", "source_event_id"),
        ),
    ),
    CollectionSpec(
        AUDIT_LOG,
        purpose="Audit trail of privileged/administrative actions (FR-15).",
        indexes=(_p("qw_audit_at", "at"),),
    ),
    CollectionSpec(
        JOB_LEASES,
        rule=JOB_LEASE_RULE,
        purpose=(
            "Job leases: at most one running instance per job name; expiry by server time. "
            "The TTL index only garbage-collects abandoned leases."
        ),
        indexes=(IndexSpec("qw_leases_ttl", "ttl", ("expires_at",), expire_after=0),),
    ),
    CollectionSpec(
        CACHE_ENTRIES,
        purpose=(
            "Django cache (throttles, login counters, analytics, diagnostics). Expiry checked on "
            "every read (application clock); the TTL index only removes expired entries."
        ),
        indexes=(IndexSpec("qw_cache_ttl", "ttl", ("expires_at",), expire_after=0),),
    ),
    CollectionSpec(
        RATE_LIMITS,
        purpose=(
            "API rate-limit windows (apps.core.throttling): recent request times per scope and "
            "client, checked and recorded in one atomic statement. TTL index = garbage collection."
        ),
        indexes=(IndexSpec("qw_rate_limits_ttl", "ttl", ("expires_at",), expire_after=0),),
    ),
    CollectionSpec(METRIC_COUNTERS, purpose="Operational counters (one document per name)."),
    CollectionSpec(METRIC_SERIES, purpose="Latency series: the most recent samples per name."),
    CollectionSpec(CIRCUIT_BREAKERS, purpose="Shared circuit-breaker state per upstream source."),
    CollectionSpec(
        JOBS,
        rule=JOB_RULE,
        purpose=(
            "Durable background jobs (queue, leases, retries, dead letters); see apps.jobs. "
            "Finished jobs are purged by the TTL index after the retention period."
        ),
        indexes=(
            _p("qw_jobs_claim", "status", "run_at"),
            _p("qw_jobs_dedupe", "dedupe_key", unique=True, sparse=True),
            _p("qw_jobs_task_created", "task", "created_at"),
            IndexSpec("qw_jobs_purge", "ttl", ("purge_at",), expire_after=0),
        ),
    ),
    CollectionSpec(
        JOB_SCHEDULES, purpose="Periodic schedule state: the last enqueued tick per entry."
    ),
    CollectionSpec(
        AUTH_USERS,
        rule=AUTH_USER_RULE,
        purpose=(
            "Accounts (replaces Django's SQLite auth_user, ADR-015): integer id as _key, Django "
            "password hash, staff flags. Never exposed by traversals (the graph uses `users`)."
        ),
        # Exact uniqueness, as Django's auth_user; sign-up also rejects case-insensitive twins.
        indexes=(
            _p("qw_auth_username", "username", unique=True),
            _p("qw_auth_username_ci", "username_ci"),
        ),
    ),
    CollectionSpec(
        SESSIONS,
        purpose=(
            "Django sessions (apps.accounts.sessions). Expiry checked on every read; the TTL "
            "index only removes expired sessions."
        ),
        indexes=(IndexSpec("qw_sessions_ttl", "ttl", ("expire_at",), expire_after=0),),
    ),
    CollectionSpec(ID_SEQUENCES, purpose="Monotonic integer id allocation (e.g. user ids)."),
    CollectionSpec(SCHEMA_META, purpose="Applied schema version bookkeeping."),
    CollectionSpec(EVENT_IN_REGION, edge=True, purpose="events -> regions"),
    CollectionSpec(EVENT_REPORTED_BY_NETWORK, edge=True, purpose="events -> networks"),
    CollectionSpec(USER_OWNS_RULE, edge=True, purpose="users -> alert_rules"),
    CollectionSpec(RULE_MATCHED_EVENT, edge=True, purpose="alert_rules -> events"),
)

EDGE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "edge_collection": EVENT_IN_REGION,
        "from_vertex_collections": [EVENTS],
        "to_vertex_collections": [REGIONS],
    },
    {
        "edge_collection": EVENT_REPORTED_BY_NETWORK,
        "from_vertex_collections": [EVENTS],
        "to_vertex_collections": [NETWORKS],
    },
    {
        "edge_collection": USER_OWNS_RULE,
        "from_vertex_collections": [USERS],
        "to_vertex_collections": [ALERT_RULES],
    },
    {
        "edge_collection": RULE_MATCHED_EVENT,
        "from_vertex_collections": [ALERT_RULES],
        "to_vertex_collections": [EVENTS],
    },
)

# Full-text search over place / region names for the explorer "location text" filter (FR-06).
EVENTS_SEARCH_VIEW_PROPERTIES: dict[str, Any] = {
    "links": {
        EVENTS: {
            "includeAllFields": False,
            "fields": {
                "place": {"analyzers": ["text_en"]},
                "derived": {"fields": {"region_name": {"analyzers": ["text_en", "identity"]}}},
            },
        }
    },
    "primarySort": [{"field": "occurred_at", "direction": "desc"}],
}


def collection_spec(name: str) -> CollectionSpec:
    for spec in COLLECTIONS:
        if spec.name == name:
            return spec
    raise KeyError(name)
