"""Manifest sync service tests. / manifest 显式同步服务测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.system.plugin_service import PluginService


def _manifest_payload(display_name: str, *, version: str = "1.0.0") -> dict:
    return {
        "name": "demo-plugin",
        "version": version,
        "display_name": {"en": display_name},
        "description": {"en": f"{display_name} description"},
        "scope": "all_tenants",
        "capabilities": ["db:write"],
    }


@pytest.mark.asyncio
async def test_sync_manifest_updates_snapshot_but_keeps_granted_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    service = PluginService(db)

    plugin = SimpleNamespace(
        id=1,
        name="demo-plugin",
        version="1.0.0",
        display_name="Old",
        description="Old desc",
        author=None,
        icon=None,
        icon_color=None,
        homepage=None,
        repository_url=None,
        license_text=None,
        tags=[],
        scope="all_tenants",
        manifest=_manifest_payload("Old"),
        ai_requirements=None,
        pricing_type="free",
        pricing_info=None,
        installed_packages=[],
        granted_capabilities=["db:read"],
        status="installed",
        config={},
    )

    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=plugin)
    from app.plugins.manifest import PluginManifest

    service._loader = MagicMock()
    service._loader.load_manifest.return_value = PluginManifest.model_validate(
        _manifest_payload("New"),
    )
    service._loader.plugins_dir = MagicMock()

    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: {"has_frontend": False, "mode": "none"},
    )

    await service.sync_manifest(1)

    assert plugin.display_name == "New"
    assert plugin.description == "New description"
    assert plugin.manifest["display_name"]["en"] == "New"
    assert plugin.granted_capabilities == ["db:read"]
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_manifest_clears_disabled_plugin_manifest_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    service = PluginService(db)

    plugin = SimpleNamespace(
        id=1,
        name="demo-plugin",
        version="1.0.0",
        display_name="Old",
        description="Old desc",
        author=None,
        icon=None,
        icon_color=None,
        homepage=None,
        repository_url=None,
        license_text=None,
        tags=[],
        scope="all_tenants",
        manifest=_manifest_payload("Old"),
        ai_requirements=None,
        pricing_type="free",
        pricing_info=None,
        installed_packages=[],
        granted_capabilities=[],
        status="disabled",
        enabled_at=None,
        error_message="Manifest drift detected on disk. Run explicit sync-manifest to apply non-version changes.",
        error_count=1,
        config={},
    )

    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=plugin)
    from app.plugins.manifest import PluginManifest

    service._loader = MagicMock()
    service._loader.load_manifest.return_value = PluginManifest.model_validate(
        _manifest_payload("New"),
    )
    service._loader.plugins_dir = MagicMock()

    monkeypatch.setattr(
        "app.plugins.frontend_contract.validate_runtime_frontend_contract",
        lambda *_args, **_kwargs: {"has_frontend": False, "mode": "none"},
    )

    await service.sync_manifest(1)

    assert plugin.status == "disabled"
    assert plugin.error_message is None
    assert plugin.error_count == 0
    assert plugin.manifest["display_name"]["en"] == "New"
    assert db.flush.await_count == 2


@pytest.mark.asyncio
async def test_sync_manifest_rejects_disk_version_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    service = PluginService(db)

    plugin = SimpleNamespace(
        id=1,
        name="demo-plugin",
        version="1.0.0",
        manifest=_manifest_payload("Old"),
        granted_capabilities=["db:read"],
        status="installed",
        config={},
    )

    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=plugin)
    from app.plugins.manifest import PluginManifest

    service._loader = MagicMock()
    service._loader.load_manifest.return_value = PluginManifest.model_validate(
        _manifest_payload("New", version="1.1.0"),
    )
    service._loader.plugins_dir = MagicMock()

    with pytest.raises(Exception, match="Use formal upgrade"):
        await service.sync_manifest(1)


@pytest.mark.asyncio
async def test_update_plugin_config_uses_latest_disk_schema_without_syncing_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    service = PluginService(db)

    old_manifest = _manifest_payload("Old")
    old_manifest["config_schema"] = {
        "type": "object",
        "properties": {
            "legacy": {"type": "string"},
        },
    }
    new_manifest = _manifest_payload("New")
    new_manifest["config_schema"] = {
        "type": "object",
        "properties": {
            "api_key": {"type": "string"},
        },
    }

    plugin = SimpleNamespace(
        id=1,
        name="demo-plugin",
        manifest=old_manifest,
        config={},
    )

    service.repo = MagicMock()
    service.repo.get_by_id = AsyncMock(return_value=plugin)

    from app.plugins.manifest import PluginManifest

    service._loader = MagicMock()
    service._loader.load_manifest.return_value = PluginManifest.model_validate(
        new_manifest,
    )

    seen: dict[str, object] = {}

    def _capture_validate(config: dict, schema: dict) -> None:
        seen["config"] = config
        seen["schema"] = schema

    monkeypatch.setattr(service, "_validate_config_against_schema", _capture_validate)
    monkeypatch.setattr(
        "app.plugins.crypto.encrypt_plugin_config",
        lambda config, _schema: config,
    )

    await service.update_plugin_config(1, {"api_key": "secret"})

    assert seen["config"] == {"api_key": "secret"}
    assert seen["schema"] == new_manifest["config_schema"]
    assert plugin.manifest == old_manifest
    assert plugin.config == {"api_key": "secret"}
    db.flush.assert_awaited_once()
