"""
Test type: behavioral
Regression for: tenant plan configuration silently producing unlimited or
incorrect entitlements.
Scope: plan permission assignment, plan quota/feature schemas, and tenant plan
binding preflight.
Mock strategy: service collaborators are faked; assertions target service-level
fail-closed contracts instead of mocked downstream success.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.exceptions import BusinessException, NotFoundException
from app.schemas.tenant.plan import TenantPlanCreateRequest


@pytest.mark.asyncio
async def test_assign_permissions_rejects_invalid_ids_without_mutating_plan(
    mock_db,
) -> None:
    from app.services.tenant.tenant_plan_service import TenantPlanService

    plan = SimpleNamespace(id=8, features={}, permissions=["existing"])
    valid_permission = SimpleNamespace(id=101)

    service = TenantPlanService.__new__(TenantPlanService)
    service.db = mock_db
    service.repo = AsyncMock()
    service.repo.get_with_permissions = AsyncMock(return_value=plan)
    service._get_valid_permissions = AsyncMock(return_value=[valid_permission])
    service._sync_plan_plugin_entitlements = AsyncMock()

    with pytest.raises(BusinessException) as exc_info:
        await service.assign_permissions(8, [101, 999, 101])

    assert exc_info.value.data == {"invalid_permission_ids": [999]}
    assert plan.permissions == ["existing"]
    mock_db.flush.assert_not_awaited()
    service._sync_plan_plugin_entitlements.assert_not_awaited()


def test_plan_quota_schema_rejects_unknown_limit_keys() -> None:
    with pytest.raises(ValidationError):
        TenantPlanCreateRequest(
            name="Typo Plan",
            quota={"max_user": 10},
        )


def test_plan_features_schema_rejects_unknown_feature_keys() -> None:
    with pytest.raises(ValidationError):
        TenantPlanCreateRequest(
            name="Typo Plan",
            features={"ai_enable": False},
        )


@pytest.mark.asyncio
async def test_tenant_plan_preflight_snapshot_requires_active_plan(mock_db) -> None:
    from app.services.system.tenant_service import TenantService

    class _Result:
        def scalar_one_or_none(self):
            return None

    captured_statements: list[str] = []

    async def execute(stmt):
        captured_statements.append(str(stmt))
        return _Result()

    mock_db.execute = AsyncMock(side_effect=execute)
    service = TenantService.__new__(TenantService)
    service.db = mock_db

    with pytest.raises(NotFoundException):
        await service._get_plan_preflight_snapshot(12)

    assert captured_statements
    assert "tenant_plans.is_active" in captured_statements[0]
