"""AgentRouterService routing hardening tests / AgentRouterService 路由硬约束测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.services.ai.agent_router_policy import requested_tool_families
from app.services.ai.agent_router_service import (
    ROUTED_BY_CONVERSATION,
    ROUTED_BY_DEFAULT,
    ROUTED_BY_PREFERRED_FALLBACK,
    AgentRouterService,
    RouteResult,
)


def _make_skill_grant(skill_name: str, *, enabled: bool = True):
    grant = MagicMock()
    grant.enabled = enabled
    grant.skill = MagicMock()
    grant.skill.name = skill_name
    grant.skill.key = None
    grant.skill.description = ""
    grant.skill.is_active = True
    grant.skill.is_deleted = False
    grant.skill.package = MagicMock()
    grant.skill.package.name = ""
    grant.skill.package.description = ""
    grant.skill.package.is_active = True
    grant.skill.package.is_deleted = False
    return grant


def _make_agent(
    *,
    agent_id: int,
    name: str,
    supports_vision: bool,
    owner_tenant_id: int | None = 1,
    skill_names: list[str] | None = None,
):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.owner_tenant_id = owner_tenant_id
    agent.model = MagicMock()
    agent.model.supports_vision = supports_vision
    agent.skill_grants = [
        _make_skill_grant(skill_name) for skill_name in (skill_names or [])
    ]
    return agent


def _make_descriptor_grant(
    *,
    skill_name: str,
    skill_config: dict | None = None,
    skill_key: str | None = None,
    skill_description: str = "",
    package_name: str = "",
    package_description: str = "",
):
    grant = _make_skill_grant(skill_name)
    grant.skill.key = skill_key
    grant.skill.config = skill_config or {}
    grant.skill.description = skill_description
    grant.skill.package.name = package_name
    grant.skill.package.description = package_description
    return grant


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


def _thin_page_context(
    page_key: str,
    *,
    primary_tools: list[str] | None = None,
    reason: str = "router-test",
) -> dict[str, object]:
    return {
        "page_key": page_key,
        "ui_epoch": 1,
        "suggested_tools": {
            "primary": primary_tools
            or [
                "ui_get_snapshot",
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ],
            "secondary": ["ui_open_surface"],
            "reason": reason,
        },
    }


def test_agent_supports_page_operations_ignores_inactive_packages() -> None:
    agent = _make_agent(
        agent_id=59,
        name="Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    for grant in agent.skill_grants:
        grant.skill.package.is_active = False

    assert AgentRouterService._agent_supports_page_operations(agent) is False


def test_agent_needs_function_calling_ignores_inactive_packages() -> None:
    agent = _make_agent(
        agent_id=60,
        name="Tool Agent",
        supports_vision=False,
        skill_names=["ui_click"],
    )
    for grant in agent.skill_grants:
        grant.skill.package.is_active = False

    assert AgentRouterService._agent_needs_function_calling(agent) is False


def test_agent_supports_families_uses_skill_preview_metadata() -> None:
    agent = _make_agent(
        agent_id=61,
        name="Descriptor Agent",
        supports_vision=False,
    )
    agent.skill_grants = [
        _make_descriptor_grant(
            skill_name="weather-runtime",
            skill_config={"tools": [{"name": "get_current_weather"}]},
        ),
        _make_descriptor_grant(
            skill_name="web_search",
        ),
        _make_descriptor_grant(
            skill_name="neutral-page-skill",
            skill_config={"preview_semantic_families": ["page_ops"]},
        ),
    ]

    assert AgentRouterService._agent_supports_families(
        agent,
        ["weather", "web_research", "page_ops"],
    )


def test_agent_supports_families_treats_time_as_runtime_baseline() -> None:
    agent = _make_agent(
        agent_id=62,
        name="Weather Descriptor Agent",
        supports_vision=False,
    )
    agent.skill_grants = [
        _make_descriptor_grant(
            skill_name="weather-runtime",
            skill_config={"tools": [{"name": "get_current_weather"}]},
        ),
    ]

    assert AgentRouterService._agent_supports_families(
        agent,
        ["weather", "time_ops"],
    )


def test_requested_tool_families_treats_colloquial_here_question_as_page_ops() -> None:
    families = requested_tool_families(
        "这里都有啥？",
        _thin_page_context("admin.ai.agents"),
    )

    assert families == ["page_ops"]


@pytest.mark.parametrize(
    "message",
    [
        "翻到第3页",
        "翻回上一页",
        "每页显示50条",
    ],
)
def test_requested_tool_families_routes_pagination_messages_to_page_ops(
    message: str,
) -> None:
    families = requested_tool_families(
        message,
        _thin_page_context("admin.runtime.records"),
    )

    assert families == ["page_ops"]


def test_requested_tool_families_keeps_page_search_keywords_inside_page_ops() -> None:
    families = requested_tool_families(
        "帮我搜索一下包含'天气'的记录",
        _thin_page_context("admin.runtime.records"),
    )

    assert families == ["page_ops"]


def test_requested_tool_families_keeps_mixed_web_and_page_summary_families() -> None:
    families = requested_tool_families(
        "帮我搜索一下今天的 AI 新闻，再顺便概括一下当前页面都能做什么",
        _thin_page_context(
            "admin.ai.quotas",
            primary_tools=["ui_get_snapshot", "ui_read_region", "ui_read_table"],
        ),
    )

    assert families == ["web_research", "page_ops"]


@pytest.mark.parametrize(
    "message",
    [
        "帮我看看第一条记录的详细信息",
        "帮我打开一条新建记录表单，然后告诉我这个表单现在填了什么，有哪些选项可以选？",
        "帮我编辑第一条记录，把名称改成 E2E-Edit-Test",
    ],
)
def test_requested_tool_families_routes_detail_and_form_messages_to_page_ops(
    message: str,
) -> None:
    families = requested_tool_families(
        message,
        _thin_page_context("admin.ai.skill-packages"),
    )

    assert families == ["page_ops"]


def _semantic_agents_menu_entry() -> dict[str, object]:
    return {
        "title": "智能体管理",
        "page_key": "admin.ai.agents",
        "path": "/admin/ai/agents",
        "description": "创建、编辑和管理 AI 智能体",
        "keywords": ["智能体", "agent", "AI助手", "assistant"],
        "capabilities": ["create_agent", "edit_agent"],
        "category": "ai",
    }


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
    service._agent_can_handle_images = AsyncMock(return_value=False)
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
    service._agent_can_handle_images = AsyncMock(return_value=False)
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
    service._agent_can_handle_images = AsyncMock(return_value=False)
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
    service._agent_can_handle_images = AsyncMock(return_value=False)

    with pytest.raises(BusinessException):
        await service._fallback_to_default(
            None,
            UserRoleEnum.PLATFORM_ADMIN.value,
            user_id=1,
            user_role_id=1,
            has_image_attachments=True,
        )


@pytest.mark.asyncio
async def test_route_accepts_image_turn_when_smart_routing_can_supply_vision_model(
    mock_db,
    monkeypatch,
):
    service = AgentRouterService(mock_db)
    conversation = _make_conversation(conversation_id=100, agent_id=7)
    non_vision_agent = _make_agent(
        agent_id=7,
        name="Smart Routed Agent",
        supports_vision=False,
    )

    class _FakeModelRouter:
        def __init__(self, db):
            self.db = db

        async def can_handle_attachments(self, _agent, **_kwargs):
            return True

    monkeypatch.setattr(
        "app.services.ai.agent_router_capability_support.ModelRouter",
        _FakeModelRouter,
    )

    service._get_accessible_conversation = AsyncMock(return_value=conversation)
    service._get_published_agent = AsyncMock(return_value=non_vision_agent)
    service._is_agent_visible = AsyncMock(return_value=True)
    service._list_available_agents = AsyncMock()
    service._call_router = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="continue with image",
        conversation_id=100,
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
        has_image_attachments=True,
    )

    assert result.agent_id == 7
    assert result.routed_by == ROUTED_BY_CONVERSATION
    service._list_available_agents.assert_not_awaited()
    service._call_router.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_directly_selects_only_page_operation_capable_agent(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="请帮我操作当前页面并打开表单",
        page_context=_thin_page_context("admin.ai.quotas"),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 59
    assert result.agent_name == "Page Agent"
    service._get_router_agent.assert_not_awaited()
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_detects_admin_cross_page_navigation_intent(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Admin Page Agent",
        supports_vision=False,
        owner_tenant_id=None,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=None,
        message="我想添加一个智能体",
        page_context={
            **_thin_page_context(
                "admin.dashboard",
                primary_tools=[
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ],
            ),
            "page_data": {"navigation_catalog": [_semantic_agents_menu_entry()]},
        },
        user_role=UserRoleEnum.PLATFORM_ADMIN.value,
        user_role_id=1,
        user_id=1,
    )

    assert result.agent_id == 59
    assert result.routed_by == "router"
    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_detects_tenant_cross_page_navigation_intent(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=66,
        name="Tenant Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="帮我添加一个智能体",
        page_context={
            **_thin_page_context(
                "tenant.dashboard",
                primary_tools=[
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ],
            ),
            "page_data": {"navigation_catalog": [_semantic_agents_menu_entry()]},
        },
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 66
    assert result.routed_by == "router"
    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_detects_semantic_agent_navigation_phrase(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Admin Page Agent",
        supports_vision=False,
        owner_tenant_id=None,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=None,
        message="我想创建一个 agent",
        page_context={
            **_thin_page_context(
                "admin.system.organization",
                primary_tools=[
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ],
            ),
            "page_data": {"navigation_catalog": [_semantic_agents_menu_entry()]},
        },
        user_role=UserRoleEnum.PLATFORM_ADMIN.value,
        user_role_id=1,
        user_id=1,
    )

    assert result.agent_id == 59
    assert result.routed_by == "router"
    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_detects_semantic_ai_assistant_navigation_phrase(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Admin Page Agent",
        supports_vision=False,
        owner_tenant_id=None,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=None,
        message="帮我新增 AI 助手",
        page_context={
            **_thin_page_context(
                "admin.system.organization",
                primary_tools=[
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ],
            ),
            "page_data": {"navigation_catalog": [_semantic_agents_menu_entry()]},
        },
        user_role=UserRoleEnum.PLATFORM_ADMIN.value,
        user_role_id=1,
        user_id=1,
    )

    assert result.agent_id == 59
    assert result.routed_by == "router"
    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_does_not_force_page_operation_pool_for_page_analysis_request(
    mock_db,
):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    router_agent = MagicMock()
    router_agent.model_id = 101

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock(return_value=router_agent)
    service._call_router = AsyncMock(
        return_value={"agent_id": 15, "confidence": 0.91},
    )
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="请解释一下当前页面的配额和限速差异",
        page_context=_thin_page_context("admin.ai.quotas"),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 15
    routed_candidates = service._call_router.await_args.args[1]
    assert [agent.id for agent in routed_candidates] == [15, 59]
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_keeps_full_candidate_pool_for_mixed_weather_and_page_write_request(
    mock_db,
):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    router_agent = MagicMock()
    router_agent.model_id = 101

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock(return_value=router_agent)
    service._call_router = AsyncMock(
        return_value={"agent_id": 15, "confidence": 0.93},
    )
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="帮我查一下北京天气，然后在当前页面创建一条测试记录",
        page_context=_thin_page_context("admin.ai.quotas"),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 15
    routed_candidates = service._call_router.await_args.args[1]
    assert [agent.id for agent in routed_candidates] == [15, 59]
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_keeps_full_candidate_pool_for_mixed_web_and_page_request(
    mock_db,
):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent = _make_agent(
        agent_id=59,
        name="Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    router_agent = MagicMock()
    router_agent.model_id = 101

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent],
    )
    service._get_router_agent = AsyncMock(return_value=router_agent)
    service._call_router = AsyncMock(
        return_value={"agent_id": 15, "confidence": 0.9},
    )
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="帮我搜索一下今天的 AI 新闻，再顺便概括一下当前页面都能做什么",
        page_context=_thin_page_context(
            "admin.ai.quotas",
            primary_tools=["ui_get_snapshot", "ui_read_region", "ui_read_table"],
        ),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 15
    routed_candidates = service._call_router.await_args.args[1]
    assert [agent.id for agent in routed_candidates] == [15, 59]
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_prefers_candidate_covering_all_requested_families_for_mixed_turn(
    mock_db,
):
    service = AgentRouterService(mock_db)
    partial_agent = _make_agent(
        agent_id=15,
        name="Search Page Agent",
        supports_vision=False,
        skill_names=[
            "web_search",
            "fetch_url",
            "ui_get_snapshot",
            "ui_click",
        ],
    )
    full_agent = _make_agent(
        agent_id=61,
        name="Full Mixed Agent",
        supports_vision=False,
        skill_names=[
            "get_current_weather",
            "web_search",
            "fetch_url",
            "ui_get_snapshot",
            "ui_click",
        ],
    )

    service._list_available_agents = AsyncMock(
        return_value=[partial_agent, full_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="帮我查一下北京天气，顺便搜索一下今天的热点新闻，再看看当前页面都有什么",
        page_context=_thin_page_context(
            "admin.ai.agents",
            primary_tools=["ui_get_snapshot", "ui_read_region", "ui_read_table"],
        ),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 61
    service._get_router_agent.assert_not_awaited()
    service._fallback_to_default.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_prefers_candidate_covering_weather_and_time_for_mixed_non_page_turn(
    mock_db,
):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    weather_agent = _make_agent(
        agent_id=62,
        name="Weather Agent",
        supports_vision=False,
        skill_names=["get_current_weather"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, weather_agent],
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="现在几点了？今天天气怎么样？",
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 62
    service._get_router_agent.assert_not_awaited()
    service._fallback_to_default.assert_not_awaited()


async def test_route_uses_page_operation_candidate_pool_for_fallback(mock_db):
    service = AgentRouterService(mock_db)
    general_agent = _make_agent(
        agent_id=15,
        name="General Agent",
        supports_vision=False,
    )
    page_agent_a = _make_agent(
        agent_id=59,
        name="Page Agent A",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    page_agent_b = _make_agent(
        agent_id=60,
        name="Page Agent B",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[general_agent, page_agent_a, page_agent_b],
    )
    service._get_router_agent = AsyncMock(return_value=None)
    service._fallback_to_default = AsyncMock(
        return_value=RouteResult(
            agent_id=59,
            agent_name="Page Agent A",
            confidence=1.0,
            routed_by="default",
        ),
    )

    result = await service.route(
        tenant_id=1,
        message="请帮我在这个页面编辑一条限速规则",
        page_context=_thin_page_context("admin.ai.quotas"),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 59
    service._fallback_to_default.assert_awaited_once()
    fallback_kwargs = service._fallback_to_default.await_args.kwargs
    assert [agent.id for agent in fallback_kwargs["preferred_candidates"]] == [
        59,
        60,
    ]


@pytest.mark.asyncio
async def test_fallback_to_default_prefers_bound_default_agent_within_preferred_pool():
    service = AgentRouterService.__new__(AgentRouterService)
    assignment = MagicMock()
    assignment.agent_id = 59
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = assignment
    service.db = MagicMock()
    service.db.execute = AsyncMock(return_value=execute_result)
    service._get_published_agent = AsyncMock(
        return_value=_make_agent(
            agent_id=59,
            name="Default Page Agent",
            supports_vision=True,
            owner_tenant_id=None,
            skill_names=["ui_get_snapshot", "ui_click"],
        ),
    )
    service._is_agent_visible = AsyncMock(return_value=True)

    result = await service._fallback_to_default(
        None,
        UserRoleEnum.PLATFORM_ADMIN.value,
        user_id=1,
        user_role_id=1,
        preferred_candidates=[
            _make_agent(
                agent_id=59,
                name="Default Page Agent",
                supports_vision=True,
                owner_tenant_id=None,
                skill_names=["ui_get_snapshot", "ui_click"],
            ),
            _make_agent(
                agent_id=60,
                name="Backup Page Agent",
                supports_vision=True,
                owner_tenant_id=None,
                skill_names=["ui_get_snapshot", "ui_click"],
            ),
        ],
    )

    assert result.agent_id == 59
    assert result.routed_by == ROUTED_BY_DEFAULT


@pytest.mark.asyncio
async def test_fallback_to_default_uses_preferred_pool_when_default_agent_is_outside_it():
    service = AgentRouterService.__new__(AgentRouterService)
    assignment = MagicMock()
    assignment.agent_id = 15
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = assignment
    service.db = MagicMock()
    service.db.execute = AsyncMock(return_value=execute_result)
    service._get_published_agent = AsyncMock(
        return_value=_make_agent(
            agent_id=15,
            name="General Default Agent",
            supports_vision=True,
            owner_tenant_id=None,
        ),
    )
    service._is_agent_visible = AsyncMock(return_value=True)

    result = await service._fallback_to_default(
        None,
        UserRoleEnum.PLATFORM_ADMIN.value,
        user_id=1,
        user_role_id=1,
        preferred_candidates=[
            _make_agent(
                agent_id=59,
                name="Page Agent A",
                supports_vision=True,
                owner_tenant_id=None,
                skill_names=["ui_get_snapshot", "ui_click"],
            ),
            _make_agent(
                agent_id=60,
                name="Page Agent B",
                supports_vision=True,
                owner_tenant_id=None,
                skill_names=["ui_get_snapshot", "ui_click"],
            ),
        ],
    )

    assert result.agent_id == 59
    assert result.routed_by == ROUTED_BY_PREFERRED_FALLBACK


@pytest.mark.asyncio
async def test_route_prefers_vision_page_agent_for_screenshot_request(mock_db):
    service = AgentRouterService(mock_db)
    text_page_agent = _make_agent(
        agent_id=59,
        name="Text Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )
    vision_page_agent = _make_agent(
        agent_id=60,
        name="Vision Page Agent",
        supports_vision=True,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(
        return_value=[text_page_agent, vision_page_agent],
    )
    service._agent_can_handle_images = AsyncMock(
        side_effect=lambda agent: bool(agent.model.supports_vision)
    )
    service._get_router_agent = AsyncMock()
    service._fallback_to_default = AsyncMock()

    result = await service.route(
        tenant_id=1,
        message="请帮我给当前页面截图",
        page_context=_thin_page_context(
            "admin.ai.quotas",
            primary_tools=["ui_get_snapshot", "ui_read_region", "ui_click"],
        ),
        user_role=UserRoleEnum.TENANT_ADMIN.value,
        user_role_id=1,
        user_id=10,
    )

    assert result.agent_id == 60
    service._get_router_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_rejects_screenshot_request_when_no_vision_page_agent_exists(mock_db):
    service = AgentRouterService(mock_db)
    text_page_agent = _make_agent(
        agent_id=59,
        name="Text Page Agent",
        supports_vision=False,
        skill_names=["ui_get_snapshot", "ui_click"],
    )

    service._list_available_agents = AsyncMock(return_value=[text_page_agent])
    service._agent_can_handle_images = AsyncMock(return_value=False)
    service._fallback_to_default = AsyncMock()

    with pytest.raises(BusinessException):
        await service.route(
            tenant_id=1,
            message="请帮我把当前页面截图发出来",
            page_context=_thin_page_context(
                "admin.ai.quotas",
                primary_tools=["ui_get_snapshot", "ui_read_region", "ui_click"],
            ),
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            user_role_id=1,
            user_id=10,
        )

    service._fallback_to_default.assert_not_awaited()


