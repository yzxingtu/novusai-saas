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
    ExecutionBudget,
    ExecutionRequest,
    IntentPlan,
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
            ToolDefinition(name="query_records", description="Query data"),
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
        intent_plan=[
            IntentPlan(
                intent_id="intent-1",
                kind="web_research",
                family="web_research",
                order=1,
                user_visible_label="web_research",
                source_text="联网帮我查一下 gpt 到底是什么东西",
                allowed_tool_names=["web_search", "fetch_url"],
                preferred_tool_names=["web_search", "fetch_url"],
                completion_signals=["web_search", "fetch_url"],
            )
        ],
        execution_budget=ExecutionBudget(
            max_prompt_tokens=4000,
            max_completion_tokens=1200,
            max_tool_rounds=2,
            max_elapsed_ms=25000,
            max_retry_per_intent=1,
            max_candidate_tools=3,
            max_tool_result_bytes=16000,
        ),
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
    async def _fake_handle_tool_calls(*, messages, response, **kwargs):
        _ = kwargs
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
        return (
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="GPT 是生成式预训练 Transformer。",
                ),
                total_tokens=20,
            ),
            [
                ToolResult(
                    tool_call_id="call_search",
                    name="web_search",
                    success=True,
                    output="GPT background from web search",
                )
            ],
            20,
            20,
        )

    engine._handle_tool_calls = AsyncMock(side_effect=_fake_handle_tool_calls)

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
            ToolDefinition(name="query_records", description="Query data"),
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
        agent,
        messages,
        response,
        **kwargs,
    ):
        tools = kwargs["tools"]
        all_tools = kwargs["all_tools"]
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
        retry_policy = ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=False,
            reason="web_research_summary_without_fetch",
        )
        retry_call = await engine._call_llm(
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=[tool.name for tool in (all_tools or tools or [])],
            tool_use_policy=retry_policy,
            breach_retry_result="retry_follow_up",
        )
        assert retry_call.tool_calls is not None
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        **retry_call.tool_calls[0],
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
                    tool_call_id="call_search",
                    name="web_search",
                    success=True,
                    output="Search results for: 乌克兰 局势 今天 最新 官方 新闻",
                ),
                ToolResult(
                    tool_call_id="call_fetch",
                    name="fetch_url",
                    success=True,
                    output="Content from https://example.com/ukraine-live:\n\n正文内容",
                ),
            ],
            35,
            35,
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
async def test_conversation_engine_repairs_title_only_answer_after_fetch() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    page_title = "湖南中小学将施行春秋假制度-湖南省人民政府门户网站"
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="你联网查一下 湖南学生放假时间")],
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        all_tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        continuation_context=SimpleNamespace(
            active=True,
            family="web_research",
            origin="continuation",
            current_user_text="继续查看正文。",
            research_target_text="湖南学生放假时间",
            recent_successful_tool_names=["web_search"],
            recent_web_queries=["湖南学生放假时间"],
            search_query_count=1,
            fetched_url_count=0,
            research_instruction_texts=["你联网查一下 湖南学生放假时间"],
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
                    "arguments": '{"query":"湖南学生放假时间","max_results":5}',
                },
            }
        ],
        total_tokens=18,
    )
    retry_fetch_response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_fetch",
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": '{"url":"https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/t20260328_33943174.html","max_length":4000}',
                },
            }
        ],
        total_tokens=7,
    )
    repaired_response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=(
                "湖南义务教育阶段学校已开始统筹推行春秋假制度，春假和秋假通常各安排 2 至 3 天，"
                "一般放在 4 月至 5 月和 10 月至 11 月，并鼓励与双休日或法定节假日衔接。"
            ),
        ),
        total_tokens=20,
    )
    engine._call_llm = AsyncMock(
        side_effect=[first_response, retry_fetch_response, repaired_response]
    )

    async def _fake_handle_tool_calls(
        *,
        agent,
        messages,
        response,
        **kwargs,
    ):
        tools = kwargs["tools"]
        all_tools = kwargs["all_tools"]
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
                content="Search results for: 湖南学生放假时间",
                tool_call_id="call_search",
            )
        )
        retry_policy = ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=False,
            reason="web_research_summary_without_fetch",
        )
        retry_call = await engine._call_llm(
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=[tool.name for tool in (all_tools or tools or [])],
            tool_use_policy=retry_policy,
            breach_retry_result="retry_follow_up",
        )
        assert retry_call.tool_calls is not None
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        **retry_call.tool_calls[0],
                        "success": True,
                    }
                ],
            )
        )
        messages.append(
            ChatMessage(
                role="tool",
                content=(
                    "Content from https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/"
                    "t20260328_33943174.html\n"
                    f"Title: {page_title}\n"
                    "湖南中小学生即将迎来春秋假。"
                ),
                tool_call_id="call_fetch",
            )
        )
        return (
            ChatResponse(
                message=ChatMessage(role="assistant", content=page_title),
                total_tokens=11,
            ),
            [
                ToolResult(
                    tool_call_id="call_search",
                    name="web_search",
                    success=True,
                    output="Search results for: 湖南学生放假时间",
                ),
                ToolResult(
                    tool_call_id="call_fetch",
                    name="fetch_url",
                    success=True,
                    output=(
                        "Content from https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/"
                        "t20260328_33943174.html\n"
                        f"Title: {page_title}\n"
                        "湖南中小学生即将迎来春秋假。"
                    ),
                ),
            ],
            36,
            36,
        )

    engine._handle_tool_calls = AsyncMock(side_effect=_fake_handle_tool_calls)

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="你联网查一下 湖南学生放假时间")],
        input_variables={},
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    assert "春假和秋假通常各安排 2 至 3 天" in result.output
    assert len(engine._call_llm.await_args_list) == 3
    assert engine._call_llm.await_args_list[2].kwargs["tools"] is None
    assert engine._call_llm.await_args_list[2].kwargs["tool_use_policy"] == ToolUsePolicy(
        family="none",
        mode="none",
        allowed_tool_names=[],
        retry_on_contract_breach=False,
        reason="web_research_title_only_after_fetch",
    )
    repair_messages = engine._call_llm.await_args_list[2].kwargs["messages"]
    assert any(
        msg.role == "system"
        and "previous assistant draft did not satisfy the tool-use contract"
        in (msg.content or "").lower()
        for msg in repair_messages
    )
    assert result.turn_record["contract_breach_type"] == (
        "web_research_title_only_after_fetch"
    )


@pytest.mark.asyncio
async def test_conversation_engine_retries_leaked_textual_tool_output_after_partial_web_research() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    prep = PreparedExecution(
        messages=[
            ChatMessage(
                role="user",
                content="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
            )
        ],
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
            ToolDefinition(name="get_page_context", description="Read page context"),
        ],
        all_tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
            ToolDefinition(name="get_page_context", description="Read page context"),
        ],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url", "get_page_context"],
            retry_on_contract_breach=True,
            reason="explicit_web_request",
        ),
        diagnostics={"ordered_requested_families": ["web_research", "page_ops"]},
        rag_sources=None,
        tool_consent_modes={},
        optimize_event=None,
        route_result=None,
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        side_effect=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_search_weather",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"2026-04-03 今天天气 中国","max_results":5}',
                        },
                    },
                    {
                        "id": "call_page_context",
                        "type": "function",
                        "function": {
                            "name": "get_page_context",
                            "arguments": "{}",
                        },
                    },
                ],
                total_tokens=12,
            ),
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_fetch_weather",
                        "type": "function",
                        "function": {
                            "name": "fetch_url",
                            "arguments": '{"url":"https://weather.cma.cn/","max_length":4000}',
                        },
                    },
                    {
                        "id": "call_fetch_ticket",
                        "type": "function",
                        "function": {
                            "name": "fetch_url",
                            "arguments": '{"url":"https://www.gaotie.cn/","max_length":4000}',
                        },
                    }
                ],
                total_tokens=10,
            ),
        ]
    )

    async def _fake_handle_tool_calls(
        *,
        agent,
        messages,
        response,
        **kwargs,
    ):
        tools = kwargs["tools"]
        all_tools = kwargs["all_tools"]
        tool_names = [
            (tool_call.get("function") or {}).get("name")
            for tool_call in (response.tool_calls or [])
        ]
        if tool_names == ["web_search", "get_page_context"]:
            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {**response.tool_calls[0], "success": True},
                        {**response.tool_calls[1], "success": True},
                    ],
                )
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    content="Search results for: 2026-04-03 今天天气 中国",
                    tool_call_id="call_search_weather",
                )
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    content="Page: admin.dashboard\nTitle: 平台控制塔\nData: {\"ai_calls_today\":146}",
                    tool_call_id="call_page_context",
                )
            )

        retry_policy = ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=False,
            reason="leaked_textual_tool_call:web_search",
        )
        retry_call = await engine._call_llm(
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=[tool.name for tool in (all_tools or tools or [])],
            tool_use_policy=retry_policy,
            breach_retry_result="retry_follow_up",
        )
        assert retry_call.tool_calls is not None
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {**tool_call, "success": True}
                    for tool_call in retry_call.tool_calls
                ],
            )
        )
        messages.append(
            ChatMessage(
                role="tool",
                content="Content from https://weather.cma.cn/\nTitle: 中国气象局-天气预报",
                tool_call_id="call_fetch_weather",
            )
        )
        messages.append(
            ChatMessage(
                role="tool",
                content="Content from https://www.gaotie.cn/\nTitle: 高铁网\n北京方向车票可查询",
                tool_call_id="call_fetch_ticket",
            )
        )
        return (
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=(
                        "今天天气方面，可参考中国气象局页面信息；"
                        "去北京的高铁票可以继续通过高铁网等替代来源查询；"
                        "当前页面是 admin.dashboard，显示平台控制塔指标。"
                    ),
                ),
                total_tokens=16,
            ),
            [
                ToolResult(
                    tool_call_id="call_search_weather",
                    name="web_search",
                    success=True,
                    output="Search results for: 2026-04-03 今天天气 中国",
                ),
                ToolResult(
                    tool_call_id="call_page_context",
                    name="get_page_context",
                    success=True,
                    output="Page: admin.dashboard\nTitle: 平台控制塔\nData: {\"ai_calls_today\":146}",
                ),
                ToolResult(
                    tool_call_id="call_fetch_weather",
                    name="fetch_url",
                    success=True,
                    output="Content from https://weather.cma.cn/\nTitle: 中国气象局-天气预报",
                ),
                ToolResult(
                    tool_call_id="call_fetch_ticket",
                    name="fetch_url",
                    success=True,
                    output="Content from https://www.gaotie.cn/\nTitle: 高铁网\n北京方向车票可查询",
                ),
            ],
            38,
            38,
        )

    engine._handle_tool_calls = AsyncMock(side_effect=_fake_handle_tool_calls)

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
            )
        ],
        input_variables={
            "page_context": {
                "page_key": "admin.dashboard",
                "page_title": "平台控制塔",
                "page_data": {"ai_calls_today": 146},
            }
        },
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    assert "今天天气" in result.output
    assert "高铁票" in result.output
    assert "admin.dashboard" in result.output
    assert len(engine._call_llm.await_args_list) == 2
    assert engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].reason.startswith(
        "leaked_textual_tool_call:"
    )


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


def test_web_research_title_only_retry_skips_explicit_title_request() -> None:
    page_title = "湖南中小学将施行春秋假制度-湖南省人民政府门户网站"
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=page_title,
        ),
    )
    current_policy = ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="active_continuation:web_research",
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch a webpage"),
    ]

    should_retry, retry_policy, response_text = (
        ConversationEngine._should_retry_web_research_contract_breach(
            messages=[
                ChatMessage(role="user", content="把这篇网页的标题告诉我"),
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            "id": "call_search",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"湖南中小学将施行春秋假制度","max_results":5}',
                            },
                            "success": True,
                        }
                    ],
                ),
                ChatMessage(
                    role="tool",
                    content="Search results for: 湖南中小学将施行春秋假制度",
                    tool_call_id="call_search",
                ),
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        {
                            "id": "call_fetch",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://searchs.hunan.gov.cn/example","max_length":4000}',
                            },
                            "success": True,
                        }
                    ],
                ),
                ChatMessage(
                    role="tool",
                    content=(
                        "Content from https://searchs.hunan.gov.cn/example\n"
                        f"Title: {page_title}\n"
                        "湖南中小学生即将迎来春秋假。"
                    ),
                    tool_call_id="call_fetch",
                ),
            ],
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables={},
            continuation=ResearchContinuationContext(
                active=True,
                family="web_research",
                current_user_text="把这篇网页的标题告诉我",
                research_target_text="湖南中小学将施行春秋假制度",
            ),
        )
    )

    assert should_retry is False
    assert retry_policy is None
    assert response_text == ""


def test_collect_completed_turn_intents_requires_weather_fetch_or_weather_tool() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="get_page_context", description="Read page context"),
    ]
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call_search_weather",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query":"2026-04-03 上海 今天天气","max_results":5}',
                    },
                    "success": True,
                },
                {
                    "id": "call_page_context",
                    "type": "function",
                    "function": {
                        "name": "get_page_context",
                        "arguments": "{}",
                    },
                    "success": True,
                },
            ],
        ),
        ChatMessage(
            role="tool",
            content="Search results for: 2026-04-03 上海 今天天气",
            tool_call_id="call_search_weather",
        ),
        ChatMessage(
            role="tool",
            content="Page: admin.ai.agents",
            tool_call_id="call_page_context",
        ),
    ]

    completed_without_fetch = ConversationEngine._collect_completed_turn_intents(
        messages,
        tools=tools,
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_title": "智能体名称",
            }
        },
    )

    assert "weather" not in completed_without_fetch
    assert "page_summary" in completed_without_fetch

    messages.extend(
        [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_fetch_weather",
                        "type": "function",
                        "function": {
                            "name": "fetch_url",
                            "arguments": '{"url":"https://weather.cma.cn/","max_length":4000}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(
                role="tool",
                content="Content from https://weather.cma.cn/\nTitle: 中国气象局-天气预报",
                tool_call_id="call_fetch_weather",
            ),
        ]
    )

    completed_with_fetch = ConversationEngine._collect_completed_turn_intents(
        messages,
        tools=tools,
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_title": "智能体名称",
            }
        },
    )

    assert "weather" in completed_with_fetch


def test_ensure_web_research_tool_pair_restores_fetch_url_for_page_first_selection() -> None:
    all_tools = [
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
    ]
    selected_tools = [
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="web_search", description="Search the web"),
    ]

    restored_tools, restored = ConversationEngine._ensure_web_research_tool_pair(
        selected_tools=selected_tools,
        all_tools=all_tools,
        explicit_requested_families=["page_ops", "web_research"],
        policy=ToolUsePolicy(
            family="page_ops",
            mode="required",
            allowed_tool_names=["get_page_context", "web_search"],
            retry_on_contract_breach=False,
            reason="explicit_page_request",
        ),
    )

    assert restored is True
    assert [tool.name for tool in restored_tools] == [
        "get_page_context",
        "web_search",
        "fetch_url",
    ]


def test_restrict_page_tools_for_generic_summary_keeps_get_page_context_only() -> None:
    all_tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="invoke_page_operation", description="Invoke page operation"),
        ToolDefinition(name="pageop_read_current_view", description="Read current view"),
        ToolDefinition(name="pageop_read_visible_rows", description="Read visible rows"),
    ]
    selected_tools = list(all_tools)

    restricted_tools, restricted = ConversationEngine._restrict_page_tools_for_generic_summary(
        selected_tools=selected_tools,
        all_tools=all_tools,
        user_text="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_title": "智能体名称",
            }
        },
    )

    assert restricted is True
    assert [tool.name for tool in restricted_tools] == [
        "web_search",
        "fetch_url",
        "get_page_context",
    ]


def test_restrict_page_tools_for_generic_summary_keeps_detail_tools_when_rows_requested() -> None:
    all_tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="get_page_context", description="Read page context"),
        ToolDefinition(name="pageop_read_visible_rows", description="Read visible rows"),
    ]

    restricted_tools, restricted = ConversationEngine._restrict_page_tools_for_generic_summary(
        selected_tools=list(all_tools),
        all_tools=all_tools,
        user_text="先帮我看看本页面都有什么内容，再把当前可见行也读出来",
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_title": "智能体名称",
            }
        },
    )

    assert restricted is False
    assert [tool.name for tool in restricted_tools] == [
        "web_search",
        "fetch_url",
        "get_page_context",
        "pageop_read_visible_rows",
    ]
