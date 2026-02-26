"""插件服务 license 激活路径的回归测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.system import plugin_service as plugin_service_module
from app.services.system.plugin_service import PluginService


@pytest.mark.asyncio
async def test_plugin_service_activate_license_uses_unified_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    service = PluginService(db)

    calls: dict[str, object] = {}

    async def _fake_activate(plugin_id: int, license_key: str, db_session):
        calls["args"] = (plugin_id, license_key, db_session)
        return {"success": True, "message": "ok"}

    monkeypatch.setattr("app.plugins.license.activate_license", _fake_activate)

    await service.activate_license(7, "NOVUS-test-key")

    assert calls["args"] == (7, "NOVUS-test-key", db)


@pytest.mark.asyncio
async def test_plugin_service_activate_license_raises_business_exception_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    service = PluginService(db)

    async def _fake_activate(plugin_id: int, license_key: str, db_session):
        _ = (plugin_id, license_key, db_session)
        return {"success": False, "message": "Invalid license key"}

    monkeypatch.setattr("app.plugins.license.activate_license", _fake_activate)

    with pytest.raises(plugin_service_module.BusinessException) as exc_info:
        await service.activate_license(8, "invalid")

    assert "Invalid license key" in str(exc_info.value)
