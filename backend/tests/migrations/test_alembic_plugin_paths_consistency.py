"""CLI / env.py / purge 使用同一插件 migrations 根目录 / Alembic plugin path alignment."""

from __future__ import annotations

from pathlib import Path

from app.cli_commands.core_commands import (
    _BACKEND_DIR,
    _discover_plugin_migration_paths,
)


def _expected_plugin_version_dirs(backend: Path) -> list[str]:
    plugins = backend / "plugins"
    if not plugins.is_dir():
        return []
    out: list[str] = []
    for d in sorted(plugins.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        v = d / "backend" / "migrations" / "versions"
        if v.is_dir():
            out.append(str(v.resolve()))
    return out


def test_discover_plugin_migration_paths_matches_env_py_strategy() -> None:
    """与 backend/migrations/env.py 中 sorted(plugins.iterdir()) + versions 判定一致。"""
    cli_paths = {str(Path(p).resolve()) for p in _discover_plugin_migration_paths()}
    expected = set(_expected_plugin_version_dirs(_BACKEND_DIR))
    assert cli_paths == expected
