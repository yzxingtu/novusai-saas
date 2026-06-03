from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions.base import BusinessException
from app.services.system.plugin_admin_workflow_service import (
    PluginAdminWorkflowService,
)


@pytest.mark.asyncio
async def test_enable_plugin_applies_menu_overrides_and_notifies(monkeypatch) -> None:
    notify = AsyncMock()
    monkeypatch.setattr("app.services.common.notification_service.notify", notify)

    workflow = PluginAdminWorkflowService.__new__(PluginAdminWorkflowService)
    workflow._db = SimpleNamespace()
    workflow._plugin_service = SimpleNamespace(
        enable_plugin=AsyncMock(),
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(display_name="Demo Plugin", name="demo")
        ),
    )
    workflow._cleanup_service = SimpleNamespace()
    workflow._lifecycle = SimpleNamespace(update_menu_overrides=AsyncMock())

    await workflow.enable_plugin(
        plugin_id=7,
        admin_id=11,
        menu_overrides=[
            SimpleNamespace(
                name="demo_menu",
                parent="system_maintenance",
                tenant_parent="workspace",
            )
        ],
    )

    workflow._lifecycle.update_menu_overrides.assert_awaited_once_with(
        7,
        menu_overrides={
            "demo_menu": {
                "parent": "system_maintenance",
                "tenant_parent": "workspace",
            }
        },
        refresh_runtime=False,
    )
    workflow._plugin_service.enable_plugin.assert_awaited_once_with(
        7,
        operator_id=11,
    )
    notify.assert_awaited_once_with(
        workflow._db,
        "biz.plugin_enabled",
        [("admin", 11)],
        data={"plugin_name": "Demo Plugin"},
    )


@pytest.mark.asyncio
async def test_uninstall_plugin_returns_deleted_already_message() -> None:
    workflow = PluginAdminWorkflowService.__new__(PluginAdminWorkflowService)
    workflow._db = SimpleNamespace()
    workflow._plugin_service = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    workflow._cleanup_service = SimpleNamespace()
    workflow._lifecycle = SimpleNamespace()

    message = await workflow.uninstall_plugin(
        plugin_id=9,
        admin_id=1,
        confirm_data_delete=False,
        cleanup_dependencies=False,
    )

    assert message is not None
    assert "9" in message


@pytest.mark.asyncio
async def test_refresh_plugin_schedules_commits(monkeypatch) -> None:
    workflow = PluginAdminWorkflowService.__new__(PluginAdminWorkflowService)
    workflow._db = SimpleNamespace(commit=AsyncMock())
    workflow._plugin_service = SimpleNamespace(
        refresh_plugin_schedules=AsyncMock(return_value={"refreshed": 3})
    )
    workflow._cleanup_service = SimpleNamespace()
    workflow._lifecycle = SimpleNamespace()

    result = await workflow.refresh_plugin_schedules(
        plugin_id=5,
        admin_id=2,
    )

    assert result == {"refreshed": 3}
    workflow._plugin_service.refresh_plugin_schedules.assert_awaited_once_with(
        5,
        operator_id=2,
    )
    workflow._db.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_activate_license_raises_on_failed_activation(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.plugins.license.activate_license",
        AsyncMock(return_value={"success": False, "message": "license invalid"}),
    )

    workflow = PluginAdminWorkflowService.__new__(PluginAdminWorkflowService)
    workflow._db = SimpleNamespace()
    workflow._plugin_service = SimpleNamespace()
    workflow._cleanup_service = SimpleNamespace()
    workflow._lifecycle = SimpleNamespace()

    with pytest.raises(BusinessException) as exc_info:
        await workflow.activate_license(plugin_id=3, license_key="bad-key")

    assert "license invalid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_icon_reads_file_and_delegates() -> None:
    workflow = PluginAdminWorkflowService.__new__(PluginAdminWorkflowService)
    workflow._db = SimpleNamespace()
    workflow._plugin_service = SimpleNamespace()
    workflow._cleanup_service = SimpleNamespace(
        save_plugin_icon=AsyncMock(return_value="icon.svg")
    )
    workflow._lifecycle = SimpleNamespace()

    file = SimpleNamespace(filename="icon.svg", read=AsyncMock(return_value=b"svg"))

    icon = await workflow.upload_icon(plugin_id=12, file=file)

    assert icon == "icon.svg"
    file.read.assert_awaited_once_with()
    workflow._cleanup_service.save_plugin_icon.assert_awaited_once_with(
        12,
        filename="icon.svg",
        content=b"svg",
    )
