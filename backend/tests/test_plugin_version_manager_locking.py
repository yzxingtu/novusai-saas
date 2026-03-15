"""VersionManager 锁使用与回滚缓存一致性的回归测试。 / Test."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.plugin import PluginStatusEnum
from app.plugins.version_manager import VersionManager


@pytest.mark.asyncio
async def test_upgrade_uses_plugin_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = VersionManager(AsyncMock())
    calls: dict[str, object] = {}

    @asynccontextmanager
    async def fake_lock(plugin_id: int):
        calls["lock_plugin_id"] = plugin_id
        calls["entered"] = True
        yield
        calls["exited"] = True

    async def fake_upgrade_unlocked(plugin_id: int, new_source: Path) -> None:
        calls["upgrade_args"] = (plugin_id, new_source)

    monkeypatch.setattr("app.plugins.lifecycle._plugin_lock", fake_lock)
    monkeypatch.setattr(manager, "_upgrade_unlocked", fake_upgrade_unlocked)

    source = Path("dummy-upgrade-source")
    await manager.upgrade(11, source)

    assert calls["lock_plugin_id"] == 11
    assert calls["upgrade_args"] == (11, source)
    assert calls["entered"] is True
    assert calls["exited"] is True


@pytest.mark.asyncio
async def test_rollback_uses_plugin_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = VersionManager(AsyncMock())
    calls: dict[str, object] = {}

    @asynccontextmanager
    async def fake_lock(plugin_id: int):
        calls["lock_plugin_id"] = plugin_id
        calls["entered"] = True
        yield
        calls["exited"] = True

    async def fake_rollback_unlocked(plugin_id: int, target_version: str) -> None:
        calls["rollback_args"] = (plugin_id, target_version)

    monkeypatch.setattr("app.plugins.lifecycle._plugin_lock", fake_lock)
    monkeypatch.setattr(manager, "_rollback_unlocked", fake_rollback_unlocked)

    await manager.rollback(22, "1.0.0")

    assert calls["lock_plugin_id"] == 22
    assert calls["rollback_args"] == (22, "1.0.0")
    assert calls["entered"] is True
    assert calls["exited"] is True


@pytest.mark.asyncio
async def test_rollback_unlocked_unloads_plugin_modules_after_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plugin_name = "demo-plugin"
    plugins_root = tmp_path / "plugins"
    versions_root = plugins_root / ".versions"
    target_dir = plugins_root / plugin_name
    backup_dir = versions_root / plugin_name / "1.0.0"

    target_dir.mkdir(parents=True)
    (target_dir / "stale.txt").write_text("old", encoding="utf-8")
    backup_dir.mkdir(parents=True)
    (backup_dir / "plugin.yaml").write_text("name: demo-plugin", encoding="utf-8")

    # 覆盖 VersionManager 使用的模块级常量。
    monkeypatch.setattr("app.plugins.version_manager.PLUGINS_DIR", plugins_root)
    monkeypatch.setattr("app.plugins.version_manager.VERSIONS_DIR", versions_root)
    # 保持 PluginLoader 默认根目录与补丁后的 plugins 根目录一致。
    monkeypatch.setattr("app.plugins.loader.PLUGINS_DIR", plugins_root)

    plugin = SimpleNamespace(
        id=1,
        name=plugin_name,
        version="2.0.0",
        status=PluginStatusEnum.DISABLED.value,
        manifest={},
    )
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = plugin

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)
    db.flush = AsyncMock()

    manager = VersionManager(db)

    # archive_version 不是本用例关注点，替换为桩函数避免重复操作备份目录。
    monkeypatch.setattr(
        manager,
        "archive_version",
        lambda _plugin_name, _version: versions_root / _plugin_name / _version,
    )

    unloaded: list[str] = []
    monkeypatch.setattr(
        "app.plugins.module_loader.unload_plugin_modules",
        lambda name: unloaded.append(name),
    )

    class _DummyManifest:
        def model_dump(self) -> dict[str, str]:
            return {"name": plugin_name, "version": "1.0.0"}

    class _DummyLoader:
        def load_manifest(self, _name: str) -> _DummyManifest:
            return _DummyManifest()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", lambda: _DummyLoader())

    await manager._rollback_unlocked(plugin_id=1, target_version="1.0.0")

    assert unloaded == [plugin_name]
    assert plugin.version == "1.0.0"
    assert (target_dir / "plugin.yaml").is_file()
    db.flush.assert_awaited_once()
