"""PreToolUse hook: block Claude from writing real secret files (.env, *.pem, *.key).

.env.example stays editable. Exit code 2 blocks the tool call and explains why.
"""

from __future__ import annotations

import json
import sys
from pathlib import PurePath

BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_SUFFIXES = {".pem", ".key"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return 0
    path = PurePath(file_path)
    if path.name in BLOCKED_NAMES or path.suffix in BLOCKED_SUFFIXES:
        sys.stderr.write(
            f"Blocked: {path.name} holds secrets and must not be edited by the agent. "
            "Change .env.example instead and ask the user to update their local .env.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
