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
    ctx.host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "qiniu-kodo"},
        }
    )
    ctx.host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "qiniu-kodo"},
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
    ctx.host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    ctx.host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
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
        return_value={"storage_mode": "platform", "storage_config": {"driver": "local"}}
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={"storage_mode": "platform", "storage_config": {"driver": "local"}}
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    result = await service.get_tenant_prerequisites(21)

    assert result["ok"] is True
    assert result["prerequisites"]["charge_local_storage"] is False
    assert result["prerequisites"]["ready"] is False
    assert "current_driver_not_billable" in result["prerequisites"]["missing_reasons"]


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_reports_binding_provider_mismatch():
    module = load_plugin_module("storage-billing", "services.binding_service")
    models = load_plugin_module("storage-billing", "models.binding")
    assert module is not None
    assert models is not None

    binding = models.StorageTenantBinding(
        tenant_id=31,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-31-bucket",
        validation_status="valid",
        validation_message="ok",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([binding]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 31,
            "tenant_code": "tenant-31",
            "tenant_name": "Tenant 31",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "aliyun-oss"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "aliyun-oss"},
        }
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "aliyun-oss": {
                    "enabled": True,
                    "driver_enabled": True,
                }
            },
            "validations": {
                "aliyun-oss": {
                    "driver_enabled": True,
                    "errors": [],
                }
            },
        }
    )
    result = await service.get_tenant_prerequisites(31)

    assert result["prerequisites"]["ready"] is False
    assert "binding_provider_mismatch" in result["prerequisites"]["missing_reasons"]
    assert result["bindings"]["active_total"] == 1
    assert result["bindings"]["matching_active_total"] == 0
    assert result["bindings"]["ready_total"] == 0


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_reports_invalid_binding_for_current_driver():
    module = load_plugin_module("storage-billing", "services.binding_service")
    models = load_plugin_module("storage-billing", "models.binding")
    assert module is not None
    assert models is not None

    binding = models.StorageTenantBinding(
        tenant_id=32,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        provider_profile_code="aliyun-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-32-bucket",
        validation_status="invalid",
        validation_message="profile mismatch",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([binding]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 32,
            "tenant_code": "tenant-32",
            "tenant_name": "Tenant 32",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "aliyun-oss"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "aliyun-oss"},
        }
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "aliyun-oss": {
                    "enabled": True,
                    "driver_enabled": True,
                }
            },
            "validations": {
                "aliyun-oss": {
                    "driver_enabled": True,
                    "errors": [],
                }
            },
        }
    )
    result = await service.get_tenant_prerequisites(32)

    assert result["prerequisites"]["ready"] is False
    assert "binding_invalid" in result["prerequisites"]["missing_reasons"]
    assert result["bindings"]["matching_active_total"] == 1
    assert result["bindings"]["ready_total"] == 0


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_is_ready_with_valid_matching_binding():
    module = load_plugin_module("storage-billing", "services.binding_service")
    models = load_plugin_module("storage-billing", "models.binding")
    assert module is not None
    assert models is not None

    valid_matching_binding = models.StorageTenantBinding(
        tenant_id=33,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-33-bucket",
        validation_status="valid",
        validation_message="ok",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    unrelated_binding = models.StorageTenantBinding(
        tenant_id=33,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        provider_profile_code="aliyun-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-33-secondary",
        validation_status="invalid",
        validation_message="ignored",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(
        return_value=_make_scalars_result([valid_matching_binding, unrelated_binding])
    )

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 33,
            "tenant_code": "tenant-33",
            "tenant_name": "Tenant 33",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "tencent-cos": {
                    "enabled": True,
                    "driver_enabled": True,
                }
            },
            "validations": {
                "tencent-cos": {
                    "driver_enabled": True,
                    "errors": [],
                }
            },
        }
    )
    result = await service.get_tenant_prerequisites(33)

    assert result["prerequisites"]["ready"] is True
    assert result["prerequisites"]["missing_reasons"] == []
    assert result["bindings"]["active_total"] == 2
    assert result["bindings"]["valid_active_total"] == 1
    assert result["bindings"]["matching_active_total"] == 1
    assert result["bindings"]["ready_total"] == 1


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_reports_provider_profile_disabled():
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 40,
            "tenant_code": "tenant-40",
            "tenant_name": "Tenant 40",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "tencent-cos": {
                    "enabled": False,
                    "driver_enabled": True,
                }
            },
            "validations": {
                "tencent-cos": {
                    "driver_enabled": True,
                    "errors": [],
                }
            },
        }
    )

    result = await service.get_tenant_prerequisites(40)

    assert result["prerequisites"]["ready"] is False
    assert "provider_profile_disabled" in result["prerequisites"]["missing_reasons"]


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_does_not_fallback_to_tenant_driver_when_platform_driver_missing():
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 41,
            "tenant_code": "tenant-41",
            "tenant_name": "Tenant 41",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={"storage_mode": "platform", "storage_config": {}}
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "tencent-cos": {
                    "enabled": True,
                    "driver_enabled": True,
                }
            },
            "validations": {
                "tencent-cos": {
                    "driver_enabled": True,
                    "errors": [],
                }
            },
        }
    )

    result = await service.get_tenant_prerequisites(41)

    assert result["prerequisites"]["ready"] is False
    assert result["prerequisites"]["current_driver"] == ""
    assert result["prerequisites"]["tenant_effective_driver"] == "tencent-cos"
    assert "current_driver_unsupported" in result["prerequisites"]["missing_reasons"]
    assert result["provider_capabilities"] == {}


@pytest.mark.asyncio
async def test_create_binding_is_invalid_when_platform_driver_is_missing(monkeypatch):
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
            "tenant_id": 42,
            "tenant_code": "tenant-42",
            "tenant_name": "Tenant 42",
            "plan_id": 2,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    ctx.host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    ctx.host.get_platform_storage_context = AsyncMock(
        return_value={"storage_mode": "platform", "storage_config": {}}
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

    result = await service.create_binding(
        {
            "tenant_id": 42,
            "provider_code": "tencent-cos",
            "scope_type": "bucket",
            "scope_value": "tenant-42-bucket",
            "billing_mode": "official_reconciled",
            "provider_profile_code": "tencent-default",
        }
    )

    assert result["validation"]["validation_status"] == "invalid"
    assert "unsupported" in result["validation"]["validation_message"].lower()


@pytest.mark.asyncio
async def test_get_tenant_prerequisites_reports_tenant_not_using_platform_storage():
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    plugin_db = AsyncMock()
    plugin_db.execute = AsyncMock(return_value=_make_scalars_result([]))

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=plugin_db)

    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 41,
            "tenant_code": "tenant-41",
            "tenant_name": "Tenant 41",
            "plan_id": 9,
            "plan": {
                "code": "plan_storage",
                "name": "Storage Plan",
                "features": {"storage_billing_enabled": True},
            },
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={
            "storage_mode": "custom",
            "storage_config": {"driver": "aliyun-oss"},
        }
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "storage_config": {"driver": "tencent-cos"},
        }
    )
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    service = module.StorageBillingBindingService(ctx, host_read=host)
    service._profile_service.list_provider_profiles = AsyncMock(
        return_value={"providers": {}, "validations": {}}
    )

    result = await service.get_tenant_prerequisites(41)

    assert result["prerequisites"]["ready"] is False
    assert result["prerequisites"]["tenant_storage_mode"] == "custom"
    assert result["prerequisites"]["tenant_effective_driver"] == "aliyun-oss"
    assert (
        "tenant_not_using_platform_storage"
        in result["prerequisites"]["missing_reasons"]
    )
