"""
Test type: behavioral
Scope: ConversationEngine exception passthrough, retry policy, and web research repair.
Mocked dependencies: Redis module import seam and LLM adapter calls via focused AsyncMock.
"""

# Redis import stubs must be installed before importing app modules under test.
# ruff: noqa: E402

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
    def from_url(cls, *_args, **_kwargs):
        return cls()

    async def aclose(self) -> None:
        return None


class _RedisClient:
    def __init__(self, *_args, **_kwargs) -> None:
        return None


class _RedisPipeline:
    pass


redis_exceptions_module.RedisError = type("RedisError", (Exception,), {})
redis_asyncio_module.ConnectionPool = _RedisConnectionPool
redis_asyncio_module.Redis = _RedisClient
redis_asyncio_client_module.Pipeline = _RedisPipeline
redis_module.Redis = _RedisClient
redis_module.from_url = lambda *_args, **_kwargs: MagicMock()
redis_module.asyncio = redis_asyncio_module
redis_module.exceptions = redis_exceptions_module
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.asyncio", redis_asyncio_module)
sys.modules.setdefault("redis.asyncio.client", redis_asyncio_client_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

from app.ai.engine import conversation_sync_io_adapter as sync_io_adapter
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.turn_executor import ToolBatchResult
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
async def test_conversation_engine_execute_hides_generic_exception_in_production() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    assert result.error == "服务器内部错误 [trace_id=trace-conversation-prod]"
    assert result.diagnostics is not None


@pytest.mark.asyncio
async def test_conversation_engine_retries_capability_denial_with_required_tool_policy(
    monkeypatch,
) -> None:
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        side_effect=[
            ToolResult(
                tool_call_id="call_search",
                name="web_search",
                success=True,
                output="GPT background from web search",
                summary_payload={
                    "result_count": 1,
                    "items": [
                        {
                            "title": "GPT overview",
                            "url": "https://example.com/gpt",
                            "snippet": "GPT background from web search",
                        }
                    ],
                },
            ),
            ToolResult(
                tool_call_id="call_fetch",
                name="fetch_url",
                success=True,
                output="Content from https://example.com/gpt\n\nGPT background from web search",
                summary_payload={
                    "fetch_url": True,
                    "title": "GPT overview",
                    "description": "GPT background from web search",
                    "summary": "GPT background from web search",
                },
            ),
        ]
    )
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=sandbox)
    prep = PreparedExecution(
        messages=[
            ChatMessage(role="user", content="联网帮我查一下 gpt 到底是什么东西")
        ],
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
            max_tool_rounds=3,
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
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_fetch",
                        "type": "function",
                        "function": {
                            "name": "fetch_url",
                            "arguments": '{"url":"https://example.com/gpt","max_length":4000}',
                        },
                    }
                ],
                total_tokens=8,
            ),
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="GPT 是生成式预训练 Transformer。",
                ),
                total_tokens=20,
            ),
        ]
    )

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="联网帮我查一下 gpt 到底是什么东西")
        ],
        input_variables={},
    )
    agent = SimpleNamespace(id=1)

    result = await engine.execute(agent, request)

    assert result.success is True
    assert result.partial is False
    assert "GPT background from web search" in result.output
    assert len(engine._call_llm.await_args_list) == 2
    assert engine._call_llm.await_args_list[0].kwargs["tool_use_policy"].mode == "auto"
    assert (
        engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].mode == "required"
    )
    assert (
        engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].family
        == "web_research"
    )
    assert [
        tool.name for tool in engine._call_llm.await_args_list[1].kwargs["tools"]
    ] == [
        "web_search",
        "fetch_url",
    ]


@pytest.mark.asyncio
async def test_conversation_engine_retries_summary_without_fetch_with_fetch_url() -> (
    None
):
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        side_effect=[
            ToolResult(
                tool_call_id="call_search",
                name="web_search",
                success=True,
                output="Search results for: 乌克兰 局势 今天 最新 官方 新闻",
                summary_payload={
                    "result_count": 1,
                    "items": [
                        {
                            "title": "Ukraine live updates",
                            "url": "https://example.com/ukraine-live",
                            "snippet": "Search results for Ukraine live updates",
                        }
                    ],
                },
            ),
            ToolResult(
                tool_call_id="call_fetch",
                name="fetch_url",
                success=True,
                output="Content from https://example.com/ukraine-live:\n\n正文内容",
                summary_payload={
                    "fetch_url": True,
                    "title": "Ukraine live updates",
                    "description": "正文内容",
                    "summary": "正文内容",
                },
            ),
        ]
    )
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=sandbox)
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
        intent_plan=[
            IntentPlan(
                intent_id="intent-web-research",
                kind="web_research",
                family="web_research",
                order=1,
                user_visible_label="web_research",
                source_text="联网查阅一下，今天乌克兰的局势",
                allowed_tool_names=["web_search", "fetch_url"],
                preferred_tool_names=["web_search", "fetch_url"],
                completion_signals=["fetch_url"],
            )
        ],
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
    engine._call_llm = AsyncMock(
        side_effect=[
            first_response,
            retry_response,
            ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="基于正文，今天乌克兰局势仍然处于持续对抗状态。",
                ),
                total_tokens=15,
            ),
        ]
    )

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
    assert result.output == "正文内容"
    assert len(engine._call_llm.await_args_list) == 1
    assert engine._call_llm.await_args_list[0].kwargs["tool_use_policy"].mode == (
        "required"
    )
    assert [
        tool.name for tool in engine._call_llm.await_args_list[0].kwargs["tools"]
    ] == [
        "web_search",
        "fetch_url",
    ]


@pytest.mark.asyncio
async def test_conversation_engine_repairs_title_only_answer_after_fetch(
    monkeypatch,
) -> None:
    page_title = "湖南中小学将施行春秋假制度-湖南省人民政府门户网站"
    sandbox = MagicMock()
    sandbox.execute = AsyncMock(
        side_effect=[
            ToolResult(
                tool_call_id="call_search",
                name="web_search",
                success=True,
                output="Search results for: 湖南学生放假时间",
                summary_payload={
                    "result_count": 1,
                    "items": [
                        {
                            "title": page_title,
                            "url": "https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/t20260328_33943174.html",
                            "snippet": "湖南中小学生即将迎来春秋假。",
                        }
                    ],
                },
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
                summary_payload={
                    "fetch_url": True,
                    "title": page_title,
                    "description": "湖南中小学生即将迎来春秋假。",
                    "summary": "湖南中小学生即将迎来春秋假。",
                },
            ),
        ]
    )
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=sandbox)
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
        intent_plan=[
            IntentPlan(
                intent_id="intent-web-research",
                kind="web_research",
                family="web_research",
                order=1,
                user_visible_label="web_research",
                source_text="你联网查一下 湖南学生放假时间",
                allowed_tool_names=["web_search", "fetch_url"],
                preferred_tool_names=["web_search", "fetch_url"],
                completion_signals=["fetch_url"],
            )
        ],
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
        side_effect=[
            first_response,
            retry_fetch_response,
            repaired_response,
        ]
    )

    async def _fake_sync_tool_calls(*, messages, response, **kwargs):
        _ = kwargs
        tool_calls = list(response.tool_calls or response.message.tool_calls or [])
        tool_calls[0]["success"] = True
        messages.append(
            ChatMessage(
                role="assistant",
                content=response.message.content or "",
                tool_calls=tool_calls,
            )
        )
        tool_name = str(tool_calls[0]["function"]["name"])
        if tool_name == "web_search":
            result = ToolResult(
                tool_call_id="call_search",
                name="web_search",
                success=True,
                output="Search results for: 湖南学生放假时间",
                summary_payload={
                    "result_count": 1,
                    "items": [
                        {
                            "title": page_title,
                            "url": "https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/t20260328_33943174.html",
                            "snippet": "湖南中小学生即将迎来春秋假。",
                        }
                    ],
                },
            )
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result.output or "",
                    tool_call_id=result.tool_call_id,
                )
            )
            return ToolBatchResult(
                response=None,
                tool_results=[result],
                total_tokens=18,
                completion_tokens_used=18,
            )
        result = ToolResult(
            tool_call_id="call_fetch",
            name="fetch_url",
            success=True,
            output=(
                "Content from https://searchs.hunan.gov.cn/hnszf/hnyw/zwdt/202603/"
                "t20260328_33943174.html\n"
                f"Title: {page_title}\n"
                "湖南中小学生即将迎来春秋假。"
            ),
            summary_payload={
                "fetch_url": True,
                "title": page_title,
                "description": "湖南中小学生即将迎来春秋假。",
                "summary": "湖南中小学生即将迎来春秋假。",
            },
        )
        messages.append(
            ChatMessage(
                role="tool",
                content=result.output or "",
                tool_call_id=result.tool_call_id,
            )
        )
        return ToolBatchResult(
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=page_title),
                total_tokens=11,
            ),
            tool_results=[result],
            total_tokens=29,
            completion_tokens_used=29,
        )

    monkeypatch.setattr(
        sync_io_adapter,
        "handle_sync_tool_calls",
        _fake_sync_tool_calls,
    )

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
    assert "湖南中小学生即将迎来春秋假" in result.output
    assert result.output != page_title
    assert len(engine._call_llm.await_args_list) == 1
    assert result.turn_record["final_output_source"] == "recovery_evidence"


@pytest.mark.asyncio
async def test_conversation_engine_execute_calls_context_engine_after_turn() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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


def test_contract_breach_retry_uses_semantic_capability_terms_for_custom_web_tool() -> (
    None
):
    tools = [
        ToolDefinition(
            name="external_lookup",
            description="Research external public sources",
            semantic_family="web_research",
            semantic_tags=["联网搜索", "网页查询", "最新信息", "官方来源"],
        ),
    ]

    should_retry, retry_policy, response_text = (
        ConversationEngine._should_retry_tool_contract_breach(
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
    )

    assert should_retry is True
    assert response_text == "我现在不能联网搜索公开网页，只能基于已有知识回答。"
    assert retry_policy is not None
    assert retry_policy.family == "web_research"
    assert retry_policy.mode == "required"
    assert retry_policy.allowed_tool_names == ["external_lookup"]


def test_conversation_engine_detects_capability_denial_from_semantic_family_terms() -> (
    None
):
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


def test_web_research_contract_retry_does_not_override_explicit_weather_policy() -> (
    None
):
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


def test_analyze_post_tool_contract_breach_accepts_native_web_search_weather_answer() -> (
    None
):
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
    ]
    messages = [ChatMessage(role="user", content="今天怀化天气怎么样 联网查查")]
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="今天怀化白天多云，最高气温 27°C，夜间有阵雨概率。",
        ),
        raw_response={
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "今天怀化白天多云，最高气温 27°C，夜间有阵雨概率。",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://www.weather.com/zh-CN/weather/today/l/CHXX0036:1:CH",
                                    "title": "weather.com",
                                }
                            ],
                        }
                    ],
                },
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "url": "https://www.weather.com/zh-CN/weather/today/l/CHXX0036:1:CH"
                            }
                        ]
                    },
                },
            ]
        },
    )

    breach_type, retry_policy, diagnostics = (
        ConversationEngine._analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=ToolUsePolicy(
                family="web_research",
                mode="required",
                allowed_tool_names=["web_search", "fetch_url"],
                retry_on_contract_breach=False,
                reason="explicit_web_request",
            ),
            tools=tools,
            input_variables={},
        )
    )

    assert breach_type is None
    assert retry_policy is None
    assert diagnostics["native_web_search_evidence"] is True
    assert diagnostics["completed_intents"] == ["weather"]
    assert diagnostics["unfinished_intents"] == []


def test_analyze_post_tool_contract_breach_accepts_native_web_research_answer() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
    ]
    messages = [ChatMessage(role="user", content="联网查一下今天的开源模型发布")]
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="今天有多个开源模型发布动态，其中 Example AI 发布了新模型。",
        ),
        raw_response={
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [{"url": "https://example.com/open-model-release"}]
                    },
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "今天有多个开源模型发布动态。",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/open-model-release",
                                    "title": "Example AI",
                                }
                            ],
                        }
                    ],
                },
            ]
        },
    )

    breach_type, retry_policy, diagnostics = (
        ConversationEngine._analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=ToolUsePolicy(
                family="web_research",
                mode="required",
                allowed_tool_names=["web_search", "fetch_url"],
                retry_on_contract_breach=False,
                reason="web_research:builtin_pipeline",
            ),
            tools=tools,
            input_variables={},
        )
    )

    assert breach_type is None
    assert retry_policy is None
    assert diagnostics["native_web_search_evidence"] is True
    assert diagnostics["completed_intents"] == ["web_research"]
    assert diagnostics["unfinished_intents"] == []
