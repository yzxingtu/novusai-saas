from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.module_loader import load_plugin_module


def _make_scalar_result(item):
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


def _make_scalars_result(items):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_create_binding_sets_invalid_status_for_qiniu_pass_through(monkeypatch):
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalar_result(None))
    plugin_db.flush = AsyncMock()
    plugin_db.refresh = AsyncMock()
    plugin_db.add = MagicMock()

    ctx = AsyncMock()
    ctx.get_db.return_value = plugin_db
    ctx.host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 7,
            "tenant_code": "tenant-7",
            "tenant_name": "Tenant 7",
            "plan_id": 2,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )

    service = module.StorageBillingBindingService.from_context(ctx)
    monkeypatch.setattr(
        service._profile_service,
        "get_provider_runtime_profile",
        AsyncMock(
            return_value={
                "enabled": True,
                "profile_code": "qiniu-default",
                "driver_enabled": True,
            }
        ),
    )
    monkeypatch.setattr(
        service._profile_service,
        "validate_provider_profile",
        AsyncMock(return_value={"errors": [], "warnings": []}),
    )

    result = await service.create_binding(
        {
            "tenant_id": 7,
            "provider_code": "qiniu-kodo",
            "scope_type": "bucket",
            "scope_value": "tenant-7-bucket",
            "billing_mode": "official_pass_through",
            "provider_profile_code": "qiniu-default",
        }
    )

    assert result["validation"]["validation_status"] == "invalid"
    plugin_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_validate_binding_refreshes_existing_binding(monkeypatch):
    module = load_plugin_module("storage-billing", "services.binding_service")
    binding_module = load_plugin_module("storage-billing", "models.binding")
    assert module is not None
    assert binding_module is not None

    binding = binding_module.StorageTenantBinding(
        tenant_id=9,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_pass_through",
        scope_type="bucket",
        scope_value="tenant-9-bucket",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    binding.id = 12

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalar_result(binding))
    plugin_db.flush = AsyncMock()
    plugin_db.refresh = AsyncMock()

    ctx = AsyncMock()
    ctx.get_db.return_value = plugin_db
    ctx.host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 9,
            "tenant_code": "tenant-9",
            "tenant_name": "Tenant 9",
            "plan_id": 3,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )

    service = module.StorageBillingBindingService.from_context(ctx)
    monkeypatch.setattr(
        service._profile_service,
        "get_provider_runtime_profile",
        AsyncMock(
            return_value={
                "enabled": True,
                "profile_code": "tencent-default",
                "driver_enabled": True,
            }
        ),
    )
    monkeypatch.setattr(
        service._profile_service,
        "validate_provider_profile",
        AsyncMock(return_value={"errors": [], "warnings": []}),
    )

    result = await service.validate_binding(12)

    assert result["validation"]["validation_status"] == "valid"
    plugin_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_reports_local_driver_not_billable():
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 21,
            "tenant_code": "tenant-21",
            "tenant_name": "Tenant 21",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={"storage_config": {"driver": "local"}}
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    result = await service.get_tenant_prerequisites(21)

    assert result["ok"] is True
    assert result["prerequisites"]["charge_local_storage"] is False
    assert result["prerequisites"]["ready"] is False
    assert "current_driver_not_billable" in result["prerequisites"]["missing_reasons"]
