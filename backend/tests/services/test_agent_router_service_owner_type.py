from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.common import UserRoleEnum


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_router_conversation_access_scopes_tenant_admin_by_owner_type_and_user_id(mock_db):
    from app.services.ai.agent_router_service import AgentRouterService

    conversation = MagicMock()
    mock_db.execute = AsyncMock(return_value=_scalar_result(conversation))

    service = AgentRouterService(mock_db)
    result = await service._get_accessible_conversation(
        conversation_id=10,
        tenant_id=1,
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_id=88,
    )

    assert result is conversation
    stmt = mock_db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "agent_conversations.tenant_id = 1" in sql
    assert "agent_conversations.owner_type = 'tenant_admin'" in sql
    assert "agent_conversations.user_id = 88" in sql


@pytest.mark.asyncio
async def test_router_conversation_access_scopes_platform_admin_to_platform_owner_type(mock_db):
    from app.services.ai.agent_router_service import AgentRouterService

    conversation = MagicMock()
    mock_db.execute = AsyncMock(return_value=_scalar_result(conversation))

    service = AgentRouterService(mock_db)
    result = await service._get_accessible_conversation(
        conversation_id=20,
        tenant_id=0,
        user_role=UserRoleEnum.PLATFORM_ADMIN.value,
        user_id=99,
    )

    assert result is conversation
    stmt = mock_db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "agent_conversations.tenant_id = 0" in sql
    assert "agent_conversations.owner_type = 'platform_admin'" in sql
    assert "agent_conversations.user_id =" not in sql
