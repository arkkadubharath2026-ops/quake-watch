"""Registry of named AQL queries.

Static queries are declared once as :class:`NamedQuery` objects next to the repository that runs
them. The registry lets us:

* EXPLAIN every query with representative bind values (``manage.py aql_explain``);
* assert in tests that hot paths use the intended indexes (ESD §6 "demonstrated with EXPLAIN");
* generate the query catalogue in docs/AQL_QUERIES.md from the code, so documentation cannot drift.

Dynamically composed queries (explorer search) register representative *variants* for the same
purposes; the builder itself only concatenates allow-listed fragments with bind variables.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Binds = dict[str, Any]


@dataclass(frozen=True, slots=True)
class NamedQuery:
    name: str
    category: str
    question: str
    aql: str
    sample_binds: Callable[[], Binds] = field(default=lambda: {})
    # The optimizer's plan must use at least one of these (it may legitimately pick between
    # candidate indexes depending on data selectivity); empty means no index expectation.
    expected_indexes: tuple[str, ...] = ()
    features: tuple[str, ...] = ()  # e.g. ("geo", "graph traversal", "aggregation")
    # Write queries are only ever EXPLAINed by tooling (catalogue, diagnostics), never executed.
    read_only: bool = True

    def plan_ok(self, used: list[str]) -> bool:
        return not self.expected_indexes or any(
            expected in name for expected in self.expected_indexes for name in used
        )


_REGISTRY: dict[str, NamedQuery] = {}


def register(query: NamedQuery) -> NamedQuery:
    existing = _REGISTRY.get(query.name)
    if existing is not None and existing.aql != query.aql:
        raise ValueError(f"duplicate named query {query.name!r} with different AQL")
    _REGISTRY[query.name] = query
    return query


def all_queries() -> list[NamedQuery]:
    return sorted(_REGISTRY.values(), key=lambda q: (q.category, q.name))


def get(name: str) -> NamedQuery:
    return _REGISTRY[name]
