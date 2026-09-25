"""Print the Project Dashboard, computed from docs/PROGRESS.md, git and the last test run.

Nothing here is estimated: milestone percentages are ticked / total tasks in docs/PROGRESS.md,
overall progress is the mean of the milestone percentages, and test/coverage figures come from
var/test-status.json (written by tests/conftest.py) and the .coverage data file.

    .venv/Scripts/python scripts/dashboard.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "docs" / "PROGRESS.md"
TEST_STATUS = ROOT / "var" / "test-status.json"
BAR_WIDTH = 20

HEADING = re.compile(r"^##\s+(L\d)\s+(.+?)\s*$")
TASK = re.compile(r"^-\s+\[([ xX])\]\s+(.+?)\s*$")


@dataclass
class Milestone:
    code: str
    title: str
    done: list[str] = field(default_factory=list)
    todo: list[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        total = len(self.done) + len(self.todo)
        return 100.0 * len(self.done) / total if total else 0.0


def parse(text: str) -> list[Milestone]:
    milestones: list[Milestone] = []
    for line in text.splitlines():
        if heading := HEADING.match(line):
            milestones.append(Milestone(heading.group(1), heading.group(2)))
        elif (task := TASK.match(line)) and milestones:
            (milestones[-1].done if task.group(1) != " " else milestones[-1].todo).append(
                task.group(2)
            )
    return milestones


def bar(percent: float) -> str:
    filled = round(percent / 100 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603, S607
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def coverage_total() -> str:
    if not (ROOT / ".coverage").exists():
        return "no coverage data (run pytest with --cov)"
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "report", "--format=total"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return f"{result.stdout.strip()}%" if result.returncode == 0 else "coverage report failed"


def tests_line() -> str:
    if not TEST_STATUS.exists():
        return "no recorded test run"
    status = json.loads(TEST_STATUS.read_text())
    verdict = "GREEN" if status["exit_status"] == 0 else "RED"
    return (
        f"{verdict} — {status['passed']} passed, {status['failed']} failed, "
        f"{status['error']} errors, {status['skipped']} skipped (run {status['finished_at']})"
    )


def render(milestones: list[Milestone]) -> str:
    overall = sum(m.percent for m in milestones) / len(milestones) if milestones else 0.0
    done = sum(len(m.done) for m in milestones)
    total = done + sum(len(m.todo) for m in milestones)
    complete = sum(1 for m in milestones if not m.todo)
    next_milestone = next((m for m in milestones if m.todo), None)
    dirty = git("status", "--porcelain") not in ("", "unknown")
    lines = [
        "PROJECT DASHBOARD",
        f"Overall   {bar(overall)} {overall:5.1f}%  ({complete}/{len(milestones)} milestones, "
        f"{done}/{total} tasks)",
        "",
    ]
    lines += [
        f"{m.code} {m.title:<16} {bar(m.percent)} {m.percent:5.1f}%  "
        f"({len(m.done)}/{len(m.done) + len(m.todo)})"
        for m in milestones
    ]
    lines += ["", f"Completed tasks: {done}    Remaining tasks: {total - done}"]
    if next_milestone:
        lines.append(f"Remaining in {next_milestone.code} {next_milestone.title}:")
        lines += [f"  - {task}" for task in next_milestone.todo]
    lines += [
        "",
        f"Branch/commit: {git('rev-parse', '--abbrev-ref', 'HEAD')} @ "
        f"{git('log', '-1', '--format=%h %s')}{' (uncommitted changes)' if dirty else ''}",
        f"Tests:    {tests_line()}",
        f"Coverage: {coverage_total()}",
        "Next recommended milestone: "
        + (
            f"{next_milestone.code} {next_milestone.title}"
            if next_milestone
            else "none — all complete"
        ),
        "",
        "Reminder: run /compact now.",
    ]
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(render(parse(PROGRESS.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
