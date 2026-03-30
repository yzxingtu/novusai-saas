"""StreamExecutionHandler 真实流式行为测试 / Test."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub redis/socketio before app imports（不 stub bcrypt，以免污染 TestRealPasswordHash）
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

_mock_sio = MagicMock()
_mock_sio.emit = AsyncMock()
_sio_mod = types.ModuleType("app.core.socketio_server")
_sio_mod.get_sio = lambda: _mock_sio
_sio_mod.sio = _mock_sio  # emit_force_logout 等使用 sio 直接导入
sys.modules.setdefault("app.core.socketio_server", _sio_mod)

from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.middleware.trace import trace_id_var
from app.ai.engine.types import ToolUsePolicy


def _parse_sse_payload(raw: str) -> dict:
    """解析单条 SSE 文本（data: {...}\n\n）为 dict。 / Parse."""
    line = raw.strip()
    assert line.startswith("data: ")
    return json.loads(line[6:])


class _FakeSandbox:
    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict,
        definitions: list[ToolDefinition],
        conversation_id: int,
    ) -> ToolResult:
        _ = arguments, definitions, conversation_id
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            success=True,
            output='{"ok": true}',
        )


class _FakeEngine:
    """Fake engine: prefer real stream rounds, with ChatResponse fallback for legacy tests."""

    def __init__(
        self,
        rounds: list[list[ChatChunk]] | None = None,
        call_llm_responses: list[ChatResponse] | None = None,
    ):
        self.sandbox = _FakeSandbox()
        self._rounds = rounds or []
        self._call_llm_responses = call_llm_responses or []
        self._round_cursor = 0
        self._call_llm_cursor = 0

    async def _call_llm(self, **kwargs):
        _ = kwargs
        idx = (
            self._call_llm_cursor
            if self._call_llm_cursor < len(self._call_llm_responses)
            else len(self._call_llm_responses) - 1
        )
        self._call_llm_cursor += 1
        return self._call_llm_responses[idx]

    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        if self._rounds:
            idx = (
                self._round_cursor
                if self._round_cursor < len(self._rounds)
                else len(self._rounds) - 1
            )
            self._round_cursor += 1
            chunks = self._rounds[idx]
        elif self._call_llm_responses:
            idx = (
                self._round_cursor
                if self._round_cursor < len(self._call_llm_responses)
                else len(self._call_llm_responses) - 1
            )
            self._round_cursor += 1
            response = self._call_llm_responses[idx]
            chunks = [
                ChatChunk(
                    delta=response.message.content or "",
                    reasoning_delta=response.message.reasoning_content or "",
                    finish_reason=(
                        "tool_calls"
                        if (response.tool_calls or response.message.tool_calls)
                        else (response.finish_reason or "stop")
                    ),
                    total_tokens=response.total_tokens,
                    tool_calls=response.tool_calls or response.message.tool_calls,
                )
            ]
        else:
            chunks = []
        for chunk in chunks:
            yield chunk

    @staticmethod
    def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict]:
        return [asdict(m) for m in messages]

    @staticmethod
    def _log_web_research_contract_diagnostics(
        *,
        agent,
        messages,
        response,
        tools,
        continuation,
        conversation_id,
    ):
        from app.ai.engine.conversation import ConversationEngine

        engine = object.__new__(ConversationEngine)
        return ConversationEngine._log_web_research_contract_diagnostics(
            engine,
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            continuation=continuation,
            conversation_id=conversation_id,
        )

    @staticmethod
    def _log_tool_contract_diagnostics(
        *,
        agent,
        messages,
        response,
        tools,
        policy,
        conversation_id,
        breach_type,
        retry_result,
        continuation=None,
    ):
        from app.ai.engine.conversation import ConversationEngine

        engine = object.__new__(ConversationEngine)
        return ConversationEngine._log_tool_contract_diagnostics(
            engine,
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=policy,
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result=retry_result,
            continuation=continuation,
        )

    @staticmethod
    def _should_retry_tool_contract_breach(
        *,
        response,
        current_policy,
        tools,
        input_variables,
    ):
        from app.ai.engine.conversation import ConversationEngine

        return ConversationEngine._should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    @staticmethod
    def _should_retry_web_research_contract_breach(
        *,
        messages,
        response,
        current_policy,
        tools,
        input_variables,
        continuation,
    ):
        from app.ai.engine.conversation import ConversationEngine

        return ConversationEngine._should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
            continuation=continuation,
        )

    @staticmethod
    def _filter_tools_for_policy(tools, policy):
        from app.ai.engine.conversation import ConversationEngine

        return ConversationEngine._filter_tools_for_policy(tools, policy)

    @staticmethod
    def _needs_fetch_url_before_summary(messages):
        from app.ai.engine.base import BaseEngine

        return BaseEngine._needs_fetch_url_before_summary(messages)

    @staticmethod
    def _apply_fetch_url_only_gate(messages, tools, all_tools):
        from app.ai.engine.base import BaseEngine

        return BaseEngine._apply_fetch_url_only_gate(messages, tools, all_tools)


class _BrokenStreamEngine(_FakeEngine):
    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        raise RuntimeError("provider boom")
        yield  # pragma: no cover


def _build_handler(
    engine: _FakeEngine,
    tools: list[ToolDefinition] | None = None,
    continuation_context=None,
    tool_use_policy: ToolUsePolicy | None = None,
) -> StreamExecutionHandler:
    if tools is None:
        tools = [ToolDefinition(name="query_db", description="查询数据库")]
    request = SimpleNamespace(
        tenant_id=1,
        user_id=1,
        conversation_id=9001,
        messages=[ChatMessage(role="user", content="测试流式")],
        interaction_updates=None,
    )
    prep = SimpleNamespace(
        messages=[ChatMessage(role="user", content="测试流式")],
        tools=tools,
        all_tools=tools,
        continuation_context=continuation_context,
        tool_use_policy=tool_use_policy or ToolUsePolicy(),
        rag_sources=None,
        rag_source_kinds=[],
        context_compacted=False,
        memory_flush_triggered=False,
        memory_recalled=False,
        prune_stats=None,
        context_engine=None,
        optimize_event=None,
        tool_consent_modes={},
        route_result=None,
    )
    agent = SimpleNamespace(id=1)
    return StreamExecutionHandler(
        engine=engine,
        agent=agent,
        request=request,
        prep=prep,
        start_time=0.0,
        on_complete=None,
    )


@pytest.mark.asyncio
async def test_stream_handler_done_and_on_complete_when_llm_stream_stops_at_finish_reason():
    """finish_reason 出现后流结束须发 done，且 on_complete 成功（对齐 adapter 主动收口语义）。"""
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(delta="p"),
                ChatChunk(delta="art", finish_reason="stop", total_tokens=9),
            ],
        ],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.sleep(0)

    assert any(e.get("event") == "done" for e in events)
    assert "".join(e.get("delta", "") for e in events if e.get("event") == "message") == "part"
    assert len(captured) == 1
    assert captured[0].success is True
    assert captured[0].partial is False


@pytest.mark.asyncio
async def test_stream_handler_disconnect_after_done_still_runs_on_complete():
    """客户端在 done 后立刻断开时，后台 on_complete 仍应继续执行并持久化。"""
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        await asyncio.sleep(0)
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="完成", finish_reason="stop", total_tokens=3)]],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    agen = handler.generate()
    done_seen = False

    while True:
        raw = await agen.__anext__()
        if raw.strip().startswith("data: {"):
            payload = _parse_sse_payload(raw)
            if payload.get("event") == "done":
                done_seen = True
                break

    await agen.aclose()
    await asyncio.wait_for(completed.wait(), timeout=1)

    assert done_seen is True
    assert len(captured) == 1
    assert captured[0].success is True
    assert captured[0].output == "完成"


@pytest.mark.asyncio
async def test_stream_handler_error_event_includes_trace_id():
    handler = _build_handler(_BrokenStreamEngine())
    token = trace_id_var.set("trace-stream-error")
    try:
        events: list[dict] = []
        async for raw in handler.generate():
            if raw.strip().startswith("data: {"):
                events.append(_parse_sse_payload(raw))
    finally:
        trace_id_var.reset(token)

    error_event = next(event for event in events if event.get("error") is True)
    assert error_event["trace_id"] == "trace-stream-error"


@pytest.mark.asyncio
async def test_stream_handler_with_tools_keeps_real_delta_order():
    """有 tools 但本轮未触发 tool_call 时，仍保持真实逐块流式顺序。"""
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(delta="第"),
                ChatChunk(delta="一"),
                ChatChunk(delta="段", finish_reason="stop", total_tokens=12),
            ]
        ],
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_deltas = [e["delta"] for e in events if e.get("event") == "message"]
    assert "".join(message_deltas) == "第一段"
    assert any(e.get("event") == "done" for e in events)
    assert not any(e.get("event") == "thinking" for e in events)


@pytest.mark.asyncio
async def test_stream_handler_emits_conversation_event_early():
    """流开始时应先下发 conversation_id，便于前端在 done 前保留会话。"""
    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="第一段", finish_reason="stop", total_tokens=12)]],
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    assert events[0]["event"] == "conversation"
    assert events[0]["conversation_id"] == 9001


@pytest.mark.asyncio
async def test_stream_handler_emits_knowledge_base_feedback_event():
    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="完成", finish_reason="stop", total_tokens=3)]],
    )
    handler = _build_handler(engine)
    handler.request.knowledge_base_feedback = {
        "dropped_knowledge_base_ids": [12, 18],
        "effective_knowledge_base_ids": [5],
    }

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    kb_event = next(
        event
        for event in events
        if event.get("event") == "knowledge_base_feedback"
    )
    assert kb_event["dropped_knowledge_base_ids"] == [12, 18]
    assert kb_event["effective_knowledge_base_ids"] == [5]


@pytest.mark.asyncio
async def test_stream_handler_tool_rounds_keep_real_stream_and_final_answer():
    """
    工具轮次与最终回复都走真实流式；工具调用在流中增量聚合，最终答复继续流出。
    """
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(delta="", reasoning_delta="先"),
                ChatChunk(delta="", reasoning_delta="查询"),
                ChatChunk(
                    delta="数据库。",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "query_db",
                                "arguments": '{"sql":"SELECT 1"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=36,
                ),
            ],
            [
                ChatChunk(delta="查询完成"),
                ChatChunk(delta="。", finish_reason="stop", total_tokens=52),
            ],
        ],
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    assert any(e.get("event") == "thinking" for e in events)
    assert any(e.get("event") == "tool_start" and e.get("name") == "query_db" for e in events)
    assert any(e.get("event") == "tool_call" and e.get("success") is True for e in events)
    msg_deltas = [e["delta"] for e in events if e.get("event") == "message"]
    assert "查询完成" in "".join(msg_deltas) and "。" in "".join(msg_deltas)


@pytest.mark.asyncio
async def test_stream_handler_retries_summary_without_fetch_before_emitting_message():
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_search_1",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"sample topic public info","max_results":5}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=15,
                ),
            ],
            [
                ChatChunk(
                    delta="Here is a summary based only on the search snippets.",
                    finish_reason="stop",
                    total_tokens=20,
                ),
            ],
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_1",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://example.com/ukraine-live","max_length":4000}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=18,
                ),
            ],
            [
                ChatChunk(
                    delta="Based on the fetched page body.",
                    finish_reason="stop",
                    total_tokens=24,
                ),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
    ]
    continuation_context = SimpleNamespace(
        active=True,
        family="web_research",
        origin="continuation",
        current_user_text="Continue reviewing the same public webpages.",
        research_target_text="sample topic public info",
        recent_successful_tool_names=["web_search"],
        recent_web_queries=["sample topic public info"],
        search_query_count=1,
        fetched_url_count=0,
        research_instruction_texts=["Continue reviewing the same public webpages."],
    )
    handler = _build_handler(
        engine,
        tools=tools,
        continuation_context=continuation_context,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="active_continuation:web_research",
        ),
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "Here is a summary based only on the search snippets" not in message_text
    assert "Based on the fetched page body." in message_text
    assert any(
        event.get("event") == "tool_start" and event.get("name") == "fetch_url"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_retries_capability_denial_before_emitting_message() -> None:
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="我现在没有外部互联网搜索工具，只能基于已有知识回答。",
                    finish_reason="stop",
                    total_tokens=10,
                ),
            ],
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_search_retry",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"GPT 是什么","max_results":5}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=12,
                ),
            ],
            [
                ChatChunk(delta="GPT 是生成式预训练 Transformer。", finish_reason="stop", total_tokens=18),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="data_query", description="Query data"),
    ]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=[tool.name for tool in tools],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "没有外部互联网搜索工具" not in message_text
    assert "GPT 是生成式预训练 Transformer。" in message_text
    assert any(
        event.get("event") == "tool_start" and event.get("name") == "web_search"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_logs_failed_retry_when_required_policy_still_returns_text() -> None:
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="我现在没有外部互联网搜索工具，只能基于已有知识回答。",
                    finish_reason="stop",
                    total_tokens=10,
                ),
            ],
            [
                ChatChunk(
                    delta="仍然没有联网能力。",
                    finish_reason="stop",
                    total_tokens=12,
                ),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
    ]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=[tool.name for tool in tools],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
    )

    events: list[dict] = []
    with patch.object(_FakeEngine, "_log_tool_contract_diagnostics") as diag_mock:
        async for raw in handler.generate():
            if raw.strip().startswith("data: {"):
                events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "仍然没有联网能力。" in message_text
    assert diag_mock.call_count >= 2
    retry_results = [call.kwargs["retry_result"] for call in diag_mock.call_args_list]
    assert retry_results == ["retrying", "failed"]


@pytest.mark.asyncio
async def test_stream_handler_tool_round_persists_reasoning_content():
    """工具轮 assistant(tool_calls) 应保留 reasoning_content，供历史对话恢复思考块。"""
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="先查询数据库。",
                    tool_calls=[
                        {
                            "id": "call_reasoning_1",
                            "type": "function",
                            "function": {
                                "name": "query_db",
                                "arguments": '{"sql":"SELECT 1"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=36,
                ),
            ],
            [ChatChunk(delta="查询完成。", finish_reason="stop", total_tokens=52)],
        ],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    async for _ in handler.generate():
        pass

    await asyncio.sleep(0)

    assert len(captured) == 1
    assistant_tool_message = next(
        m for m in captured[0].messages if m.get("role") == "assistant" and m.get("tool_calls")
    )
    assert assistant_tool_message.get("content") == "先查询数据库。"
    assert assistant_tool_message.get("reasoning_content") == "先查询数据库。"


@pytest.mark.asyncio
async def test_stream_handler_consent_round_does_not_append_duplicate_assistant():
    """consent ask round 只保留 assistant(tool_calls) 一次，不再额外追加重复 plain assistant。"""
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="请先确认后再执行。",
                    tool_calls=[
                        {
                            "id": "call_ask_1",
                            "type": "function",
                            "function": {
                                "name": "query_db",
                                "arguments": '{"sql":"SELECT 1"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=20,
                ),
            ]
        ],
    )
    handler = _build_handler(engine)
    handler.prep.tool_consent_modes = {"query_db": "ask"}
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.sleep(0)

    assert "".join(
        e.get("delta", "") for e in events if e.get("event") == "message"
    ) == "请先确认后再执行。"
    assert len(captured) == 1
    assistant_messages = [
        m for m in captured[0].messages if m.get("role") == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0].get("tool_calls")


@pytest.mark.asyncio
async def test_tool_call_name_matches_tool_start_when_sandbox_redirects():
    """
    When sandbox redirects pageop_* to invoke_page_operation, tool_call event
    must use original func_name (name_override) so frontend matches correctly.
    pageop_* 重定向后 tool_call 事件的 name 必须与 tool_start 一致（原始 func_name）。
    """
    class _RedirectSandbox:
        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list,
            conversation_id: int,
        ):
            _ = tool_call_id, arguments, definitions, conversation_id
            # Simulate sandbox redirect: pageop_* -> invoke_page_operation
            result_name = "invoke_page_operation" if name.startswith("pageop_") else name
            return ToolResult(
                tool_call_id="call_1",
                name=result_name,
                success=True,
                output='{"ok": true}',
            )

    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "pageop_get_editor_html",
                            "arguments": '{"page_key":"test"}',
                        },
                    },
                ],
                total_tokens=50,
            ),
            ChatResponse(
                message=ChatMessage(role="assistant", content="Done"),
                tool_calls=None,
                total_tokens=60,
            ),
        ],
    )
    engine.sandbox = _RedirectSandbox()
    tools = [
        ToolDefinition(name="pageop_get_editor_html", description="Get editor HTML"),
    ]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    tool_starts = [e for e in events if e.get("event") == "tool_start"]
    tool_calls = [e for e in events if e.get("event") == "tool_call" and e.get("success")]
    assert len(tool_starts) >= 1
    assert len(tool_calls) >= 1
    assert tool_starts[0].get("name") == "pageop_get_editor_html"
    assert tool_calls[0].get("name") == "pageop_get_editor_html", (
        "tool_call name must match tool_start (name_override) when sandbox redirects"
    )


@pytest.mark.asyncio
async def test_tool_call_event_includes_summary_payload():
    class _SummarySandbox:
        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list,
            conversation_id: int,
        ):
            _ = arguments, definitions, conversation_id
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output='{"ok": true}',
                summary="按今天范围统计调用并按租户分组",
                summary_payload={
                    "tool_kind": "data_query",
                    "tables": ["ai_call_logs", "tenants"],
                    "metrics": ["COUNT(acl.id)"],
                    "filters": ["today"],
                },
            )

    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "call_summary_1",
                        "type": "function",
                        "function": {
                            "name": "data_query",
                            "arguments": '{"question":"统计今天调用情况"}',
                        },
                    },
                ],
                total_tokens=40,
            ),
            ChatResponse(
                message=ChatMessage(role="assistant", content="Done"),
                tool_calls=None,
                total_tokens=60,
            ),
        ],
    )
    engine.sandbox = _SummarySandbox()
    tools = [ToolDefinition(name="data_query", description="Query data")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    tool_call_event = next(
        event
        for event in events
        if event.get("event") == "tool_call" and event.get("name") == "data_query"
    )
    assert tool_call_event.get("summary") == "按今天范围统计调用并按租户分组"
    assert tool_call_event.get("summary_payload") == {
        "tool_kind": "data_query",
        "tables": ["ai_call_logs", "tenants"],
        "metrics": ["COUNT(acl.id)"],
        "filters": ["today"],
    }


@pytest.mark.asyncio
async def test_parse_error_abort_after_consecutive_page_op_failures():
    """
    parse error 连续 3 次后触发熔断，停止工具循环并输出恢复提示。
    验证富文本审计方案：parse error 分支纳入熔断计数。
    """
    # 3 个 invoke_page_operation 调用，每个 arguments 为非法 JSON
    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {"id": "c1", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 1"}},
                    {"id": "c2", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 2"}},
                    {"id": "c3", "type": "function", "function": {"name": "invoke_page_operation", "arguments": "{bad json 3"}},
                ],
                total_tokens=100,
            ),
        ],
    )
    tools = [ToolDefinition(name="invoke_page_operation", description="Execute page op")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    # 应有 3 个 tool_call 失败事件
    failed_calls = [e for e in events if e.get("event") == "tool_call" and e.get("success") is False]
    assert len(failed_calls) >= 3

    # 熔断后 output 应包含恢复提示（兼容 i18n key 或翻译结果）
    output = handler._output or ""
    assert "multiple_failures" in output or "Multiple" in output or "失败" in output


@pytest.mark.asyncio
async def test_interrupted_calls_on_complete_with_partial_result():
    """
    中断（CancelledError）时 on_complete 应收到带 messages/output/tool_results 的 partial ExecutionResult。
    """
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)

    class _RaisingEngine(_FakeEngine):
        async def _stream_llm_chunks(self, **kwargs):
            _ = kwargs
            yield ChatChunk(delta="部")
            raise asyncio.CancelledError("simulated cancel")

    engine = _RaisingEngine(
        call_llm_responses=[],  # unused, we raise before
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    with pytest.raises(asyncio.CancelledError):
        async for _ in handler.generate():
            pass

    if handler._background_tasks:
        await asyncio.wait_for(
            asyncio.gather(*list(handler._background_tasks)),
            timeout=1,
        )

    assert len(captured) == 1
    r = captured[0]
    assert r.partial is True
    assert r.interrupted is True
    assert r.completion_reason == "interrupted"
    assert r.success is False
    assert r.output == "部"
    # Should have messages (prep.messages passed through)
    assert r.messages is not None
