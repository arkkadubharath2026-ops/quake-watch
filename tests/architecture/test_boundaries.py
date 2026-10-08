"""Architecture fitness tests: enforce module boundaries from CLAUDE.md / docs/ARCHITECTURE.md.

- python-arango is imported only by repositories and apps/core/arango (persistence boundary).
- httpx is imported only by apps/ingestion/adapters (external API boundary).
- Pure domain modules (domain.py, services.py, policy/matcher modules, apps/geo) import no Django
  HTTP/DRF, no httpx and no python-arango.
- ArangoDB is the only stateful service: no application or config module imports Redis, Celery or
  Kombu (ADR-014).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / "apps"

PURE_MODULE_NAMES = {
    "domain.py",
    "services.py",
    "normalizer.py",
    "revision_policy.py",
    "differ.py",
    "matcher.py",
    "manifest.py",
    "enrichment.py",
    "networks.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _python_files() -> list[Path]:
    return [p for p in APPS.rglob("*.py") if "migrations" not in p.parts]


def _runtime_files() -> list[Path]:
    return _python_files() + sorted((ROOT / "config").glob("*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _is_repository(path: Path) -> bool:
    rel = _rel(path)
    return (
        path.name == "repository.py"
        or rel.startswith("apps/core/arango/")
        or ("/repositories/" in rel)
    )


def _starts(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


@pytest.mark.parametrize("path", _python_files(), ids=_rel)
def test_arango_only_in_persistence_layer(path: Path) -> None:
    if _is_repository(path) or "/management/commands/" in _rel(path):
        return
    offenders = [m for m in _imports(path) if _starts(m, "arango")]
    assert not offenders, f"{_rel(path)} imports python-arango directly: {offenders}"


@pytest.mark.parametrize("path", _python_files(), ids=_rel)
def test_httpx_only_in_adapters(path: Path) -> None:
    if _rel(path).startswith("apps/ingestion/adapters/"):
        return
    offenders = [m for m in _imports(path) if _starts(m, "httpx")]
    assert not offenders, f"{_rel(path)} calls external HTTP outside adapters: {offenders}"


def _pure_modules() -> list[Path]:
    files = [p for p in _python_files() if p.name in PURE_MODULE_NAMES]
    files += [p for p in (APPS / "geo").glob("*.py") if p.name not in {"apps.py", "__init__.py"}]
    return files


@pytest.mark.parametrize("path", _pure_modules(), ids=_rel)
def test_pure_modules_have_no_framework_or_io_imports(path: Path) -> None:
    banned = ("django.http", "django.shortcuts", "rest_framework", "httpx", "arango", "redis")
    offenders = [m for m in _imports(path) if any(_starts(m, b) for b in banned)]
    assert not offenders, f"{_rel(path)} (pure module) imports {offenders}"


@pytest.mark.parametrize("path", _runtime_files(), ids=_rel)
def test_no_redis_or_celery_at_runtime(path: Path) -> None:
    banned = ("redis", "celery", "kombu", "django_redis")
    offenders = [m for m in _imports(path) if any(_starts(m, b) for b in banned)]
    assert not offenders, f"{_rel(path)} imports {offenders}: ArangoDB is the only state store"
