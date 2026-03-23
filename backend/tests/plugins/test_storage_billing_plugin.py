from __future__ import annotations

import pytest

from app.plugins.loader import PluginLoader
from app.plugins.module_loader import load_plugin_handler, load_plugin_module


def test_storage_billing_manifest_loads() -> None:
    manifest = PluginLoader().load_manifest("storage-billing")

    assert manifest.name == "storage-billing"
    assert "platform:read" in manifest.capabilities
    assert "config:write" in manifest.capabilities
    assert manifest.extensions.custom[0].type == "tenant_menu_policy"
    assert manifest.extensions.tasks[0].cron_expression == "0 3 * * *"
    assert manifest.config_schema is not None
    assert len(manifest.extensions.api.admin_routes) >= 8
    assert len(manifest.extensions.frontend.pages) == 2
    assert manifest.extensions.frontend.release.manifest == "plugin.manifest.json"


@pytest.mark.asyncio
async def test_storage_billing_overview_service_scaffold() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingOverviewService(db=None, host_read=None)
    overview = await service.build_admin_overview()

    assert overview["billable_drivers"] == [
        "qiniu-kodo",
        "aliyun-oss",
        "tencent-cos",
    ]
    assert overview["excluded_drivers"] == ["local"]
    assert overview["reconciliation_schedule"]["local_time"] == "03:00"
    assert overview["reconciliation_schedule"]["official_billing_lag_days"] is None
    assert overview["reconciliation_schedule"]["official_target_rule"] == "per-provider"
    assert overview["reconciliation_schedule"]["provider_rules"]["aliyun-oss"]["official_target_rule"] == "D-3"


def test_storage_billing_task_handler_loads() -> None:
    handler = load_plugin_handler("storage-billing", "tasks.run_daily_reconciliation")
    assert handler is not None
