"""ArangoDB persistence infrastructure.

``Database`` (any handle, including stream transactions) and ``StandardDatabase`` (a handle that
can open transactions) are re-exported so services can type their dependencies without importing
python-arango directly (architecture boundary).
"""

from arango.database import Database, StandardDatabase

__all__ = ["Database", "StandardDatabase"]
