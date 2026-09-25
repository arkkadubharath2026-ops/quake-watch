"""PostToolUse hook: format + lint-fix a Python file right after Claude edits it.

Reads the hook payload from stdin, runs ruff on the touched file only (fast), and
reports remaining lint findings back to Claude via stderr + exit code 2 so they are
fixed immediately instead of accumulating. Never fails the session if ruff is absent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def find_ruff(project_dir: Path) -> str | None:
    for candidate in (
        project_dir / ".venv" / "Scripts" / "ruff.exe",
        project_dir / ".venv" / "bin" / "ruff",
    ):
        if candidate.exists():
            return str(candidate)
    return shutil.which("ruff")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path.endswith(".py"):
        return 0
    path = Path(file_path)
    if not path.exists() or ".venv" in path.parts:
        return 0
    project_dir = Path(payload.get("cwd") or ".").resolve()
    ruff = find_ruff(project_dir)
    if ruff is None:
        return 0
    # Run from the project root with a relative path so pyproject per-file-ignores globs match
    # (absolute Windows paths with a lower-case drive letter do not).
    try:
        target = str(path.resolve().relative_to(project_dir))
    except ValueError:
        target = str(path)
    subprocess.run([ruff, "format", "--quiet", target], check=False, cwd=project_dir)
    result = subprocess.run(
        [ruff, "check", "--fix", "--quiet", "--output-format", "concise", target],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_dir,
    )
    if result.returncode != 0 and result.stdout.strip():
        sys.stderr.write("ruff found issues it could not auto-fix:\n" + result.stdout)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
