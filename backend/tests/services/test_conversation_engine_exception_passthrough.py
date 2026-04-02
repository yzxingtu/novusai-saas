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
from app.ai.engine.types import (
    ExecutionRequest,
    PreparedExecution,
    ResearchContinuationContext,
    ToolUsePolicy,
)
from app.ai.quota import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.tools.types import ToolDefinition, ToolResult
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


@pytest.mark.asyncio
async def test_conversation_engine_retries_summary_without_fetch_with_fetch_url() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="联网查阅一下，今天乌克兰的局势")],
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        all_tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
            ToolDefinition(name="data_query", description="Query data"),
        ],
        continuation_context=SimpleNamespace(
            active=True,
            family="web_research",
            origin="continuation",
            current_user_text="继续查看正文。",
            research_target_text="乌克兰 局势 今天 最新 官方 新闻",
            recent_successful_tool_names=["web_search"],
            recent_web_queries=["乌克兰 局势 今天 最新 官方 新闻"],
            search_query_count=1,
            fetched_url_count=0,
            research_instruction_texts=["联网查阅一下，今天乌克兰的局势"],
        ),
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="active_continuation:web_research",
        ),
        rag_sources=None,
        tool_consent_modes={},
        optimize_event=None,
        route_result=None,
    )
    engine._prepare_execution = AsyncMock(return_value=prep)

    first_response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_search",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"乌克兰 局势 今天 最新 官方 新闻","max_results":5}',
                },
            }
        ],
        total_tokens=20,
    )
    retry_response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_fetch",
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": '{"url":"https://example.com/ukraine-live","max_length":4000}',
                },
            }
        ],
        total_tokens=8,
    )
    engine._call_llm = AsyncMock(side_effect=[first_response, retry_response])

    async def _fake_handle_tool_calls(
        *,
        messages,
        response,
        **kwargs,
    ):
        _ = kwargs
        tool_name = response.tool_calls[0]["function"]["name"]
        if tool_name == "web_search":
            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            **response.tool_calls[0],
                            "success": True,
                        }
                    ],
                )
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    content="Search results for: 乌克兰 局势 今天 最新 官方 新闻",
                    tool_call_id="call_search",
                )
            )
            return (
                ChatResponse(
                    message=ChatMessage(
                        role="assistant",
                        content="Here is a summary based only on the search snippets.",
                    ),
                    total_tokens=12,
                ),
                [
                    ToolResult(
                        tool_call_id="call_search",
                        name="web_search",
                        success=True,
                        output="Search results for: 乌克兰 局势 今天 最新 官方 新闻",
                    )
                ],
                32,
            )

        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        **response.tool_calls[0],
                        "success": True,
                    }
                ],
            )
        )
        messages.append(
            ChatMessage(
                role="tool",
                content="Content from https://example.com/ukraine-live:\n\n正文内容",
                tool_call_id="call_fetch",
            )
        )
        return (
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="基于正文，今天乌克兰局势仍然处于持续对抗状态。",
                ),
                total_tokens=15,
            ),
            [
                ToolResult(
                    tool_call_id="call_fetch",
                    name="fetch_url",
                    success=True,
                    output="Content from https://example.com/ukraine-live:\n\n正文内容",
                )
            ],
            23,
        )

    engine._handle_tool_calls = AsyncMock(side_effect=_fake_handle_tool_calls)

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查阅一下，今天乌克兰的局势")],
        input_variables={},
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    assert "基于正文" in result.output
    assert len(engine._call_llm.await_args_list) == 2
    assert engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].reason == (
        "web_research_summary_without_fetch"
    )
    assert [tool.name for tool in engine._call_llm.await_args_list[1].kwargs["tools"]] == [
        "web_search",
        "fetch_url",
    ]


@pytest.mark.asyncio
async def test_conversation_engine_execute_calls_context_engine_after_turn() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    context_engine = AsyncMock()
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="hello")],
        tools=[],
        rag_sources=None,
        tool_consent_modes={},
        optimize_event=None,
        route_result=None,
        context_engine=context_engine,
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="world"),
            total_tokens=8,
        )
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="hello")],
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    context_engine.after_turn.assert_awaited_once()


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


def test_conversation_engine_retries_same_explicit_family_before_switching() -> None:
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="我现在没有实时天气接口，不能直接查询今天北京天气。",
        ),
    )
    current_policy = ToolUsePolicy(
        family="weather",
        mode="auto",
        allowed_tool_names=["get_current_weather", "get_weather_forecast"],
        retry_on_contract_breach=True,
        reason="explicit_weather_request",
    )
    tools = [
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
        ToolDefinition(name="get_page_context", description="Read page context"),
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
    assert response_text == "我现在没有实时天气接口，不能直接查询今天北京天气。"
    assert retry_policy == ToolUsePolicy(
        family="weather",
        mode="required",
        allowed_tool_names=["get_current_weather", "get_weather_forecast"],
        retry_on_contract_breach=False,
        reason="capability_denial:weather",
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


def test_web_research_contract_retry_does_not_override_explicit_weather_policy() -> None:
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="天气服务这次没有返回结果。",
        ),
    )
    current_policy = ToolUsePolicy(
        family="weather",
        mode="auto",
        allowed_tool_names=["get_current_weather", "get_weather_forecast"],
        retry_on_contract_breach=True,
        reason="explicit_weather_request",
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ToolDefinition(name="get_current_weather", description="Get current weather"),
        ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
    ]

    should_retry, retry_policy, response_text = (
        ConversationEngine._should_retry_web_research_contract_breach(
            messages=[ChatMessage(role="user", content="今天北京天气怎么样")],
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables={},
            continuation=ResearchContinuationContext(
                active=True,
                family="web_research",
                current_user_text="今天北京天气怎么样",
                research_target_text="北京天气",
            ),
        )
    )

    assert should_retry is False
    assert retry_policy is None
    assert response_text == ""
