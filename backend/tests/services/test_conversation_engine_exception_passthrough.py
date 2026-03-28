import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *a, **kw: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest, PreparedExecution, ToolUsePolicy
from app.ai.quota import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.config import settings
from app.middleware.trace import trace_id_var


@pytest.mark.asyncio
async def test_conversation_engine_execute_reraises_business_exception() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    engine._prepare_execution = AsyncMock(
        return_value=PreparedExecution(
            messages=[ChatMessage(role="user", content="hello")],
            tools=[],
            rag_sources=None,
            tool_consent_modes={},
            optimize_event=None,
            route_result=None,
        )
    )
    engine._call_llm = AsyncMock(
        side_effect=QuotaExceeded("AI quota exceeded for passthrough test")
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)

    with pytest.raises(QuotaExceeded) as exc_info:
        await engine.execute(agent, request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == 4291


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_factory", "expected_code"),
    [
        (lambda: QuotaExceeded("quota preflight blocked"), 4291),
        (lambda: RateLimitExceeded("rate limit preflight blocked"), 4292),
    ],
)
async def test_conversation_engine_stream_execute_preflight_reraises_business_exception(
    exc_factory,
    expected_code: int,
) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    engine._prepare_execution = AsyncMock(
        return_value=PreparedExecution(
            messages=[ChatMessage(role="user", content="hello")],
            tools=[],
            rag_sources=None,
            tool_consent_modes={},
            optimize_event=None,
            route_result=None,
        )
    )
    engine._prepare_stream_runtime = AsyncMock(side_effect=exc_factory())

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )
    agent = SimpleNamespace(id=1)

    with pytest.raises((QuotaExceeded, RateLimitExceeded)) as exc_info:
        await engine.stream_execute(agent, request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_conversation_engine_execute_hides_generic_exception_in_production() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    engine._prepare_execution = AsyncMock(
        side_effect=RuntimeError("secret provider stack")
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-conversation-prod")
    settings.DEBUG = False
    try:
        result = await engine.execute(agent, request)
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert result.success is False
    assert "secret provider stack" not in (result.error or "")
    assert "trace-conversation-prod" in (result.error or "")


@pytest.mark.asyncio
async def test_conversation_engine_retries_capability_denial_with_required_tool_policy() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="联网帮我查一下 gpt 到底是什么东西")],
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        all_tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
            ToolDefinition(name="data_query", description="Query data"),
        ],
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
        rag_sources=None,
        tool_consent_modes={},
        optimize_event=None,
        route_result=None,
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        side_effect=[
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="我现在没有外部互联网搜索工具，只能基于已有知识回答。",
                ),
                total_tokens=10,
            ),
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_search",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"GPT 是什么","max_results":5}',
                        },
                    }
                ],
                total_tokens=12,
            ),
        ]
    )
    engine._handle_tool_calls = AsyncMock(
        return_value=(
            ChatResponse(
                message=ChatMessage(role="assistant", content="GPT 是生成式预训练 Transformer。"),
                total_tokens=20,
            ),
            [],
            20,
        )
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网帮我查一下 gpt 到底是什么东西")],
        input_variables={},
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    assert result.output == "GPT 是生成式预训练 Transformer。"
    assert len(engine._call_llm.await_args_list) == 2
    assert engine._call_llm.await_args_list[0].kwargs["tool_use_policy"].mode == "auto"
    assert engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].mode == "required"
    assert engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].family == "web_research"
    assert [tool.name for tool in engine._call_llm.await_args_list[1].kwargs["tools"]] == [
        "web_search",
        "fetch_url",
    ]


def test_contract_breach_retry_uses_semantic_capability_terms_for_custom_web_tool() -> None:
    tools = [
        ToolDefinition(
            name="external_lookup",
            description="Research external public sources",
            semantic_family="web_research",
            semantic_tags=["联网搜索", "网页查询", "最新信息", "官方来源"],
        ),
    ]

    should_retry, retry_policy, response_text = ConversationEngine._should_retry_tool_contract_breach(
        response=ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="我现在不能联网搜索公开网页，只能基于已有知识回答。",
            ),
        ),
        current_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=["external_lookup"],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
        tools=tools,
        input_variables={},
    )

    assert should_retry is True
    assert response_text == "我现在不能联网搜索公开网页，只能基于已有知识回答。"
    assert retry_policy is not None
    assert retry_policy.family == "web_research"
    assert retry_policy.mode == "required"
    assert retry_policy.allowed_tool_names == ["external_lookup"]


def test_conversation_engine_detects_capability_denial_from_semantic_family_terms() -> None:
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="当前无法使用网页来源检索能力，请直接提问。",
        ),
    )
    current_policy = ToolUsePolicy(
        family="none",
        mode="auto",
        allowed_tool_names=["public_lookup"],
        retry_on_contract_breach=True,
        reason="default_auto",
    )
    tools = [
        ToolDefinition(
            name="public_lookup",
            description="Find external references",
            semantic_family="web_research",
            semantic_tags=["网页", "来源", "检索"],
        )
    ]

    should_retry, retry_policy, response_text = (
        ConversationEngine._should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables={},
        )
    )

    assert should_retry is True
    assert response_text == "当前无法使用网页来源检索能力，请直接提问。"
    assert retry_policy == ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["public_lookup"],
        retry_on_contract_breach=False,
        reason="capability_denial:web_research",
    )


def test_conversation_engine_retries_when_tool_call_leaks_as_plain_text() -> None:
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="to=functions.get_page_context 天天乐不json_string",
        ),
    )
    current_policy = ToolUsePolicy(
        family="none",
        mode="auto",
        allowed_tool_names=["get_page_context", "invoke_page_operation", "web_search"],
        retry_on_contract_breach=True,
        reason="default_auto",
    )
    tools = [
        ToolDefinition(name="get_page_context", description="Read current page context"),
        ToolDefinition(name="invoke_page_operation", description="Execute page operation"),
        ToolDefinition(name="web_search", description="Search the web"),
    ]

    should_retry, retry_policy, response_text = (
        ConversationEngine._should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables={},
        )
    )

    assert should_retry is True
    assert response_text == "to=functions.get_page_context 天天乐不json_string"
    assert retry_policy == ToolUsePolicy(
        family="page_ops",
        mode="required",
        allowed_tool_names=["get_page_context", "invoke_page_operation"],
        retry_on_contract_breach=False,
        reason="textual_tool_call_leak:get_page_context",
    )
