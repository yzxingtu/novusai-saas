"""Startup discover/restore boundary tests. / 启动 discover/restore 边界测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.enums.plugin import PluginStatusEnum
from app.plugins.exceptions import PluginSecurityError
from app.plugins.startup import discover_and_register, restore_enabled_plugins


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


def _base_manifest(version: str = "1.0.0") -> dict:
    return {
        "name": "demo-plugin",
        "version": version,
        "display_name": {"en": "Demo Plugin"},
        "scope": "all_tenants",
        "capabilities": ["db:read"],
    }


@pytest.mark.asyncio
async def test_discover_only_marks_sync_required_without_hot_syncing_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_plugin = SimpleNamespace(
        name="demo-plugin",
        version="1.0.0",
        manifest=_base_manifest(version="1.0.0"),
        granted_capabilities=["db:write"],
        error_message=None,
        status=PluginStatusEnum.INSTALLED.value,
    )

    updated_manifest = _base_manifest(version="1.0.0")
    updated_manifest["display_name"] = {"en": "Demo Plugin Updated"}

    class _Loader:
        def __init__(self):
            self.plugins_dir = Path(".")

        def discover_plugins(self):
            return ["demo-plugin"]

        def load_manifest(self, _plugin_name: str):
            from app.plugins.manifest import PluginManifest

            return PluginManifest.model_validate(updated_manifest)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([existing_plugin]))
    db.flush = AsyncMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: None,
    )

    result = await discover_and_register(db)

    assert result == {
        "discovered": 0,
        "sync_required": 1,
        "upgrade_required": 0,
        "missing": 0,
        "failed": 0,
    }
    assert existing_plugin.manifest == _base_manifest(version="1.0.0")
    assert existing_plugin.granted_capabilities == ["db:write"]
    assert "sync-manifest" in existing_plugin.error_message
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_refuses_disk_version_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    plugin = SimpleNamespace(
        id=7,
        name="demo-plugin",
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
            _RowsResult([("demo-plugin", "drift")]),
        ]
    )

    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "demo-plugin" / "frontend" / "dist").mkdir(
        parents=True, exist_ok=True
    )
    (plugins_dir / "demo-plugin" / "frontend" / "dist" / "index.js").write_text(
        "window.demo = {};\n", encoding="utf-8"
    )
    (
        plugins_dir / "demo-plugin" / "frontend" / "dist" / "plugin.manifest.json"
    ).write_text(
        '{"format":"novus.plugin.release.v1","entry":"index.js","global_var":"NovusPlugin_demo_plugin","css":[]}',
        encoding="utf-8",
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = plugins_dir

        def load_manifest(self, _plugin_name: str):
            from app.plugins.manifest import PluginManifest

            manifest = _base_manifest(version="1.1.0")
            manifest["extensions"] = {
                "frontend": {
                    "release": {"manifest": "plugin.manifest.json"},
                    "pages": [
                        {
                            "name": "demo",
                            "path": "/admin/plugins/demo-plugin/page",
                            "component": "DemoPage",
                            "scope": "admin",
                            "title": {"en": "Demo"},
                        }
                    ],
                }
            }
            return PluginManifest.model_validate(manifest)

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.license.get_plugin_runtime_license_status",
        AsyncMock(return_value={"runtime_allowed": True, "status": "not_required"}),
    )

    result = await restore_enabled_plugins(
        db,
        run_heavy=True,
        mutate_db_status=True,
    )

    assert result == {"restored": 0, "failed": 1, "total": 1}
    assert plugin.status == PluginStatusEnum.ERROR.value
    assert "Formal upgrade is required" in (plugin.error_message or "")


@pytest.mark.asyncio
async def test_discover_reconciles_stale_scope_error_when_manifest_is_now_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.manifest import PluginManifest

    canonical_manifest = PluginManifest.model_validate(
        {
            "name": "weather-widget",
            "version": "1.0.0",
            "display_name": {"en": "Weather Widget"},
            "scope": "admin_and_selected_tenants",
            "capabilities": [],
        }
    ).model_dump()

    existing_plugin = SimpleNamespace(
        name="weather-widget",
        version="1.0.0",
        manifest=canonical_manifest,
        granted_capabilities=[],
        error_message="Startup restore failed: invalid scope admin_and_assigned",
        error_count=3,
        status=PluginStatusEnum.ERROR.value,
        enabled_at=None,
    )

    class _Loader:
        def __init__(self):
            self.plugins_dir = Path(".")

        def discover_plugins(self):
            return ["weather-widget"]

        def load_manifest(self, _plugin_name: str):
            return PluginManifest.model_validate(canonical_manifest)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([existing_plugin]))
    db.flush = AsyncMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: None,
    )

    result = await discover_and_register(db)

    assert result == {
        "discovered": 0,
        "sync_required": 0,
        "upgrade_required": 0,
        "missing": 0,
        "failed": 0,
    }
    assert existing_plugin.status == PluginStatusEnum.INSTALLED.value
    assert existing_plugin.error_message is None
    assert existing_plugin.error_count == 0
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_fail_closes_new_plugin_when_security_scan_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Loader:
        def __init__(self):
            self.plugins_dir = Path(".")

        def discover_plugins(self):
            return ["demo-plugin"]

        def load_manifest(self, _plugin_name: str):
            from app.plugins.manifest import PluginManifest

            return PluginManifest.model_validate(_base_manifest())

    db = AsyncMock()
    db.add = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([]))
    db.flush = AsyncMock()

    monkeypatch.setattr("app.plugins.loader.PluginLoader", _Loader)
    monkeypatch.setattr(
        "app.plugins.startup._assert_startup_security_clean",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PluginSecurityError(message="blocked by security scan")
        ),
    )

    result = await discover_and_register(db)

    assert result == {
        "discovered": 0,
        "sync_required": 0,
        "upgrade_required": 0,
        "missing": 0,
        "failed": 1,
    }
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
