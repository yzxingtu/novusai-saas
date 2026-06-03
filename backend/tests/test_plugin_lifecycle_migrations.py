"""Test type: structural
Scope: plugin lifecycle Alembic migration execution.
Real dependencies: LifecycleMigrationMixin script generation.
Mocked dependencies: subprocess runner and migration path discovery.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.plugins.lifecycle_migrations as lifecycle_migrations
from app.plugins.lifecycle_migrations import LifecycleMigrationMixin


class _LifecycleHarness(LifecycleMigrationMixin):
    def __init__(self) -> None:
        self._db = AsyncMock()


@pytest.mark.asyncio
async def test_run_alembic_upgrade_does_not_stamp_duplicate_table_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_scripts: list[str] = []

    async def _fake_subprocess(*args, **_kwargs):
        captured_scripts.append(str(args[2]))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(lifecycle_migrations, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(
        lifecycle_migrations,
        "build_migration_version_locations",
        lambda **_kwargs: [str(tmp_path / "plugins" / "demo-plugin")],
    )
    monkeypatch.setattr(lifecycle_migrations, "run_subprocess_async", _fake_subprocess)

    await _LifecycleHarness().run_alembic_upgrade("demo-plugin")

    assert captured_scripts
    script = captured_scripts[0]
    assert "command.upgrade(cfg, target)" in script
    assert "command.stamp" not in script
    assert "DuplicateTable" not in script
    assert "already exists" not in script


def test_run_alembic_upgrade_does_not_auto_purge_version_stamps() -> None:
    """中文: Test type: structural. 插件升级不得修补 alembic_version。

    EN: Test type: structural. Plugin upgrade must not repair alembic_version.
    """
    source = inspect.getsource(LifecycleMigrationMixin.run_alembic_upgrade)

    assert "purge_orphaned" not in source
    assert "DELETE FROM alembic_version" not in source
