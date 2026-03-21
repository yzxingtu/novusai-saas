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
