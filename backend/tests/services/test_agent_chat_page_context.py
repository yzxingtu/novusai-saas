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

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.skills.resolver import SkillResolveResult, SkillResolver, resolve_for_agent
from app.ai.tools.executors.page_context_executor import PageContextExecutor
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


def test_page_context_normalize_variables_standardizes_legacy_variables_payload() -> None:
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
async def test_validate_page_context_size_accepts_payload_within_runtime_limit() -> None:
    from app.services.ai.page_context_limits import validate_page_context_size

    page_context = {
        "page_key": "tenant.agent.detail",
        "page_data": {"agent_id": 1, "status": "active"},
    }

    with patch(
        "app.services.ai.page_context_limits.get_page_context_max_bytes",
        AsyncMock(return_value=1024),
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
        AsyncMock(return_value=32),
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
    result = await executor.execute(
        ToolDefinition(name="get_page_context"),
        "call_2",
        {},
        ExecutionContext(tenant_id=1, agent_id=2, variables={}),
    )

    assert result.success is True
    assert result.output == "No page context available."


@pytest.mark.asyncio
async def test_agent_chat_service_injects_page_context_into_execution_request(mock_db) -> None:
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
    service.conversation_svc.get_or_create_for_chat = AsyncMock(return_value=conversation)
    service.conversation_svc.load_chat_history = AsyncMock(return_value=[])
    service.conversation_svc.persist_chat_messages = AsyncMock(return_value=[])
    service.conversation_svc.update_stats = AsyncMock(return_value=None)
    service.conversation_svc.mark_memory_updated = AsyncMock(return_value=None)

    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=result)

    with patch("app.services.ai.agent_chat_service.ExecutionDispatcher", return_value=dispatcher), patch(
        "app.services.ai.agent_chat_service.AgentQuotaManager.record_conversation",
        new=AsyncMock(),
    ), patch(
        "app.services.ai.agent_chat_service.AgentStatsManager.record_chat",
        new=AsyncMock(),
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
async def test_resolve_for_agent_with_skill_grant_includes_get_page_context_tool(mock_db) -> None:
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
        [],
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=1)

    assert result is not None
    assert [tool.name for tool in result.tools] == ["get_page_context"]
    assert result.tool_consent_modes["get_page_context"] == "auto"
    assert result.tools[0].source_package_name == "页面感知"
    openai_tools = to_openai_tools(result.tools)
    assert openai_tools[0]["function"]["name"] == "get_page_context"


@pytest.mark.asyncio
async def test_resolve_for_agent_admin_grant_applies_capability_override(mock_db) -> None:
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
        [],
    ]

    result = await resolve_for_agent(mock_db, agent, tenant_id=None)

    assert result is not None
    assert [tool.name for tool in result.tools] == ["get_page_context"]
    assert result.tool_consent_modes["get_page_context"] == "reject"
    assert result.tools[0].source_package_name == "页面感知"
    openai_tools = to_openai_tools(result.tools)
    assert openai_tools[0]["function"]["name"] == "get_page_context"

@pytest.mark.asyncio
async def test_resolve_for_agent_returns_none_without_skill_grants(mock_db) -> None:
    agent = MagicMock()
    agent.id = 9
    agent.name = "No Skills"
    agent.owner_tenant_id = 1

    mock_db.execute.return_value = _make_scalars_result([])

    result = await resolve_for_agent(mock_db, agent, tenant_id=1)

    assert result is None


# ── ConversationEngine 工具注入集成测试 ──


@pytest.mark.asyncio
async def test_conversation_engine_injects_tools_into_gateway() -> None:
    """skill_result.tools → _prepare_execution → _call_llm → gateway.chat(tools=...) / 说明"""
    gateway = MagicMock()
    gateway.chat = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=8,
        )
    )
    engine = ConversationEngine(
        db=MagicMock(), gateway=gateway, sandbox=MagicMock()
    )

    provider = MagicMock()
    provider.code = "mock-provider"
    model = MagicMock()
    model.provider = provider
    model.code = "mock-model"
    model.supports_vision = False

    agent = MagicMock(spec=[
        "id", "name", "system_prompt", "model",
        "temperature", "max_tokens", "top_p", "rag_config",
    ])
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
        messages=[ChatMessage(role="user", content="hello")],
        conversation_id=123,
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

    with (
        patch("app.ai.rag_injector.merge_kb_ids", return_value=None),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=(None, {})),
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
    ):
        result = await engine.execute(agent, request, skill_result=skill_result)

    assert result.success is True
    gateway.chat.assert_called_once()
    sent_tools = gateway.chat.call_args.kwargs.get(
        "tools", gateway.chat.call_args[1].get("tools")
    )
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
            ToolDefinition(name="get_page_context", description="Read current page context"),
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
            ToolDefinition(name="get_page_context", description="Read current page context"),
        ]
        for i in range(10):
            tools.append(ToolDefinition(name=f"filler_{i}", description=f"Filler tool {i}"))

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
            ToolDefinition(name=f"tool_{i}", description=f"Tool {i}")
            for i in range(10)
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
    async def test_large_page_data_truncated(self):
        """超大 page_data 被截断（绕过 schema 校验的内部路径防御） / page_data （ schema ..."""
        from app.ai.tools.executors.page_context_executor import MAX_OUTPUT_CHARS, PageContextExecutor

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
                        {"name": "replace_section", "description": "Replace section", "params": {"old_html": {}, "new_html": {}}},
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
                    "available_operations": [
                        {
                            "name": "search",
                            "label": "Search",
                            "description": "Apply structured search",
                            "readonly": True,
                            "params": {
                                "keyword": {"type": "string", "required": True},
                                "status": {"type": "string", "enum": ["active", "paused"]},
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
