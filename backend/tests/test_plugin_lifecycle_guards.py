"""Plugin lifecycle guard registry tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.lifecycle_guards import (
    get_plugin_lifecycle_guard_registry,
    run_plugin_lifecycle_guards,
)


@pytest.mark.asyncio
async def test_lifecycle_guard_registry_stops_on_first_denial():
    registry = get_plugin_lifecycle_guard_registry()
    registry.reset()
    registry = get_plugin_lifecycle_guard_registry()

    calls: list[str] = []

    async def deny_handler(_payload):
        calls.append("deny")
        return {
            "allowed": False,
            "reason_code": "storage_billing_open_run_exists",
            "message": "blocked",
            "details": {"plugin": "storage-billing"},
        }

    async def should_not_run(_payload):
        calls.append("never")
        return {
            "allowed": True,
            "reason_code": "allowed",
            "message": "",
            "details": {},
        }

    registry.register("deny", deny_handler, priority=10)
    registry.register("later", should_not_run, priority=20)

    result = await registry.run(
        {
            "operation": "disable",
            "plugin_id": 11,
            "plugin_name": "storage-billing",
            "force": False,
            "manifest": {},
        }
    )

    assert result["allowed"] is False
    assert result["reason_code"] == "storage_billing_open_run_exists"
    assert calls == ["deny"]


def _make_plugin(*, status: str):
    return type(
        "Plugin",
        (),
        {
            "id": 11,
            "name": "storage-billing",
            "status": status,
            "manifest": {},
            "granted_capabilities": [],
            "version": "0.1.0",
        },
    )()


def _make_db_with_plugin(plugin):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = plugin
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_disable_impl_runs_guards_before_storage_driver_check(monkeypatch):
    from app.enums.plugin import PluginStatusEnum
    from app.plugins import lifecycle as lifecycle_module
    from app.plugins.exceptions import PluginError
    from app.plugins.lifecycle import PluginLifecycle

    plugin = _make_plugin(status=PluginStatusEnum.ENABLED.value)
    lifecycle = PluginLifecycle(_make_db_with_plugin(plugin))
    lifecycle._get_dependents = AsyncMock(return_value=[])
    lifecycle._check_storage_driver_in_use = AsyncMock()

    monkeypatch.setattr(
        lifecycle_module,
        "run_plugin_lifecycle_guards",
        AsyncMock(
            return_value={
                "allowed": False,
                "reason_code": "storage_billing_open_run_exists",
                "message": "blocked by guard",
                "details": {"plugin": "storage-billing"},
            }
        ),
    )

    with pytest.raises(PluginError) as exc_info:
        await lifecycle._disable_impl(11, operator_id=None)

    assert exc_info.value.data["reason_code"] == "storage_billing_open_run_exists"
    lifecycle._check_storage_driver_in_use.assert_not_awaited()


@pytest.mark.asyncio
async def test_uninstall_impl_runs_guards_before_cleanup(monkeypatch):
    from app.enums.plugin import PluginStatusEnum
    from app.plugins import lifecycle as lifecycle_module
    from app.plugins.exceptions import PluginError
    from app.plugins.lifecycle import PluginLifecycle

    plugin = _make_plugin(status=PluginStatusEnum.DISABLED.value)
    lifecycle = PluginLifecycle(_make_db_with_plugin(plugin))
    lifecycle._get_dependents = AsyncMock(return_value=[])
    lifecycle._disable_impl = AsyncMock()
    lifecycle._delete_plugin_permissions_from_db = AsyncMock()

    monkeypatch.setattr(
        lifecycle_module,
        "run_plugin_lifecycle_guards",
        AsyncMock(
            return_value={
                "allowed": False,
                "reason_code": "storage_billing_has_unsettled_statement",
                "message": "blocked by guard",
                "details": {"plugin": "storage-billing"},
            }
        ),
    )

    with pytest.raises(PluginError) as exc_info:
        await lifecycle._uninstall_impl(11, operator_id=None)

    assert exc_info.value.data["reason_code"] == "storage_billing_has_unsettled_statement"
    lifecycle._disable_impl.assert_not_awaited()
    lifecycle._delete_plugin_permissions_from_db.assert_not_awaited()


@pytest.mark.asyncio
async def test_runner_bootstraps_storage_billing_lifecycle_rules(monkeypatch):
    from app.plugins import feature_entitlement_guards as guard_module
    from app.plugins.lifecycle_guards import PluginLifecycleGuardRegistry

    PluginLifecycleGuardRegistry.reset()

    async def fake_get_active_feature_plan_summaries(_feature_flag: str):
        return [{"plan_id": 7, "plan_name": "Storage Billing Plan", "features": {}}]

    async def fake_get_plugin_status_map(_plugin_names):
        return {
            "qiniu-kodo": "enabled",
            "aliyun-oss": "disabled",
            "tencent-cos": "disabled",
        }

    monkeypatch.setattr(
        guard_module,
        "_get_active_feature_plan_summaries",
        fake_get_active_feature_plan_summaries,
    )
    monkeypatch.setattr(
        guard_module,
        "_get_plugin_status_map",
        fake_get_plugin_status_map,
    )

    result = await run_plugin_lifecycle_guards(
        {
            "operation": "disable",
            "plugin_id": 99,
            "plugin_name": "qiniu-kodo",
            "force": False,
            "manifest": {},
        }
    )

    assert result["allowed"] is False
    assert result["reason_code"] == "storage_billing_last_driver_blocked"
