"""
AgentAssignmentService.validate_agent_id (platform feature binding rules) / 功能分配校验单测
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.agent import AgentStatusEnum
from app.enums.common import AudienceEnum, ResourceScopeEnum
from app.exceptions import ValidationException
from app.services.system.agent_assignment_service import AgentAssignmentService


def _row(
    *,
    tenant_id: int | None = None,
    scope: str = ResourceScopeEnum.ADMIN_AND_ALL.value,
    audience: str = AudienceEnum.ADMIN_TENANT.value,
):
    r = MagicMock()
    r.id = 1
    r.status = AgentStatusEnum.PUBLISHED.value
    r.scope = scope
    r.tenant_id = tenant_id
    r.target_audience = audience
    return r


@pytest.mark.asyncio
async def test_for_platform_feature_binding_accepts_admin_and_all_platform_agent():
    db = MagicMock()
    svc = AgentAssignmentService(db)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = _row()
    db.execute = AsyncMock(return_value=mock_result)

    await svc.validate_agent_id(1, for_platform_feature_binding=True)


@pytest.mark.asyncio
async def test_for_platform_feature_binding_rejects_tenant_owned_agent():
    db = MagicMock()
    svc = AgentAssignmentService(db)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = _row(tenant_id=99)
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValidationException):
        await svc.validate_agent_id(1, for_platform_feature_binding=True)


@pytest.mark.asyncio
async def test_for_platform_feature_binding_rejects_assigned_scope():
    db = MagicMock()
    svc = AgentAssignmentService(db)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = _row(
        scope=ResourceScopeEnum.ASSIGNED_TENANTS.value,
    )
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValidationException):
        await svc.validate_agent_id(1, for_platform_feature_binding=True)


@pytest.mark.asyncio
async def test_for_platform_feature_binding_rejects_admin_only_audience():
    db = MagicMock()
    svc = AgentAssignmentService(db)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = _row(audience=AudienceEnum.ADMIN_ONLY.value)
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(ValidationException):
        await svc.validate_agent_id(1, for_platform_feature_binding=True)
