"""插件 license 多记录查询稳定性的回归测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.plugins.context import PluginContext
from app.plugins.manifest import PluginManifest
from app.plugins.module_loader import load_plugin_module


class _ResultWithFirst:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return SimpleNamespace(first=lambda: self._item)

    def scalar_one_or_none(self):  # pragma: no cover - 不应被调用
        raise AssertionError("多行 license 查询不应使用 scalar_one_or_none")


@pytest.mark.asyncio
async def test_plugin_context_license_query_uses_first_record() -> None:
    manifest = PluginManifest(
        name="demo-plugin",
        version="1.0.0",
        display_name={"en": "Demo Plugin"},
        scope="all_tenants",
    )

    plugin_id_result = SimpleNamespace(scalar_one_or_none=lambda: 100)
    license_record = SimpleNamespace(
        license_type="perpetual",
        is_valid=True,
        activated_at=None,
        trial_expires_at=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            plugin_id_result,
            _ResultWithFirst(license_record),
        ]
    )

    ctx = PluginContext(
        plugin_name="demo-plugin",
        manifest=manifest,
        db=db,
        granted_capabilities=[],
    )

    status = await ctx.get_own_license_status()

    assert status["is_valid"] is True
    assert status["status"] == "active"


@pytest.mark.asyncio
async def test_novusdoc_pro_license_service_uses_first_record() -> None:
    module = load_plugin_module("novusdoc-pro", "services.license_service")
    assert module is not None

    license_record = SimpleNamespace(
        license_type="standard",
        is_valid=True,
        license_key="NDOC-STD-XXXX-XXXX-XXXX-ABCD",
        activated_at=None,
        trial_expires_at=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ResultWithFirst(license_record))

    status = await module.get_license_status(db, plugin_id=1)

    assert status["is_valid"] is True
    assert status["status"] == module.LicenseStatus.ACTIVE
