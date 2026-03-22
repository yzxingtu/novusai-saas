"""Regression tests for startup restore owner/non-owner modes. / 测试"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.plugin import PluginStatusEnum
from app.plugins.startup import restore_enabled_plugins


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _build_manifest(
    *,
    python_deps: list[str] | None = None,
    version: str = "1.0.0",
):
    return SimpleNamespace(
        version=version,
        dependencies=SimpleNamespace(python=python_deps or []),
        compatibility=None,
        extensions=SimpleNamespace(frontend=SimpleNamespace()),
    )


@pytest.mark.asyncio
async def test_restore_owner_mode_runs_heavy_and_mutates_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=1,
        name="demo-plugin",
        version="1.0.0",
        status=PluginStatusEnum.ENABLED.value,
        pricing_type="free",
        error_count=2,
        error_message="old error",
        config={},
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([plugin]),  # enabled plugins query
            _RowsResult([]),  # ERROR summary query
        ]
    )

    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "demo-plugin" / "backend" / "migrations" / "versions").mkdir(
        parents=True, exist_ok=True
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = plugins_dir

        def load_manifest(self, _plugin_name: str):
            return _build_manifest(python_deps=["pydantic"])

    lifecycle_instances: list[object] = []

    class _Lifecycle:
        def __init__(self, _db):
            self.run_alembic_upgrade = AsyncMock()
            lifecycle_instances.append(self)

    registry = MagicMock()
    registry.get_registered_count.return_value = 3

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr("app.plugins.lifecycle.PluginLifecycle", _Lifecycle)
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [],
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=True,
        mutate_db_status=True,
    )

    assert len(lifecycle_instances) == 1
    lifecycle = lifecycle_instances[0]
    lifecycle.run_alembic_upgrade.assert_awaited_once_with("demo-plugin")

    assert plugin.error_count == 0
    assert plugin.error_message is None
    db.flush.assert_awaited_once()

    assert result == {"restored": 1, "failed": 0, "total": 1}


@pytest.mark.asyncio
async def test_restore_non_owner_mode_is_register_only_and_no_db_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=2,
        name="demo-plugin",
        version="1.0.0",
        status=PluginStatusEnum.ENABLED.value,
        pricing_type="free",
        error_count=5,
        error_message="keep me",
        config={},
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([plugin]),  # enabled plugins query
        ]
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = tmp_path / "plugins"

        def load_manifest(self, _plugin_name: str):
            return _build_manifest(python_deps=["pydantic"])

    lifecycle_instances: list[object] = []

    class _Lifecycle:
        def __init__(self, _db):
            lifecycle_instances.append(self)

    registry = MagicMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr("app.plugins.lifecycle.PluginLifecycle", _Lifecycle)

    def _raise_register(*_args, **_kwargs):
        raise RuntimeError("register failed")

    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        _raise_register,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [],
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=False,
        mutate_db_status=False,
    )

    # 非 owner 模式不应实例化生命周期重操作对象
    assert lifecycle_instances == []

    assert plugin.status == PluginStatusEnum.ENABLED.value
    assert plugin.error_count == 5
    assert plugin.error_message == "keep me"
    assert db.flush.await_count == 0

    assert result == {"restored": 0, "failed": 1, "total": 1}


@pytest.mark.asyncio
async def test_restore_skips_license_inactive_plugins_and_disables_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=3,
        name="paid-plugin",
        version="1.0.0",
        status=PluginStatusEnum.ENABLED.value,
        pricing_type="paid",
        error_count=4,
        error_message="old",
        config={},
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([plugin]),
            _RowsResult([]),
        ]
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = tmp_path / "plugins"

        def load_manifest(self, _plugin_name: str):
            raise AssertionError("license inactive plugin should not continue loading manifest")

    registry = MagicMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": False, "status": "expired", "message": "License expired"}),
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=True,
        mutate_db_status=True,
    )

    assert plugin.status == PluginStatusEnum.DISABLED.value
    assert plugin.error_message == "Startup restore skipped: License expired"
    assert plugin.error_count == 0
    db.flush.assert_awaited_once()
    assert result == {"restored": 0, "failed": 0, "total": 1}


@pytest.mark.asyncio
async def test_restore_marks_error_when_python_dependencies_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=4,
        name="broken-plugin",
        version="1.0.0",
        status=PluginStatusEnum.ENABLED.value,
        pricing_type="free",
        error_count=0,
        error_message=None,
        config={},
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([plugin]),
            _RowsResult(
                [
                    (
                        "broken-plugin",
                        "Startup restore failed: Dependency validation failed: impossible-lib missing or version mismatch",
                    )
                ]
            ),
        ]
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = tmp_path / "plugins"

        def load_manifest(self, _plugin_name: str):
            return _build_manifest(python_deps=["impossible-lib>=9.9.9"])

    registry = MagicMock()
    registry.get_registered_count.return_value = 0

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [],
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=True,
        mutate_db_status=True,
    )

    assert result == {"restored": 0, "failed": 1, "total": 1}
    assert plugin.status == PluginStatusEnum.ERROR.value
    assert "Dependency validation failed" in (plugin.error_message or "")


@pytest.mark.asyncio
async def test_restore_marks_error_when_alembic_upgrade_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=5,
        name="broken-migration-plugin",
        version="1.0.0",
        status=PluginStatusEnum.ENABLED.value,
        pricing_type="free",
        error_count=0,
        error_message=None,
        config={},
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([plugin]),
            _RowsResult([]),
        ]
    )

    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "broken-migration-plugin" / "backend" / "migrations" / "versions").mkdir(
        parents=True,
        exist_ok=True,
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = plugins_dir

        def load_manifest(self, _plugin_name: str):
            return _build_manifest()

    lifecycle_instances: list[object] = []

    class _Lifecycle:
        def __init__(self, _db):
            self.run_alembic_upgrade = AsyncMock(side_effect=RuntimeError("migration boom"))
            lifecycle_instances.append(self)

    registry = MagicMock()
    register_all_extensions = MagicMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )
    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr("app.plugins.lifecycle.PluginLifecycle", _Lifecycle)
    monkeypatch.setattr(
        "app.plugins._extension_registrar.register_all_extensions",
        register_all_extensions,
    )
    monkeypatch.setattr(
        "app.plugins._extension_registrar.get_failed_extensions",
        lambda _plugin_name: [],
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=True,
        mutate_db_status=True,
    )

    assert len(lifecycle_instances) == 1
    lifecycle = lifecycle_instances[0]
    lifecycle.run_alembic_upgrade.assert_awaited_once_with("broken-migration-plugin")
    register_all_extensions.assert_not_called()
    db.flush.assert_awaited_once()
    assert result == {"restored": 0, "failed": 1, "total": 1}
    assert plugin.status == PluginStatusEnum.ERROR.value
    assert plugin.error_count == 1
    assert plugin.error_message == "Startup restore failed: migration boom"
