"\"\"\"Tests for TenantPlanPluginEntitlementService.\"\"\""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

import pytest

from app.services.tenant.tenant_plan_plugin_entitlement_service import (
    TenantPlanPluginEntitlementService,
)


@pytest.mark.asyncio
async def test_sync_plan_permissions_grants_when_flag_enabled(mock_db, monkeypatch):
    service = TenantPlanPluginEntitlementService(mock_db)
    monkeypatch.setattr(
        service,
        "_get_plan_permission_ids",
        AsyncMock(return_value={1}),
    )
    monkeypatch.setattr(
        service,
        "_fetch_plugin_permission_ids",
        AsyncMock(return_value=([1, 2], [1, 2])),
    )
    monkeypatch.setattr(
        service,
        "_get_plugin_policy",
        lambda plugin: {"grant_mode": "auto_all_active_plans"},
    )
    grant = AsyncMock()
    monkeypatch.setattr(service, "_grant_permissions", grant)
    revoke = AsyncMock()
    monkeypatch.setattr(service, "_revoke_permissions", revoke)

    await service.sync_plan_permissions(10, {"storage_billing_enabled": True})

    grant.assert_awaited_once_with(10, {2})
    revoke.assert_not_called()


@pytest.mark.asyncio
async def test_sync_plan_permissions_revokes_when_flag_disabled(mock_db, monkeypatch):
    service = TenantPlanPluginEntitlementService(mock_db)
    monkeypatch.setattr(
        service,
        "_get_plan_permission_ids",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        service,
        "_fetch_plugin_permission_ids",
        AsyncMock(return_value=([1, 2], [1, 2])),
    )
    monkeypatch.setattr(
        service,
        "_get_plugin_policy",
        lambda plugin: {"grant_mode": "auto_all_active_plans"},
    )
    grant = AsyncMock()
    monkeypatch.setattr(service, "_grant_permissions", grant)
    revoke = AsyncMock()
    monkeypatch.setattr(service, "_revoke_permissions", revoke)

    await service.sync_plan_permissions(11, {"storage_billing_enabled": False})

    revoke.assert_awaited_once_with(11, {1, 2})
    grant.assert_not_called()


@pytest.mark.asyncio
async def test_sync_plan_permissions_skips_manual_policy(mock_db, monkeypatch):
    service = TenantPlanPluginEntitlementService(mock_db)
    monkeypatch.setattr(
        service,
        "_get_plan_permission_ids",
        AsyncMock(return_value={1}),
    )
    monkeypatch.setattr(
        service,
        "_fetch_plugin_permission_ids",
        AsyncMock(return_value=([1, 2], [2])),
    )
    monkeypatch.setattr(
        service,
        "_get_plugin_policy",
        lambda plugin: {"grant_mode": "manual_entitlement"},
    )
    grant = AsyncMock()
    monkeypatch.setattr(service, "_grant_permissions", grant)
    revoke = AsyncMock()
    monkeypatch.setattr(service, "_revoke_permissions", revoke)

    await service.sync_plan_permissions(12, {"storage_billing_enabled": True})

    grant.assert_not_called()
    revoke.assert_not_called()


@pytest.mark.asyncio
async def test_sync_plan_feature_entitlements_grants_manual_policy(mock_db, monkeypatch):
    service = TenantPlanPluginEntitlementService(mock_db)
    monkeypatch.setattr(
        service,
        "_get_plan_permission_ids",
        AsyncMock(return_value={1}),
    )
    monkeypatch.setattr(
        service,
        "_fetch_plugin_permission_ids",
        AsyncMock(return_value=([1, 2], [1, 2])),
    )
    monkeypatch.setattr(
        service,
        "_get_plugin_policy",
        lambda plugin: {"grant_mode": "manual_entitlement"},
    )
    grant = AsyncMock()
    monkeypatch.setattr(service, "_grant_permissions", grant)
    revoke = AsyncMock()
    monkeypatch.setattr(service, "_revoke_permissions", revoke)

    summary = await service.sync_plan_feature_entitlements(
        13,
        {"storage_billing_enabled": True},
    )

    grant.assert_awaited_once_with(13, {2})
    revoke.assert_not_called()
    assert summary["storage-billing"]["feature_enabled"] is True
    assert summary["storage-billing"]["grant_mode"] == "manual_entitlement"


@pytest.mark.asyncio
async def test_sync_plan_feature_entitlements_revokes_when_flag_disabled(mock_db, monkeypatch):
    service = TenantPlanPluginEntitlementService(mock_db)
    monkeypatch.setattr(
        service,
        "_get_plan_permission_ids",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        service,
        "_fetch_plugin_permission_ids",
        AsyncMock(return_value=([1, 2], [1, 2])),
    )
    monkeypatch.setattr(
        service,
        "_get_plugin_policy",
        lambda plugin: {"grant_mode": "manual_entitlement"},
    )
    grant = AsyncMock()
    monkeypatch.setattr(service, "_grant_permissions", grant)
    revoke = AsyncMock()
    monkeypatch.setattr(service, "_revoke_permissions", revoke)

    summary = await service.sync_plan_feature_entitlements(
        14,
        {"storage_billing_enabled": False},
    )

    revoke.assert_awaited_once_with(14, {1, 2})
    grant.assert_not_called()
    assert summary["storage-billing"]["feature_enabled"] is False


@pytest.mark.asyncio
async def test_grant_permissions_executes_insert(mock_db):
    service = TenantPlanPluginEntitlementService(mock_db)
    await service._grant_permissions(7, [3, 4, 4])

    assert mock_db.execute.await_count == 1
    stmt, params = mock_db.execute.await_args.args
    assert "INSERT INTO tenant_plan_permissions" in str(stmt)
    assert params == [
        {"plan_id": 7, "permission_id": 3},
        {"plan_id": 7, "permission_id": 4},
    ]
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_permissions_executes_delete(mock_db):
    service = TenantPlanPluginEntitlementService(mock_db)
    await service._revoke_permissions(8, [5, 6])

    assert mock_db.execute.await_count == 1
    stmt = mock_db.execute.await_args.args[0]
    assert "DELETE FROM TENANT_PLAN_PERMISSIONS" in str(stmt).upper()
    mock_db.flush.assert_awaited_once()
