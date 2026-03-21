"""AgentRouterService routing hardening tests / AgentRouterService 路由硬约束测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.services.ai.agent_router_service import (
    ROUTED_BY_CONVERSATION,
    AgentRouterService,
)


def _make_agent(
    *,
    agent_id: int,
    name: str,
    supports_vision: bool,
    owner_tenant_id: int | None = 1,
):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.owner_tenant_id = owner_tenant_id
    agent.model = MagicMock()
    agent.model.supports_vision = supports_vision
    return agent


def _make_conversation(
    *,
    conversation_id: int,
    agent_id: int,
    tenant_id: int = 1,
    user_id: int = 10,
):
    conversation = MagicMock()
    conversation.id = conversation_id
    conversation.agent_id = agent_id
    conversation.tenant_id = tenant_id
    conversation.user_id = user_id
    return conversation


@pytest.mark.asyncio
async def test_route_reuses_bound_conversation_agent_without_force_reroute(mock_db):
    service = AgentRouterService(mock_db)
    conversation = _make_conversation(conversation_id=100, agent_id=7)
    bound_agent = _make_agent(
        agent_id=7,
        name="Bound Agent",
        supports_vision=True,
    )

    service._get_accessible_conversation = AsyncMock(return_value=conversation)
    service._get_published_agent = AsyncMock(return_value=bound_agent)
    service._is_agent_visible = AsyncMock(return_value=True)
    service._list_available_agents = AsyncMock()
    service._call_router = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="continue",
        conversation_id=100,
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 7
    assert result.agent_name == "Bound Agent"
    assert result.routed_by == ROUTED_BY_CONVERSATION
    service._list_available_agents.assert_not_awaited()
    service._call_router.assert_not_awaited()
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_rejects_image_turn_for_non_vision_conversation_agent(mock_db):
    service = AgentRouterService(mock_db)
    conversation = _make_conversation(conversation_id=100, agent_id=7)
    non_vision_agent = _make_agent(
        agent_id=7,
        name="Text Agent",
        supports_vision=False,
    )

    service._get_accessible_conversation = AsyncMock(return_value=conversation)
    service._get_published_agent = AsyncMock(return_value=non_vision_agent)
    service._is_agent_visible = AsyncMock(return_value=True)
    service._list_available_agents = AsyncMock()
    service._fallback_to_default = AsyncMock()

    with pytest.raises(BusinessException):
        await service.route(
            tenant_id=1,
            message="see image",
            conversation_id=100,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=1,
            user_id=10,
            has_image_attachments=True,
        )

    service._list_available_agents.assert_not_awaited()
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_rejects_non_vision_pinned_agent_for_image_turn(mock_db):
    service = AgentRouterService(mock_db)
    non_vision_agent = _make_agent(
        agent_id=9,
        name="Pinned Agent",
        supports_vision=False,
    )

    service._get_published_agent = AsyncMock(return_value=non_vision_agent)
    service._is_agent_visible = AsyncMock(return_value=True)
    service._list_available_agents = AsyncMock()

    with pytest.raises(BusinessException):
        await service.route(
            tenant_id=1,
            message="check image",
            pinned_agent_id=9,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=1,
            user_id=10,
            has_image_attachments=True,
        )

    service._list_available_agents.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_rejects_image_turn_when_no_vision_candidates_exist(mock_db):
    service = AgentRouterService(mock_db)
    candidates = [
        _make_agent(agent_id=1, name="Text Agent A", supports_vision=False),
        _make_agent(agent_id=2, name="Text Agent B", supports_vision=False),
    ]

    service._list_available_agents = AsyncMock(return_value=candidates)
    service._get_router_agent = AsyncMock()

    with pytest.raises(BusinessException):
        await service.route(
            tenant_id=1,
            message="look at this screenshot",
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=1,
            user_id=10,
            has_image_attachments=True,
        )

    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_to_default_rejects_non_vision_default_agent_for_image_turn():
    service = AgentRouterService.__new__(AgentRouterService)
    assignment = MagicMock()
    assignment.agent_id = 11
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = assignment
    service.db = MagicMock()
    service.db.execute = AsyncMock(return_value=execute_result)
    service._get_published_agent = AsyncMock(
        return_value=_make_agent(
            agent_id=11,
            name="Default Agent",
            supports_vision=False,
            owner_tenant_id=None,
        ),
    )
    service._is_agent_visible = AsyncMock(return_value=True)

    with pytest.raises(BusinessException):
        await service._fallback_to_default(
            None,
            UserRoleEnum.PLATFORM_ADMIN.value,
            user_id=1,
            user_role_id=1,
            has_image_attachments=True,
        )
