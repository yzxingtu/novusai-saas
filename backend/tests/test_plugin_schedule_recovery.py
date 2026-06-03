"""Plugin schedule recovery regression tests. / 插件调度恢复。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.enums.plugin import PluginStatusEnum
from app.plugins.lifecycle import PluginLifecycle


class _ScalarOneResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_refresh_schedules_syncs_enabled_plugin_tasks() -> None:
    plugin = SimpleNamespace(
        id=11,
        name="demo-plugin",
        status=PluginStatusEnum.ENABLED.value,
        error_message=None,
        error_count=0,
        enabled_at=None,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarOneResult(plugin))
    db.flush = AsyncMock()

    lifecycle = PluginLifecycle(db)
    lifecycle._loader.load_manifest = lambda _name: SimpleNamespace(
        extensions=SimpleNamespace(tasks=[SimpleNamespace(name="digest")]),
    )
    lifecycle._sync_plugin_task_definitions = AsyncMock()

    result = await lifecycle._refresh_schedules_impl(plugin.id)

    lifecycle._sync_plugin_task_definitions.assert_awaited_once()
    assert result["mode"] == "sync_enabled"
    assert result["task_count"] == 1


@pytest.mark.asyncio
async def test_refresh_schedules_recovers_schedule_refresh_error_state() -> None:
    plugin = SimpleNamespace(
        id=22,
        name="demo-plugin",
        status=PluginStatusEnum.ERROR.value,
        error_message="Failed to refresh scheduled tasks for plugin demo-plugin after enable.",
        error_count=2,
        enabled_at=None,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarOneResult(plugin))
    db.flush = AsyncMock()

    lifecycle = PluginLifecycle(db)
    lifecycle._loader.load_manifest = lambda _name: SimpleNamespace(
        extensions=SimpleNamespace(tasks=[SimpleNamespace(name="digest")]),
    )
    lifecycle._sync_plugin_task_definitions = AsyncMock()

    result = await lifecycle._refresh_schedules_impl(plugin.id)

    lifecycle._sync_plugin_task_definitions.assert_awaited_once()
    assert result["mode"] == "recover_error"
    assert plugin.status == PluginStatusEnum.ENABLED.value
    assert plugin.error_message is None
    assert plugin.error_count == 0
    assert plugin.enabled_at is not None
