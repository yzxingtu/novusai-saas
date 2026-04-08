import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

redis_module = types.ModuleType("redis")
redis_asyncio_module = types.ModuleType("redis.asyncio")
redis_asyncio_client_module = types.ModuleType("redis.asyncio.client")
redis_exceptions_module = types.ModuleType("redis.exceptions")


class _RedisConnectionPool:
    @classmethod
    def from_url(cls, *args, **kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *args, **kwargs) -> None:
        return None


class _RedisError(Exception):
    pass


class _RedisPipeline:
    pass


redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_exceptions_module.RedisError = _RedisError
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *a, **kw: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.engine.conversation import ConversationEngine, _StreamRuntimeContext
from app.ai.engine.types import ExecutionRequest
from app.ai.skills.resolver import SkillResolver, SkillResolveResult, resolve_for_agent
from app.ai.tools.executors.page_context_executor import (
    PAGE_CONTEXT_TURN_SEEN_KEY,
    PageContextExecutor,
)
from app.ai.tools.types import ExecutionContext, ToolDefinition, to_openai_tools
from app.ai.types import ChatMessage, ChatResponse
from app.enums.agent import SkillTypeEnum
from app.enums.common import ResourceScopeEnum, UserRoleEnum
from app.exceptions import ValidationException
from app.schemas.ai.agent_chat import AgentChatRequest, AgentRouteRequest, PageContext


def _make_scalars_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    return result


def _make_iterable_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.__iter__.return_value = iter(items)
    return result


def _compiled_param_values(statement: object) -> set[object]:
    compiled = statement.compile()
    values: set[object] = set()
    for value in compiled.params.values():
        if isinstance(value, (list, tuple, set)):
            values.update(value)
        else:
            values.add(value)
    return values


def test_page_context_accepts_legacy_frontend_fields() -> None:
    page_context = PageContext.model_validate(
        {
            "page_type": "tenant.agent.detail",
            "summary": "Agent detail",
            "detail": {"agent_id": 1},
        }
    )

    assert page_context.model_dump(exclude_none=True) == {
        "page_key": "tenant.agent.detail",
        "page_title": "Agent detail",
        "page_data": {"agent_id": 1},
    }


def test_page_context_accepts_standard_backend_fields() -> None:
    page_context = PageContext.model_validate(
        {
            "page_key": "tenant.agent.detail",
            "page_title": "Agent detail",
            "page_data": {"agent_id": 1},
        }
    )

    assert page_context.model_dump(exclude_none=True) == {
        "page_key": "tenant.agent.detail",
        "page_title": "Agent detail",
        "page_data": {"agent_id": 1},
    }


def test_page_context_normalize_returns_standard_structure_for_legacy_dict() -> None:
    assert PageContext.normalize(
        {
            "page_type": "tenant.order.detail",
            "summary": "Order #1001",
            "detail": {"order_id": 1001},
        }
    ) == {
        "page_key": "tenant.order.detail",
        "page_title": "Order #1001",
        "page_data": {"order_id": 1001},
    }


def test_page_context_normalize_returns_none_for_invalid_payload() -> None:
    assert PageContext.normalize({"summary": "missing key"}) is None


def test_page_context_normalize_variables_merges_standardized_page_context() -> None:
    assert PageContext.normalize_variables(
        {"foo": "bar"},
        {
            "page_type": "tenant.agent.detail",
            "summary": "Agent detail",
            "detail": {"agent_id": 1},
        },
    ) == {
        "foo": "bar",
        "page_context": {
            "page_key": "tenant.agent.detail",
            "page_title": "Agent detail",
            "page_data": {"agent_id": 1},
        },
    }


def test_page_context_normalize_variables_removes_invalid_page_context() -> None:
    assert PageContext.normalize_variables(
        {"foo": "bar", "page_context": {"summary": "missing key"}}
    ) == {"foo": "bar"}


def test_page_context_normalize_variables_prefers_explicit_page_context() -> None:
    assert PageContext.normalize_variables(
        {
            "page_context": {
                "page_type": "tenant.agent.detail",
                "summary": "Legacy agent detail",
                "detail": {"agent_id": 1},
            }
        },
        {
            "page_key": "tenant.order.detail",
            "page_title": "Order detail",
            "page_data": {"order_id": 1001},
        },
    ) == {
        "page_context": {
            "page_key": "tenant.order.detail",
            "page_title": "Order detail",
            "page_data": {"order_id": 1001},
        }
    }


def test_page_context_normalize_variables_standardizes_legacy_variables_payload() -> (
    None
):
    assert PageContext.normalize_variables(
        {
            "foo": "bar",
            "page_context": {
                "page_type": "tenant.agent.detail",
                "summary": "Agent detail",
                "detail": {"agent_id": 1},
            },
        }
    ) == {
        "foo": "bar",
        "page_context": {
            "page_key": "tenant.agent.detail",
            "page_title": "Agent detail",
            "page_data": {"agent_id": 1},
        },
    }


def test_agent_chat_request_accepts_legacy_page_context_shape() -> None:
    request = AgentChatRequest.model_validate(
        {
            "message": "help me",
            "page_context": {
                "page_type": "tenant.agent.detail",
                "summary": "Agent detail",
                "detail": {"agent_id": 1},
            },
        }
    )

    assert request.page_context is not None
    assert request.page_context.model_dump(exclude_none=True) == {
        "page_key": "tenant.agent.detail",
        "page_title": "Agent detail",
        "page_data": {"agent_id": 1},
    }


def test_agent_route_request_accepts_legacy_page_context_shape() -> None:
    request = AgentRouteRequest.model_validate(
        {
            "message": "help me",
            "page_context": {
                "page_type": "tenant.agent.detail",
                "summary": "Agent detail",
                "detail": {"agent_id": 1},
            },
        }
    )

    assert request.page_context is not None
    assert request.page_context.model_dump(exclude_none=True) == {
        "page_key": "tenant.agent.detail",
        "page_title": "Agent detail",
        "page_data": {"agent_id": 1},
    }


@pytest.mark.asyncio
async def test_validate_page_context_size_accepts_payload_within_runtime_limit() -> (
    None
):
    from app.services.ai.page_context_limits import validate_page_context_size

    page_context = {
        "page_key": "tenant.agent.detail",
        "page_data": {"agent_id": 1, "status": "active"},
    }

    with patch(
        "app.services.ai.page_context_limits.get_page_context_max_bytes",
        new=AsyncMock(return_value=1024),
    ):
        await validate_page_context_size(MagicMock(), page_context)


@pytest.mark.asyncio
async def test_validate_page_context_size_rejects_payload_over_runtime_limit() -> None:
    from app.services.ai.page_context_limits import validate_page_context_size

    page_context = {
        "page_key": "tenant.agent.detail",
        "page_data": {"content": "x" * 128},
    }

    with patch(
        "app.services.ai.page_context_limits.get_page_context_max_bytes",
        new=AsyncMock(return_value=32),
    ):
        with pytest.raises(ValidationException) as exc_info:
            await validate_page_context_size(MagicMock(), page_context)

    assert "32" in str(exc_info.value)


@pytest.mark.asyncio
async def test_page_context_executor_formats_legacy_payload_from_variables() -> None:
    executor = PageContextExecutor()
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call_1",
        {},
        ExecutionContext(
            tenant_id=1,
            agent_id=2,
            variables={
                "page_context": {
                    "page_type": "tenant.order.detail",
                    "summary": "Order #1001",
                    "detail": {"order_id": 1001},
                }
            },
        ),
    )

    assert result.success is True
    assert "Page: tenant.order.detail" in result.output
    assert "Title: Order #1001" in result.output
    assert '"order_id": 1001' in result.output


@pytest.mark.asyncio
async def test_page_context_executor_returns_empty_output_without_context() -> None:
    executor = PageContextExecutor()
    ctx = ExecutionContext(tenant_id=1, agent_id=2, variables={})
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call_2",
        {},
        ctx,
    )

    assert result.success is True
    assert result.output == render_prompt_contract("page_context_unavailable")
    assert ctx.variables.get(PAGE_CONTEXT_TURN_SEEN_KEY) is True


@pytest.mark.asyncio
async def test_page_context_executor_second_call_without_page_context_returns_repeated_hint() -> (
    None
):
    """空 variables 时首轮记 turn seen；同轮再次调用返回重复提示，而非再次输出无上下文。"""
    executor = PageContextExecutor()
    ctx = ExecutionContext(tenant_id=1, agent_id=2, variables={})
    first = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call-empty-1",
        {},
        ctx,
    )
    second = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call-empty-2",
        {},
        ctx,
    )

    unavailable = render_prompt_contract("page_context_unavailable")
    assert first.success is True
    assert first.output == unavailable
    assert second.success is True
    assert "already returned earlier in this turn" in second.output
    assert second.output != unavailable


@pytest.mark.asyncio
async def test_page_context_executor_variables_none_returns_no_context() -> None:
    executor = PageContextExecutor()
    ctx = MagicMock()
    ctx.variables = None
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call-vars-none",
        {},
        ctx,
    )

    assert result.success is True
    assert result.output == render_prompt_contract("page_context_unavailable")


@pytest.mark.asyncio
async def test_page_context_executor_prioritizes_mutation_ops_and_submit_workflow() -> (
    None
):
    executor = PageContextExecutor()
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call_mutation",
        {},
        ExecutionContext(
            tenant_id=1,
            agent_id=2,
            variables={
                "page_context": {
                    "page_key": "admin.ai.providers",
                    "page_title": "供应商名称",
                    "page_data": {
                        "form_fields": {
                            "name": {
                                "type": "string",
                                "description": "供应商名称",
                                "component": "input",
                                "required": True,
                            }
                        },
                        "available_operations": [
                            {
                                "name": "read_visible_rows",
                                "label": "读取当前可见行",
                                "readonly": True,
                            },
                            {
                                "name": "create_record",
                                "label": "新建记录",
                                "readonly": False,
                            },
                            {
                                "name": "fill_form",
                                "label": "智能填写表单",
                                "readonly": False,
                            },
                            {
                                "name": "submit_form",
                                "label": "提交表单",
                                "readonly": False,
                            },
                            {
                                "name": "validate_form",
                                "label": "校验表单",
                                "readonly": True,
                            },
                        ],
                    },
                }
            },
        ),
    )

    assert result.success is True
    assert (
        "Writable Operations Available: create_record, fill_form, submit_form"
        in result.output
    )
    assert "call submit_form" in result.output
    assert "Do not claim the page is read-only" in result.output
    assert "do NOT call get_page_context again" in result.output
    assert "Never batch create_record" in result.output


@pytest.mark.asyncio
async def test_page_context_executor_returns_page_snapshot() -> None:
    executor = PageContextExecutor()
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call_page_context",
        {},
        ExecutionContext(
            tenant_id=1,
            agent_id=2,
            variables={
                "page_context": {
                    "page_key": "admin.ai.providers",
                    "page_title": "供应商名称",
                    "page_data": {
                        "available_operations": [
                            {
                                "name": "read_current_view",
                                "label": "读取当前视图",
                                "readonly": True,
                            },
                        ],
                    },
                }
            },
        ),
    )

    assert result.success is True
    assert "Page: admin.ai.providers" in result.output


@pytest.mark.asyncio
async def test_agent_chat_service_injects_page_context_into_execution_request(
    mock_db,
) -> None:
    from app.services.ai.agent_chat_service import AgentChatService

    agent = MagicMock()
    agent.id = 1
    agent.status = "published"
    agent.context_config = {}

    conversation = MagicMock()
    conversation.id = 100
    conversation.agent_id = 1
    conversation.user_id = 10

    result = MagicMock()
    result.success = True
    result.output = "ok"
    result.total_tokens = 11
    result.messages = []
    result.tool_results = []

    service = AgentChatService(mock_db, tenant_id=1)
    service._validate_agent = AsyncMock(return_value=agent)
    service._resolve_effective_memory_enabled = AsyncMock(return_value=False)
    service._load_session_memory_context = AsyncMock(return_value="")
    service._persist_session_memory = AsyncMock(return_value=None)
    service.conversation_svc.get_or_create_for_chat = AsyncMock(
        return_value=conversation
    )
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=([], 0))
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service.conversation_svc.mark_memory_updated = AsyncMock(return_value=None)

    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock(return_value=result)

    with (
        patch(
            "app.services.ai.agent_chat_service.ExecutionDispatcher",
            return_value=dispatcher,
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation",
            new=AsyncMock(),
        ),
        patch(
            "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
            new=AsyncMock(),
        ),
    ):
        await service.chat(
            agent_id=1,
            message="hello",
            user_id=10,
            user_role=UserRoleEnum.TENANT_ADMIN.value,
            variables={
                "foo": "bar",
                "page_context": {
                    "page_type": "tenant.agent.detail",
                    "summary": "Legacy agent detail",
                    "detail": {"agent_id": 1},
                },
            },
            page_context={
                "page_key": "tenant.order.detail",
                "page_title": "Order detail",
                "page_data": {"order_id": 1001},
            },
        )

    called_request = dispatcher.dispatch.call_args.args[0]
    assert called_request.input_variables == {
        "foo": "bar",
        "page_context": {
            "page_key": "tenant.order.detail",
            "page_title": "Order detail",
            "page_data": {"order_id": 1001},
        },
    }


@pytest.mark.asyncio
async def test_skill_resolver_exposes_get_page_context_tool_schema() -> None:
    skill = MagicMock()
    skill.id = 11
    skill.package_id = 21
    skill.is_active = True
    skill.config = {
        "builtin_type": "page_context",
        "tools": [
            {
                "name": "get_page_context",
                "description": "Read current page context",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }
        ],
    }
    skill.name = "get_page_context"
    skill.description = "Read current page context"
    skill.type = SkillTypeEnum.BUILTIN.value
    skill.timeout = 15

    result = await SkillResolver().resolve([skill])

    assert [tool.name for tool in result.tools] == ["get_page_context"]
    openai_tools = to_openai_tools(result.tools)
    assert openai_tools[0]["function"]["name"] == "get_page_context"
    assert openai_tools[0]["function"]["parameters"]["properties"] == {}


@pytest.mark.asyncio
async def test_skill_resolver_augments_web_research_builtin_tool_descriptions() -> None:
    skill = MagicMock()
    skill.id = 12
    skill.package_id = 22
    skill.is_active = True
    skill.config = {
        "tools": [
            {
                "name": "web_search",
                "description": "Search the web",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "fetch_url",
                "description": "Fetch a webpage",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ],
    }
    skill.name = "web_research"
    skill.description = "Research tools"
    skill.type = SkillTypeEnum.BUILTIN.value
    skill.timeout = 15

    result = await SkillResolver().resolve([skill])

    descriptions = {tool.name: tool.description for tool in result.tools}
    assert "candidate sources" in descriptions["web_search"]
    assert "fetch_url" in descriptions["web_search"]
    assert (
        "full content" in descriptions["fetch_url"].lower()
        or "read" in descriptions["fetch_url"].lower()
    )


@pytest.mark.asyncio
async def test_skill_resolver_augments_current_time_builtin_tool_description() -> None:
    skill = MagicMock()
    skill.id = 13
    skill.package_id = 23
    skill.is_active = True
    skill.config = {
        "tools": [
            {
                "name": "get_current_time",
                "description": "Get current time",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ],
    }
    skill.name = "time_tools"
    skill.description = "Time tools"
    skill.type = SkillTypeEnum.BUILTIN.value
    skill.timeout = 15

    result = await SkillResolver().resolve([skill])

    descriptions = {tool.name: tool.description for tool in result.tools}
    assert "timezone" in descriptions["get_current_time"]
    assert (
        "date" in descriptions["get_current_time"].lower()
        or "time" in descriptions["get_current_time"].lower()
    )


@pytest.mark.asyncio
async def test_resolve_for_agent_with_skill_grant_includes_get_page_context_tool(
    mock_db,
) -> None:
    agent = types.SimpleNamespace(
        id=7,
        name="Tenant Agent",
        scope=ResourceScopeEnum.ALL_TENANTS.value,
        owner_tenant_id=1,
    )

    package = types.SimpleNamespace(
        id=301,
        name="页面感知",
        is_active=True,
        is_deleted=False,
        valves_config=None,
    )

    skill = types.SimpleNamespace(
        id=401,
        package_id=301,
        is_active=True,
        is_deleted=False,
        config={
            "builtin_type": "page_context",
            "tools": [
                {
                    "name": "get_page_context",
                    "description": "Read current page context",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            ],
        },
        name="get_page_context",
        description="Read current page context",
        type=SkillTypeEnum.BUILTIN.value,
        timeout=15,
        package=package,
    )

    grant = types.SimpleNamespace(
        id=501,
        agent_id=7,
        skill_id=401,
        enabled=True,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        config_override=None,
        skill=skill,
    )

    mock_db.execute.side_effect = [
        _make_scalars_result([grant]),
        _make_iterable_result([]),
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=1)

    assert result is not None
    assert [tool.name for tool in result.tools] == [
        "get_page_context",
        "get_current_time",
    ]
    assert result.tool_consent_modes["get_page_context"] == "auto"
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert result.tools[0].source_package_name == "页面感知"
    openai_tools = to_openai_tools(result.tools)
    assert openai_tools[0]["function"]["name"] == "get_page_context"


@pytest.mark.asyncio
async def test_resolve_for_agent_admin_grant_applies_capability_override(
    mock_db,
) -> None:
    agent = types.SimpleNamespace(
        id=8,
        name="Admin Agent",
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        owner_tenant_id=None,
    )

    package = types.SimpleNamespace(
        id=302,
        name="页面感知",
        is_active=True,
        is_deleted=False,
        valves_config=None,
    )

    skill = types.SimpleNamespace(
        id=402,
        package_id=302,
        is_active=True,
        is_deleted=False,
        config={
            "builtin_type": "page_context",
            "tools": [
                {
                    "name": "get_page_context",
                    "description": "Read current page context",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                }
            ],
        },
        name="get_page_context",
        description="Read current page context",
        type=SkillTypeEnum.BUILTIN.value,
        timeout=15,
        package=package,
    )

    grant = types.SimpleNamespace(
        id=502,
        agent_id=8,
        skill_id=402,
        enabled=True,
        default_consent_mode="ask",
        capability_consent_overrides={"get_page_context": "reject"},
        config_override=None,
        skill=skill,
    )

    mock_db.execute.side_effect = [
        _make_scalars_result([grant]),
        _make_iterable_result([]),
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=None)

    assert result is not None
    assert [tool.name for tool in result.tools] == [
        "get_page_context",
        "get_current_time",
    ]
    assert result.tool_consent_modes["get_page_context"] == "reject"
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert result.tools[0].source_package_name == "页面感知"
    openai_tools = to_openai_tools(result.tools)
    assert openai_tools[0]["function"]["name"] == "get_page_context"


@pytest.mark.asyncio
async def test_resolve_for_agent_injects_baseline_time_tool_when_missing(
    mock_db,
) -> None:
    agent = types.SimpleNamespace(
        id=18,
        name="General Agent",
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        owner_tenant_id=None,
    )

    package = types.SimpleNamespace(
        id=318,
        name="系统核心技能包",
        is_active=True,
        is_deleted=False,
        valves_config=None,
    )
    skill = types.SimpleNamespace(
        id=418,
        package_id=318,
        is_active=True,
        is_deleted=False,
        config={
            "builtin_type": "web_search",
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search the web",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                }
            ],
        },
        name="web_search",
        description="Search the web",
        type=SkillTypeEnum.BUILTIN.value,
        timeout=30,
        package=package,
    )
    grant = types.SimpleNamespace(
        id=518,
        agent_id=18,
        skill_id=418,
        enabled=True,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        config_override=None,
        skill=skill,
    )

    mock_db.execute.side_effect = [
        _make_scalars_result([grant]),
        _make_iterable_result([]),
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=None)

    assert result is not None
    assert [tool.name for tool in result.tools] == ["web_search", "get_current_time"]
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert "get_current_time" in result.selected_skill_names
    assert result.tools[1].config["auto_injected"] is True


@pytest.mark.asyncio
async def test_resolve_for_agent_does_not_duplicate_existing_time_tool(
    mock_db,
) -> None:
    agent = types.SimpleNamespace(
        id=19,
        name="Time Agent",
        scope=ResourceScopeEnum.ADMIN_ONLY.value,
        owner_tenant_id=None,
    )

    package = types.SimpleNamespace(
        id=319,
        name="系统核心技能包",
        is_active=True,
        is_deleted=False,
        valves_config=None,
    )
    skill = types.SimpleNamespace(
        id=419,
        package_id=319,
        is_active=True,
        is_deleted=False,
        config={"builtin_type": "get_current_time"},
        name="get_current_time",
        description="Get current time",
        type=SkillTypeEnum.BUILTIN.value,
        timeout=15,
        input_schema={
            "type": "object",
            "properties": {
                "timezone_name": {"type": "string"},
            },
            "required": [],
        },
        package=package,
    )
    grant = types.SimpleNamespace(
        id=519,
        agent_id=19,
        skill_id=419,
        enabled=True,
        default_consent_mode="auto",
        capability_consent_overrides=None,
        config_override=None,
        skill=skill,
    )

    mock_db.execute.side_effect = [
        _make_scalars_result([grant]),
        _make_iterable_result([]),
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=None)

    assert result is not None
    assert [tool.name for tool in result.tools] == ["get_current_time"]
    assert result.selected_skill_names.count("get_current_time") == 1


@pytest.mark.asyncio
async def test_resolve_for_agent_injects_time_tool_without_skill_grants(mock_db) -> None:
    agent = MagicMock()
    agent.id = 9
    agent.name = "No Skills"
    agent.owner_tenant_id = 1

    mock_db.execute.return_value = _make_scalars_result([])

    result = await resolve_for_agent(mock_db, agent, tenant_id=1)

    assert result is not None
    assert [tool.name for tool in result.tools] == ["get_current_time"]
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert "get_current_time" in result.selected_skill_names


# ── ConversationEngine 工具注入集成测试 ──


@pytest.mark.asyncio
async def test_conversation_engine_injects_tools_into_gateway() -> None:
    """skill_result.tools → runtime-v2 adapter.chat(tools=...) / 说明"""
    gateway = MagicMock()
    gateway.get_provider_and_key = AsyncMock()
    gateway._merge_model_provider_snapshots = MagicMock(
        side_effect=lambda billing_context, **_: billing_context
    )
    engine = ConversationEngine(db=MagicMock(), gateway=gateway, sandbox=MagicMock())

    provider = MagicMock()
    provider.code = "mock-provider"
    model = MagicMock()
    model.provider = provider
    model.code = "mock-model"
    model.supports_vision = False

    agent = MagicMock(
        spec=[
            "id",
            "name",
            "system_prompt",
            "model",
            "temperature",
            "max_tokens",
            "top_p",
            "rag_config",
        ]
    )
    agent.id = 99
    agent.name = "ToolInjectionAgent"
    agent.system_prompt = "You are {{ agent_name }}"
    agent.model = model
    agent.temperature = 0.1
    agent.max_tokens = 256
    agent.top_p = 1.0
    agent.rag_config = None

    request = ExecutionRequest(
        agent_id=99,
        tenant_id=1,
        user_id=10,
        messages=[ChatMessage(role="user", content="please read this page content")],
        conversation_id=123,
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_title": "Conversation Management",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                    ]
                },
            }
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="get_page_context",
                description="Read current page context",
            )
        ]
    )

    opt_result = MagicMock()
    opt_result.tools = skill_result.tools
    opt_result.skipped = True
    opt_result.total = 1
    opt_result.selected = 1
    provider.type = "openai_compatible"
    provider.base_url = "https://api.example.com/v1"
    provider.config = {}
    provider.id = 321

    api_key = MagicMock()
    api_key.decrypt_key.return_value = "sk-test"
    api_key.increment_usage = MagicMock()
    gateway.get_provider_and_key = AsyncMock(return_value=(provider, api_key))
    model.id = 654
    model.name = "mock-model"
    model.input_price_per_1k = 0.0
    model.output_price_per_1k = 0.0
    adapter = MagicMock()
    adapter.wire_api = "chat_completions"
    adapter.chat = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=8,
        )
    )
    runtime_context = _StreamRuntimeContext(
        provider=provider,
        api_key=api_key,
        ai_model=model,
        model_code=model.code,
        is_vision=False,
        is_audio=False,
        is_video=False,
        estimated_input=0,
        metering_context=None,
        should_meter_usage=False,
        should_record_call_log=False,
        runtime_info={},
    )

    with (
        patch("app.ai.rag_injector.merge_kb_ids", return_value=None),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=(None, {})),
        ),
        patch(
            "app.services.ai.conversation_service.ConversationService.get_context_compaction_snapshot",
            new=AsyncMock(return_value=None),
        ),
        patch("app.ai.tools.optimizer.optimize_tools", return_value=opt_result),
        patch(
            "app.ai.routing.router.ModelRouter.route",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.ai.engine.conversation.TokenCounter.count_messages_tokens",
            return_value=0,
        ),
        patch(
            "app.ai.engine.conversation.ConversationEngine._prepare_stream_runtime",
            new=AsyncMock(return_value=runtime_context),
        ),
        patch(
            "app.ai.engine.conversation.AdapterRegistry.create_adapter",
            return_value=adapter,
        ),
    ):
        result = await engine.execute(agent, request, skill_result=skill_result)

    assert result.success is False
    assert result.partial is True
    assert adapter.chat.call_count >= 1
    first_call = adapter.chat.call_args_list[0]
    sent_tools = first_call.kwargs.get("tools", first_call[1].get("tools"))
    assert sent_tools is not None
    assert sent_tools[0]["function"]["name"] == "get_page_context"


# ========================================
# P0 Fix: Tool Optimizer Protected Tools
# ========================================


class TestToolOptimizerProtectedTools:
    """工具优化器保护工具白名单测试 / Test."""

    def test_get_page_context_always_retained_when_many_tools(self):
        """get_page_context 在工具数超阈值时不被过滤 / get_page_context"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(
                name="get_page_context", description="Read current page context"
            ),
            ToolDefinition(name="tool_a", description="Tool A"),
            ToolDefinition(name="tool_b", description="Tool B"),
            ToolDefinition(name="tool_c", description="Tool C for data query"),
            ToolDefinition(name="tool_d", description="Tool D for search"),
            ToolDefinition(name="tool_e", description="Tool E"),
            ToolDefinition(name="tool_f", description="Tool F"),
            ToolDefinition(name="tool_g", description="Tool G"),
            ToolDefinition(name="tool_h", description="Tool H"),
            ToolDefinition(name="tool_i", description="Tool I"),
        ]

        result = optimize_tools(tools, "tell me about the weather")

        assert not result.skipped
        tool_names = {t.name for t in result.tools}
        assert "get_page_context" in tool_names

    def test_protected_tools_dont_consume_budget(self):
        """保护工具不占用优化名额 / Description."""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(
                name="get_page_context", description="Read current page context"
            ),
        ]
        for i in range(10):
            tools.append(
                ToolDefinition(name=f"filler_{i}", description=f"Filler tool {i}")
            )

        result = optimize_tools(tools, "random question", max_after_optimization=4)

        assert not result.skipped
        tool_names = [t.name for t in result.tools]
        assert tool_names[0] == "get_page_context"
        # budget = max_after_optimization - len(protected) = 4 - 1 = 3
        assert len(result.tools) == 4  # 1 protected + 3 optimized

    def test_no_protected_tools_works_normally(self):
        """无保护工具时优化器行为不变 / Description."""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name=f"tool_{i}", description=f"Tool {i}") for i in range(10)
        ]

        result = optimize_tools(tools, "hello", max_after_optimization=5)

        assert not result.skipped
        assert len(result.tools) == 5

    def test_skip_optimization_under_threshold(self):
        """工具数在阈值内时跳过优化（含保护工具） / （ ）"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="tool_a", description="Tool A"),
        ]

        result = optimize_tools(tools, "hello")

        assert result.skipped
        assert len(result.tools) == 2

    def test_explicit_tool_names_are_retained_even_when_budget_is_tight(self):
        """用户明确点名工具名时，不应在优化阶段被筛掉。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
            ToolDefinition(name="web_search", description="Web search"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
            ToolDefinition(name="get_current_weather", description="Current weather"),
            ToolDefinition(name="get_weather_forecast", description="Weather forecast"),
        ]

        result = optimize_tools(
            tools,
            "必须使用 get_current_weather 和 get_weather_forecast 两个天气工具查询北京天气",
        )

        tool_names = {t.name for t in result.tools}
        assert "get_current_weather" in tool_names
        assert "get_weather_forecast" in tool_names

    def test_web_search_alias_phrase_retains_web_search_tool(self):
        """用户使用“联网搜索”这类强别名时，也要保留 web_search。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a web page"),
            ToolDefinition(name="tool_a", description="Misc"),
            ToolDefinition(name="tool_b", description="Misc"),
        ]

        result = optimize_tools(
            tools,
            "联网搜索 技能",
            max_after_optimization=5,
        )

        tool_names = {t.name for t in result.tools}
        assert "web_search" in tool_names

    def test_weather_query_prefers_weather_tools_over_web_search_bias(self):
        """天气问题不应仅因为“天气”关键词而优先保留 web_search。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
            ToolDefinition(
                name="web_search", description="Web search latest internet pages"
            ),
            ToolDefinition(name="fetch_url", description="Fetch a web page"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
        ]

        result = optimize_tools(
            tools,
            "请直接使用天气技能查询北京当前天气和未来两天预报，不要使用联网搜索。",
        )

        tool_names = {t.name for t in result.tools}
        assert "get_current_weather" in tool_names
        assert "get_weather_forecast" in tool_names

    def test_weather_query_with_online_word_still_prefers_weather_tools(self):
        """天气查询即使带“联网/查询”字样，也应优先保留天气工具。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
            ToolDefinition(name="tool_a", description="Misc tool"),
            ToolDefinition(name="tool_b", description="Misc tool"),
            ToolDefinition(name="tool_c", description="Misc tool"),
        ]

        result = optimize_tools(
            tools,
            "联网查询一下 凤凰县未来七天的天气",
            max_after_optimization=5,
        )

        non_protected = [
            tool.name
            for tool in result.tools
            if tool.name
            not in {"get_page_context", "invoke_page_operation", "query_records"}
        ]
        assert set(non_protected[:2]) == {
            "get_current_weather",
            "get_weather_forecast",
        }

    def test_web_research_family_reorders_small_toolset_to_prefer_web_tools(self):
        """即使工具数不多，web_research continuation 也应把 web 工具排到 data_* 前面。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ]

        result = optimize_tools(
            tools,
            "Continue the same external research task.",
            used_tool_names={"web_search"},
            preferred_family="web_research",
        )

        ordered = [tool.name for tool in result.tools]
        assert ordered.index("web_search") < ordered.index("query_records")

    def test_time_query_prefers_current_time_tool(self):
        """时间问题应优先保留 get_current_time，而不是联网搜索。"""
        from app.ai.tools.optimizer import optimize_tools

        tools = [
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Page operations"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_current_time", description="Get current time"),
            ToolDefinition(name="query_records", description="Query data"),
            ToolDefinition(name="tool_a", description="Misc tool"),
            ToolDefinition(name="tool_b", description="Misc tool"),
        ]

        result = optimize_tools(
            tools,
            "现在几点？请直接告诉我当前时间。",
            preferred_family="time_ops",
        )

        ordered = [tool.name for tool in result.tools]
        assert ordered.index("get_current_time") < ordered.index("web_search")


# ========================================
# P0 Fix: PageContext.page_data Size Limit
# ========================================


class TestPageContextDataSizeLimit:
    """PageContext.page_data 大小限制测试 / Test."""

    def test_normal_page_data_passes(self):
        """正常大小的 page_data 通过验证 / page_data"""
        from app.schemas.ai.agent_chat import PageContext

        ctx = PageContext(
            page_key="admin.dashboard",
            page_title="Dashboard",
            page_data={"metric": "users", "count": 42},
        )
        assert ctx.page_data == {"metric": "users", "count": 42}

    def test_oversized_page_data_rejected(self):
        """Schema 层不再拒绝超大 page_data，运行期限制负责拦截 / Schema no longer rejects oversized page_data."""
        from app.schemas.ai.agent_chat import PageContext

        large_data = {"key": "x" * 10000}
        ctx = PageContext(
            page_key="admin.dashboard",
            page_data=large_data,
        )
        assert ctx.page_data == large_data

    def test_none_page_data_passes(self):
        """page_data 为 None 时不校验 / page_data None"""
        from app.schemas.ai.agent_chat import PageContext

        ctx = PageContext(page_key="admin.dashboard")
        assert ctx.page_data is None

    def test_normalize_rejects_oversized(self):
        """normalize 仅做结构标准化，不再做大小拒绝 / normalize only standardizes structure now."""
        from app.schemas.ai.agent_chat import PageContext

        oversized = {"key": "x" * 9000}
        result = PageContext.normalize({"page_key": "test", "page_data": oversized})
        assert result == {"page_key": "test", "page_data": oversized}

    def test_boundary_page_data_passes(self):
        """刚好在 4KB 限制内的 page_data 通过验证 / 4KB page_data"""
        from app.schemas.ai.agent_chat import PageContext

        # 构造一个接近但不超过 4KB 的 page_data
        data = {"k": "a" * 3900}
        ctx = PageContext(page_key="test", page_data=data)
        assert ctx.page_data is not None


# ========================================
# P0 Fix: PageContextExecutor Truncation
# ========================================


class TestPageContextExecutorTruncation:
    """PageContextExecutor 输出截断保护测试 / Test."""

    @pytest.mark.asyncio
    async def test_normal_output_not_truncated(self):
        """正常 page_data 不被截断 / page_data"""
        from app.ai.tools.executors.page_context_executor import PageContextExecutor

        executor = PageContextExecutor()
        context = MagicMock()
        context.variables = {
            "page_context": {
                "page_key": "admin.user.list",
                "page_title": "User List",
                "page_data": {"total": 100},
            }
        }
        definition = ToolDefinition(name="get_page_context", description="")

        result = await executor.execute(definition, "tc1", {}, context)

        assert result.success
        assert "truncated" not in result.output
        assert "admin.user.list" in result.output

    @pytest.mark.asyncio
    async def test_repeated_get_page_context_same_turn_returns_compact_hint(self):
        """同一轮重复读取页面上下文时，返回幂等提示而不是完整重复内容。"""
        from app.ai.tools.executors.page_context_executor import PageContextExecutor

        executor = PageContextExecutor()
        context = MagicMock()
        context.variables = {
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_title": "智能体管理",
                "page_data": {
                    "entity_name": "智能体名称",
                },
            }
        }
        definition = ToolDefinition(name="get_page_context", description="")

        first_result = await executor.execute(definition, "tc-repeat-1", {}, context)
        second_result = await executor.execute(definition, "tc-repeat-2", {}, context)

        assert first_result.success
        assert "Page: admin.ai.agents" in first_result.output
        assert second_result.success
        assert "already returned earlier in this turn" in second_result.output
        assert "Current page: admin.ai.agents." in second_result.output
        assert "Page: admin.ai.agents" not in second_result.output

    @pytest.mark.asyncio
    async def test_large_page_data_truncated(self):
        """超大 page_data 被截断（绕过 schema 校验的内部路径防御） / page_data （ schema ..."""
        from app.ai.tools.executors.page_context_executor import (
            MAX_OUTPUT_CHARS,
            PageContextExecutor,
        )

        executor = PageContextExecutor()
        large_ctx = {
            "page_key": "admin.data.export",
            "page_data": {"rows": "x" * (MAX_OUTPUT_CHARS + 1000)},
        }
        context = MagicMock()
        context.variables = {"page_context": large_ctx}
        definition = ToolDefinition(name="get_page_context", description="")

        with patch(
            "app.ai.tools.executors.page_context_executor.PageContext.normalize",
            return_value=large_ctx,
        ):
            result = await executor.execute(definition, "tc2", {}, context)

        assert result.success
        assert "[truncated]" in result.output

    @pytest.mark.asyncio
    async def test_editor_operations_summary_when_has_editor(self):
        """富文本页 has_editor 时输出 available_operations 摘要 / has_editor ..."""
        from app.ai.tools.executors.page_context_executor import PageContextExecutor

        executor = PageContextExecutor()
        context = MagicMock()
        context.variables = {
            "page_context": {
                "page_key": "tenant.plugins.novusdoc.editor.42",
                "page_title": "Document",
                "page_data": {
                    "has_editor": True,
                    "entity_description": "Rich text editor",
                    "available_operations": [
                        {"name": "get_editor_html", "description": "Get HTML content"},
                        {
                            "name": "replace_section",
                            "description": "Replace section",
                            "params": {"old_html": {}, "new_html": {}},
                        },
                    ],
                },
            }
        }
        definition = ToolDefinition(name="get_page_context", description="")

        result = await executor.execute(definition, "tc-editor", {}, context)

        assert result.success
        assert "Available Editor Operations" in result.output
        assert "get_editor_html" in result.output
        assert "replace_section" in result.output

    @pytest.mark.asyncio
    async def test_generic_operations_and_fallback_source_are_visible(self):
        """普通页面也要输出 available_operations，且 fallback 来源需显式标识。"""
        from app.ai.tools.executors.page_context_executor import PageContextExecutor

        executor = PageContextExecutor()
        context = MagicMock()
        context.variables = {
            "page_context": {
                "page_key": "tenant.portal.home",
                "page_title": "Portal Home",
                "page_data": {
                    "source": "dom_snapshot",
                    "detail_fields": [
                        {"label": "状态", "value": "运行中"},
                    ],
                    "stat_cards": [
                        {"label": "请求数", "value": "128"},
                    ],
                    "text_blocks": [
                        "这是当前页面正文中的一段摘要信息。",
                    ],
                    "available_operations": [
                        {
                            "name": "search",
                            "label": "Search",
                            "description": "Apply structured search",
                            "readonly": True,
                            "params": {
                                "keyword": {"type": "string", "required": True},
                                "status": {
                                    "type": "string",
                                    "enum": ["active", "paused"],
                                },
                            },
                        }
                    ],
                },
            }
        }
        definition = ToolDefinition(name="get_page_context", description="")

        result = await executor.execute(definition, "tc-generic-ops", {}, context)

        assert result.success
        assert "Context Source: dom_snapshot" in result.output
        assert "Available Page Operations" in result.output
        assert "search [readonly]" in result.output
        assert "keyword:string required" in result.output
        assert "status:string enum[active, paused]" in result.output
        assert "Key Metrics: 请求数=128" in result.output
        assert "Visible Details: 状态=运行中" in result.output
        assert "Visible Text Summary:" in result.output
        assert (
            "If the latest user turn asks for multiple page operations" in result.output
        )
        assert "follow the latest user turn" in result.output
