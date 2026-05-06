"""Task tenant eligibility service tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.system.task_tenant_eligibility_service import (
    TaskTenantEligibilityService,
)


@pytest.mark.asyncio
async def test_resolve_tenant_model_eligibility_accepts_active_tenant_with_active_plan(
    mock_db,
) -> None:
    service = TaskTenantEligibilityService(mock_db)
    tenant = SimpleNamespace(
        id=42,
        is_deleted=False,
        is_active=True,
        plan_id=7,
        tenant_plan=SimpleNamespace(is_deleted=False, is_active=True),
    )

    result = await service.resolve_tenant_model_eligibility(42, tenant)

    assert result.is_eligible is True
    assert result.reason is None


@pytest.mark.asyncio
async def test_resolve_tenant_model_eligibility_rejects_missing_active_plan(
    mock_db,
) -> None:
    service = TaskTenantEligibilityService(mock_db)
    tenant = SimpleNamespace(
        id=42,
        is_deleted=False,
        is_active=True,
        plan_id=None,
        tenant_plan=None,
    )

    result = await service.resolve_tenant_model_eligibility(42, tenant)

    assert result.is_eligible is False
    assert result.reason == "tenant_plan_not_available"


def test_resolve_all_tenant_ids_sync_excludes_disabled_all_tenants_binding() -> None:
    tenant_query = MagicMock()
    tenant_query.join.return_value = tenant_query
    tenant_query.filter.return_value = tenant_query
    tenant_query.outerjoin.return_value = tenant_query
    tenant_query.order_by.return_value = tenant_query
    tenant_query.all.return_value = [(7,), (11,)]

    session = MagicMock()
    session.query.return_value = tenant_query

    tenant_ids = TaskTenantEligibilityService.resolve_all_tenant_ids_sync(
        session,
        task_definition_id=18,
    )

    assert tenant_ids == [7, 11]
    tenant_query.outerjoin.assert_called_once()
    assert tenant_query.filter.call_count >= 2
