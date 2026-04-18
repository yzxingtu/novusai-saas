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

_mock_sio = MagicMock()
_mock_sio.emit = AsyncMock()
_sio_mod = types.ModuleType("app.core.socketio_server")
_sio_mod.get_sio = lambda: _mock_sio
_sio_mod.sio = _mock_sio  # emit_force_logout 等使用 sio 直接导入
sys.modules.setdefault("app.core.socketio_server", _sio_mod)

from app.ai.engine.budget_guard import BudgetGuard  # noqa: E402
from app.ai.engine.stream_handler import (  # noqa: E402
    StreamExecutionHandler,
    StreamIOAdapter,
)
from app.ai.engine.turn_executor import TurnExecutionResult  # noqa: E402
from app.ai.engine.types import IntentPlan, ToolUsePolicy  # noqa: E402
from app.ai.exceptions import ProviderTimeoutError  # noqa: E402
from app.ai.tools.types import ToolDefinition, ToolResult  # noqa: E402
from app.ai.types import ChatChunk, ChatMessage, ChatResponse  # noqa: E402
from app.middleware.trace import trace_id_var  # noqa: E402


def _parse_sse_payload(raw: str) -> dict:
    """解析单条 SSE 文本（data: {...}\n\n）为 dict。 / Parse."""
    line = raw.strip()
    assert line.startswith("data: ")
    return json.loads(line[6:])


class _FakeSandbox:
    def __init__(self) -> None:
        self.runtime_model_info: dict | None = None
        self.executed_runtime_model_info: dict | None = None

    def set_runtime_model_info(self, runtime_model_info: dict | None) -> None:
        self.runtime_model_info = dict(runtime_model_info or {})

    async def execute(
        self,
        tool_call_id: str,
        name: str,
        arguments: dict,
        definitions: list[ToolDefinition],
        conversation_id: int,
    ) -> ToolResult:
        _ = arguments, definitions, conversation_id
        self.executed_runtime_model_info = dict(self.runtime_model_info or {})
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
    def _analyze_post_tool_contract_breach(
        *,
        messages,
        response,
        current_policy,
        tools,
        input_variables,
    ):
        from app.ai.engine.conversation import ConversationEngine

        return ConversationEngine._analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    @staticmethod
    def _build_contract_recovery_system_message(*, breach_type, diagnostics):
        from app.ai.engine.base import BaseEngine

        return BaseEngine._build_contract_recovery_system_message(
            breach_type=breach_type,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _merge_contract_diagnostics_into_turn_record(
        turn_record,
        *,
        breach_type,
        diagnostics,
        recovered_via_retry,
    ):
        from app.ai.engine.base import BaseEngine

        return BaseEngine._merge_contract_diagnostics_into_turn_record(
            turn_record,
            breach_type=breach_type,
            diagnostics=diagnostics,
            recovered_via_retry=recovered_via_retry,
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


class _RecordingStreamEngine(_FakeEngine):
    def __init__(self, rounds: list[list[ChatChunk]]) -> None:
        super().__init__(rounds=rounds)
        self.stream_call_kwargs: list[dict[str, object]] = []

    async def _stream_llm_chunks(self, **kwargs):
        self.stream_call_kwargs.append(dict(kwargs))
        async for chunk in super()._stream_llm_chunks(**kwargs):
            yield chunk


class _BrokenStreamEngine(_FakeEngine):
    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        raise RuntimeError("provider boom")
        yield  # pragma: no cover


class _BrokenProviderTimeoutEngine(_FakeEngine):
    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        exc = ProviderTimeoutError(message="Request timed out.")
        exc._novusai_runtime_turn_record = {
            "turn_outcome": "failed",
            "termination_reason": "error",
            "protocol_path": "responses",
            "metadata": {
                "protocol_fallback_blocked_reason": "provider_timeout",
                "stream_failure_chunk_count": 0,
                "stream_failure_has_meaningful_chunk": False,
                "stream_failure_error_type": "ProviderTimeoutError",
            },
        }
        exc._novusai_runtime_model_info = {
            "provider_id": 10,
            "provider_name": "响应云",
            "model_id": 9,
            "model_name": "gpt-5.4",
        }
        exc._novusai_runtime_protocol_path = "responses"
        raise exc
        yield  # pragma: no cover


class _BlockingThinkingStreamEngine(_FakeEngine):
    def __init__(self) -> None:
        super().__init__(rounds=[])
        self._round = 0
        self.allow_tool_finish = asyncio.Event()

    async def _stream_llm_chunks(self, **kwargs):
        _ = kwargs
        if self._round == 0:
            self._round += 1
            yield ChatChunk(delta="", reasoning_delta="先")
            await self.allow_tool_finish.wait()
            yield ChatChunk(
                delta="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "query_db",
                            "arguments": '{"sql":"SELECT 1"}',
                        },
                    }
                ],
                finish_reason="tool_calls",
                total_tokens=12,
            )
            return

        self._round += 1
        yield ChatChunk(delta="完成", finish_reason="stop", total_tokens=20)


def _build_handler(
    engine: _FakeEngine,
    tools: list[ToolDefinition] | None = None,
    continuation_context=None,
    tool_use_policy: ToolUsePolicy | None = None,
    intent_plan: list[IntentPlan] | None = None,
) -> StreamExecutionHandler:
    if tools is None:
        tools = [ToolDefinition(name="query_db", description="查询数据库")]
    effective_intent_plan = list(intent_plan or [])
    execution_budget = (
        BudgetGuard.build_default("normal", intent_count=len(effective_intent_plan))
        if effective_intent_plan
        else None
    )
    request = SimpleNamespace(
        tenant_id=1,
        user_id=1,
        conversation_id=9001,
        messages=[ChatMessage(role="user", content="测试流式")],
        input_variables={},
        interaction_updates=None,
    )
    prep = SimpleNamespace(
        messages=[ChatMessage(role="user", content="测试流式")],
        tools=tools,
        all_tools=tools,
        continuation_context=continuation_context,
        tool_use_policy=tool_use_policy or ToolUsePolicy(),
        intent_plan=effective_intent_plan,
        execution_budget=execution_budget,
        execution_path="normal" if effective_intent_plan else None,
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
async def test_prepare_stream_runtime_forwards_skip_metering_preflight() -> None:
    from app.ai.engine.conversation import ConversationEngine

    captured: dict[str, object] = {}

    class _Preflight:
        async def prepare(
            self,
            *,
            agent,
            messages,
            tenant_id,
            route_result=None,
            skip_metering_preflight=False,
        ):
            _ = agent, messages, tenant_id, route_result
            captured["skip_metering_preflight"] = skip_metering_preflight
            provider = SimpleNamespace(code="mock-provider", type="mock")
            return SimpleNamespace(
                provider=provider,
                model_code="mock-model",
                runtime_info={},
            )

    engine = ConversationEngine(
        db=SimpleNamespace(),
        gateway=SimpleNamespace(),
        sandbox=None,
    )
    engine._runtime_preflight = lambda: _Preflight()

    await engine._prepare_stream_runtime(
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        route_result=None,
        skip_metering_preflight=True,
    )

    assert captured["skip_metering_preflight"] is True


@pytest.mark.asyncio
async def test_stream_io_adapter_keeps_finalized_completed_output_over_stream_preview():
    handler = _build_handler(_FakeEngine())
    handler._output = "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网"
    adapter = StreamIOAdapter(handler)

    handler.runtime_contract.finalize_completed_output = AsyncMock(
        return_value=("根据已获取网页内容，长沙义务教育阶段学校今年暑假从7月6日开始。", 18, 18)
    )
    output, total_tokens, completion_tokens_used = (
        await adapter.finalize_completed_output(
            messages=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=18,
                output_tokens=18,
            ),
            state=handler._state,
            tool_results=[],
            reason="completed",
            total_tokens=18,
            completion_tokens_used=18,
        )
    )
    assert "长沙义务教育阶段学校今年暑假从7月6日开始" in output
    assert "特殊教育学校_新浪财经_新浪网" not in output
    assert total_tokens == 18
    assert completion_tokens_used == 18


@pytest.mark.asyncio
async def test_stream_io_adapter_keeps_finalized_partial_output_over_stream_preview():
    handler = _build_handler(_FakeEngine())
    handler._output = "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网"
    adapter = StreamIOAdapter(handler)

    handler.runtime_contract.finalize_partial_output = AsyncMock(
        return_value=("我先把目前能确认的内容给你：长沙义务教育阶段学校今年暑假从7月6日开始。", 18, 18)
    )
    output, total_tokens, completion_tokens_used = (
        await adapter.finalize_partial_output(
            messages=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=18,
                output_tokens=18,
            ),
            state=handler._state,
            tool_results=[],
            reason="completion_budget_exceeded",
            total_tokens=18,
            completion_tokens_used=18,
        )
    )
    assert "长沙义务教育阶段学校今年暑假从7月6日开始" in output
    assert "特殊教育学校_新浪财经_新浪网" not in output
    assert total_tokens == 18
    assert completion_tokens_used == 18


@pytest.mark.asyncio
async def test_stream_handler_syncs_runtime_model_info_to_sandbox_before_tool_calls() -> None:
    runtime_model_info = {
        "provider_id": 11,
        "provider_name": "OpenAI",
        "model_id": 22,
        "model_name": "GPT-5.4",
        "model_code": "gpt-5.4",
    }
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
                                "arguments": '{"query":"runtime v2 rollout","max_results":5}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=12,
                    metadata={"runtime_model_info": runtime_model_info},
                )
            ],
            [
                ChatChunk(
                    delta="done",
                    finish_reason="stop",
                    total_tokens=18,
                    metadata={"runtime_model_info": runtime_model_info},
                )
            ],
        ]
    )
    handler = _build_handler(
        engine,
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search"],
        ),
    )

    async for _raw in handler.generate():
        pass

    assert engine.sandbox.executed_runtime_model_info == runtime_model_info


@pytest.mark.asyncio
async def test_stream_handler_emits_web_search_progress_status_before_message() -> None:
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    metadata={"web_search_in_progress": True},
                ),
                ChatChunk(
                    delta="查好了",
                    finish_reason="stop",
                    total_tokens=8,
                ),
            ]
        ]
    )
    handler = _build_handler(
        engine,
        tools=[ToolDefinition(name="web_search", description="Search the web")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search"],
        ),
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    status_idx = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "status"
        and event.get("status") == "web_search_in_progress"
    )
    message_idx = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "message" and event.get("delta") == "查好了"
    )
    done_idx = next(
        index for index, event in enumerate(events) if event.get("event") == "done"
    )

    assert status_idx < message_idx < done_idx


@pytest.mark.asyncio
async def test_stream_handler_refreshes_runtime_turn_record_before_done() -> None:
    turn_record = SimpleNamespace(
        turn_outcome="executing",
        termination_reason="pending",
        protocol_path="responses",
        selected_tool_names=[],
        selected_skill_names=[],
        context_sources=[],
        fallback_history=[],
        provider_events=[],
        metadata={},
    )

    class _MutableTurnRecordEngine(_FakeEngine):
        async def _stream_llm_chunks(self, **kwargs):
            _ = kwargs
            yield ChatChunk(
                delta="完成",
                finish_reason="stop",
                total_tokens=6,
                metadata={"runtime_turn_record": turn_record},
            )
            turn_record.turn_outcome = "success"
            turn_record.termination_reason = "completed"
            turn_record.metadata = {"stream_progress_event_count": 1}

    handler = _build_handler(_MutableTurnRecordEngine())

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    done_event = next(event for event in events if event.get("event") == "done")
    assert done_event["turn_record"]["turn_outcome"] == "success"
    assert done_event["turn_record"]["termination_reason"] == "completed"


def _build_pending_intent(
    *,
    allowed_tool_names: list[str],
    family: str,
    source_text: str = "测试流式",
) -> IntentPlan:
    return IntentPlan(
        intent_id="intent_1",
        kind="tool_use",
        family=family,
        order=0,
        user_visible_label=source_text,
        source_text=source_text,
        allowed_tool_names=list(allowed_tool_names),
        completion_signals=list(allowed_tool_names),
    )


def _assert_retry_clear_sequence(
    events: list[dict],
    *,
    leaked_text: str,
    final_text: str,
) -> None:
    clear_events = [event for event in events if event.get("event") == "clear_content"]
    assert clear_events

    first_message_idx = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "message"
        and leaked_text in str(event.get("delta", ""))
    )
    first_clear_idx = events.index(clear_events[0])
    final_message_idx = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "message" and final_text in str(event.get("delta", ""))
    )

    assert first_message_idx < first_clear_idx < final_message_idx


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
    assert (
        "".join(e.get("delta", "") for e in events if e.get("event") == "message")
        == "part"
    )
    assert len(captured) == 1
    assert captured[0].success is True
    assert captured[0].partial is False


@pytest.mark.asyncio
async def test_stream_handler_done_event_merges_on_complete_extra_fields() -> None:
    async def on_complete(_result) -> dict[str, object]:
        await asyncio.sleep(0)
        return {
            "memory_updated": True,
            "persistence_committed": True,
        }

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(delta="part", finish_reason="stop", total_tokens=9),
            ],
        ],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    done_event = next(event for event in events if event.get("event") == "done")
    assert done_event["memory_updated"] is True
    assert done_event["persistence_committed"] is True


@pytest.mark.asyncio
async def test_stream_handler_waits_for_on_complete_before_done() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    events: list[dict] = []

    async def on_complete(_result) -> None:
        started.set()
        await release.wait()

    async def _collect(handler: StreamExecutionHandler) -> None:
        async for raw in handler.generate():
            if raw.strip().startswith("data: {"):
                events.append(_parse_sse_payload(raw))

    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="完成", finish_reason="stop", total_tokens=3)]],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    task = asyncio.create_task(_collect(handler))

    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    assert not any(event.get("event") == "done" for event in events)

    release.set()
    await asyncio.wait_for(task, timeout=1)

    assert any(event.get("event") == "done" for event in events)


@pytest.mark.asyncio
async def test_stream_handler_done_event_includes_turn_record_fields() -> None:
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="你好，我已经处理好了。",
                    finish_reason="stop",
                    total_tokens=12,
                )
            ],
        ],
    )
    handler = _build_handler(engine)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    done_event = next(event for event in events if event.get("event") == "done")
    assert isinstance(done_event.get("turn_record"), dict)
    assert done_event.get("termination_reason") == "completed"
    assert done_event.get("protocol_path") in {"chat_completions", "responses"}


@pytest.mark.asyncio
async def test_stream_handler_preserves_runtime_protocol_for_zero_chunk_provider_timeout() -> None:
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    handler = _build_handler(_BrokenProviderTimeoutEngine())
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    result = captured[0]
    assert result.turn_record["protocol_path"] == "responses"
    assert result.turn_record["failure_kind"] == "provider_timeout"
    assert result.turn_record["conversation_outcome"] == "failed"
    assert result.provider_failure_kind == "provider_timeout"
    assert not any(event.get("error") is True for event in events)
    assert any(event.get("event") == "done" for event in events)
    fallback_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert fallback_text


@pytest.mark.asyncio
async def test_stream_handler_budget_exit_after_tool_round_still_emits_final_message():
    """预算退出在工具轮后仍要保留最终 assistant 文本输出。"""
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="Final summary after the tool call.",
                    tool_calls=[
                        {
                            "id": "call_tool_1",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"budget exit"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=20,
                ),
            ],
        ],
    )
    tools = [ToolDefinition(name="web_search", description="Search the web")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    with patch(
        "app.ai.engine.budget_guard.BudgetGuard.completion_reason",
        return_value="elapsed_budget_exceeded",
    ):
        async for raw in handler.generate():
            if raw.strip().startswith("data: {"):
                events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "Final summary after the tool call." in message_text


@pytest.mark.asyncio
async def test_stream_handler_budget_exit_after_successful_tool_uses_generic_partial_reply():
    """工具已成功执行但预算提前退出时，仅保留普通 partial 提示。"""
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_page_context_1",
                            "type": "function",
                            "function": {
                                "name": "ui_get_snapshot",
                                "arguments": "{}",
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=12,
                ),
            ],
        ],
    )
    tools = [ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot")]
    handler = _build_handler(engine, tools=tools)
    handler.on_complete = on_complete
    handler.request.input_variables = {
        "page_context": {
            "page_key": "tenant.dashboard",
            "page_title": "仪表盘",
            "ui_epoch": 2,
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_read_region"],
            },
        }
    }
    handler._state.budget_exit_reason = MagicMock(
        side_effect=[None, "elapsed_budget_exceeded", "elapsed_budget_exceeded"]
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    await asyncio.sleep(0)
    assert message_text
    assert len(captured) == 1
    assert captured[0].partial is True
    assert captured[0].diagnostics["final_output_source"] == "budget_fallback"
    persisted_assistants = [
        message
        for message in captured[0].messages
        if message.get("role") == "assistant" and (message.get("content") or "").strip()
    ]
    assert persisted_assistants
    assert persisted_assistants[-1].get("content", "").strip() == captured[0].output


@pytest.mark.asyncio
async def test_stream_handler_promotes_budgeted_web_research_tool_evidence_to_completed():
    from app.ai.engine.types import ExecutionResult, RecoveryDecision

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_budgeted",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://finance.sina.com.cn/jjxw/2025-06-12/doc-inezupah3848475.shtml","max_length":12000}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=10,
                ),
            ],
            # synthesis round after budget-exceeded tool completion
            [
                ChatChunk(
                    delta="根据查询结果，湖南12地已公布2025年中小学暑假放假时间，今年暑假从7月6日开始。",
                    finish_reason="stop",
                    total_tokens=50,
                ),
            ],
        ],
    )
    engine.sandbox.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=ToolResult(
            tool_call_id="call_fetch_budgeted",
            name="fetch_url",
            success=True,
            output=(
                "Content from https://finance.sina.com.cn/jjxw/2025-06-12/doc-inezupah3848475.shtml\n"
                "Title: 放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网\n"
                "Description: 近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。\n\n"
                "放假通知！湖南12地明确！\n"
                "湖南12地公布2025年中小学暑假放假时间。\n"
                "根据2024年校历安排，今年暑假从7月6日开始。\n"
            ),
            summary="放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
            summary_payload={
                "fetch_url": True,
                "ok": True,
                "title": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                "description": "近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。",
                "summary": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
            },
        )
    )
    intent = _build_pending_intent(
        allowed_tool_names=["fetch_url"],
        family="web_research",
        source_text="你联网查一下 湖南学生放假时间",
    )
    intent.completion_signals = ["fetch_url"]
    handler = _build_handler(
        engine,
        tools=[ToolDefinition(name="fetch_url", description="Fetch url")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["fetch_url"],
            retry_on_contract_breach=False,
            reason="explicit_web_request",
        ),
        intent_plan=[intent],
    )
    handler.on_complete = on_complete

    events: list[dict] = []
    with patch(
        "app.ai.engine.turn_executor.RecoveryManager.decide",
        return_value=RecoveryDecision(
            action="return_partial",
            target_intent_id="intent_1",
            reason="completion_budget_exceeded",
            provider_failure_kind="budget_exit",
        ),
    ):
        async for raw in handler.generate():
            if raw.strip().startswith("data: {"):
                events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    done_event = next(event for event in events if event.get("event") == "done")

    assert "今年暑假从7月6日开始" in message_text
    assert len(captured) == 1
    assert captured[0].partial is False
    assert captured[0].completion_reason == "completed"
    assert captured[0].turn_record.get("turn_outcome") is None
    # synthesis succeeded → source is "assistant", not raw tool_evidence
    assert captured[0].turn_record["final_output_source"] == "assistant"
    assert done_event.get("turn_outcome") is None
    assert done_event["termination_reason"] == "completed"


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
async def test_stream_handler_after_turn_failure_does_not_block_on_complete():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="完成", finish_reason="stop", total_tokens=3)]],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete
    handler.prep.context_engine = SimpleNamespace(
        after_turn=AsyncMock(side_effect=RuntimeError("after turn boom"))
    )

    async for _ in handler.generate():
        pass

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    assert captured[0].output == "完成"
    assert captured[0].diagnostics["after_turn_failed"] is True
    assert captured[0].diagnostics["after_turn_error"] == "after turn boom"


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
async def test_stream_handler_with_tools_emits_thinking_before_round_finishes():
    engine = _BlockingThinkingStreamEngine()
    handler = _build_handler(engine)
    agen = handler.generate()

    first = _parse_sse_payload(await agen.__anext__())
    assert first["event"] == "conversation"

    thinking = _parse_sse_payload(await asyncio.wait_for(agen.__anext__(), timeout=0.2))
    while thinking.get("event") == "turn_stage":
        thinking = _parse_sse_payload(await asyncio.wait_for(agen.__anext__(), timeout=0.2))
    assert thinking["event"] == "thinking"
    assert thinking["delta"] == "先"

    engine.allow_tool_finish.set()

    events = [first, thinking]
    async for raw in agen:
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    assert any(
        e.get("event") == "tool_start" and e.get("name") == "query_db" for e in events
    )
    assert any(
        e.get("event") == "tool_call" and e.get("success") is True for e in events
    )
    assert any(e.get("event") == "done" for e in events)


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
        event for event in events if event.get("event") == "knowledge_base_feedback"
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
    assert any(
        e.get("event") == "tool_start" and e.get("name") == "query_db" for e in events
    )
    assert any(
        e.get("event") == "tool_call" and e.get("success") is True for e in events
    )
    msg_deltas = [e["delta"] for e in events if e.get("event") == "message"]
    assert "查询完成" in "".join(msg_deltas) and "。" in "".join(msg_deltas)


@pytest.mark.asyncio
async def test_stream_handler_does_not_recursively_contract_retry_summary_without_fetch():
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
    assert "Here is a summary based only on the search snippets" in message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert not any(
        event.get("event") == "tool_start" and event.get("name") == "fetch_url"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_does_not_recursively_contract_retry_after_partial_results():
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
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
                                "name": "ui_get_snapshot",
                                "arguments": "{}",
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=14,
                ),
            ],
            [
                ChatChunk(
                    delta="Search results for: 12306 北京 高铁票 查询 2026-04-03",
                    finish_reason="stop",
                    total_tokens=18,
                ),
            ],
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_ticket_retry",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://www.gaotie.cn/","max_length":4000}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=16,
                ),
            ],
            [
                ChatChunk(
                    delta=(
                        "今天天气可参考中国气象局页面；"
                        "去北京的高铁票可参考高铁网等替代来源；"
                        "当前页面是 admin.dashboard，展示平台控制塔指标。"
                    ),
                    finish_reason="stop",
                    total_tokens=24,
                ),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
    ]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url", "ui_get_snapshot"],
            retry_on_contract_breach=True,
            reason="explicit_web_request",
        ),
    )
    handler.request.messages = [
        ChatMessage(
            role="user",
            content="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
        )
    ]
    handler.prep.messages = list(handler.request.messages)
    handler.request.input_variables = {
        "page_context": {
            "page_key": "admin.dashboard",
            "page_title": "平台控制塔",
            "ui_epoch": 4,
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_read_region", "ui_read_table"],
            },
        }
    }

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "Search results for: 12306 北京 高铁票 查询 2026-04-03" in message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert not any(
        event.get("event") == "tool_start" and event.get("name") == "fetch_url"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_does_not_recursively_contract_retry_page_first_round():
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_search_weather",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"2026-04-03 今天天气 中国 当前天气","max_results":5}',
                            },
                        },
                        {
                            "id": "call_search_ticket",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"2026-04-03 去北京 高铁票 余票 查询 官方","max_results":5}',
                            },
                        },
                        {
                            "id": "call_page_context",
                            "type": "function",
                            "function": {
                                "name": "ui_get_snapshot",
                                "arguments": "{}",
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=18,
                ),
            ],
            [
                ChatChunk(
                    delta=(
                        "我先给你一个当前可用信息的汇总："
                        "天气和高铁票还缺少关键信息，"
                        "当前页面是 AI 智能体管理页。"
                    ),
                    finish_reason="stop",
                    total_tokens=16,
                ),
            ],
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_ticket_retry",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://www.gaotie.cn/","max_length":4000}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=14,
                ),
            ],
            [
                ChatChunk(
                    delta=(
                        "我继续补充了一轮真实工具结果："
                        "天气来源已定位到中国气象局页面，"
                        "票务信息可改走高铁网等可读候选来源，"
                        "当前页面是 admin.ai.agents 智能体管理页。"
                    ),
                    finish_reason="stop",
                    total_tokens=20,
                ),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
    ]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="page_ops",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url", "ui_get_snapshot"],
            retry_on_contract_breach=False,
            reason="explicit_page_request",
        ),
    )
    handler.request.messages = [
        ChatMessage(
            role="user",
            content="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
        )
    ]
    handler.prep.messages = list(handler.request.messages)
    handler.request.input_variables = {
        "page_context": {
            "page_key": "admin.ai.agents",
            "page_title": "智能体名称",
            "ui_epoch": 8,
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_read_region", "ui_click"],
            },
        }
    }

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "我先给你一个当前可用信息的汇总" in message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert any(
        event.get("event") == "message"
        and "AI 智能体管理页" in str(event.get("delta", ""))
        for event in events
    )
    assert not any(
        event.get("event") == "tool_start" and event.get("name") == "fetch_url"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_does_not_recursively_contract_retry_page_first_web_request():
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_search_weather",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"今天天气 城市 今日 天气 2026-04-03","max_results":5}',
                            },
                        },
                        {
                            "id": "call_search_ticket",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"2026-04-03 去北京 高铁票 余票 购票 官方","max_results":8}',
                            },
                        },
                        {
                            "id": "call_page_context",
                            "type": "function",
                            "function": {
                                "name": "ui_get_snapshot",
                                "arguments": "{}",
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=18,
                ),
            ],
            [
                ChatChunk(
                    delta=(
                        "我先给你整理目前能确认的三部分信息："
                        "天气缺城市，高铁票缺出发地，页面是智能体管理页。"
                    ),
                    finish_reason="stop",
                    total_tokens=16,
                ),
            ],
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_retry",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://www.12306.cn/index/","max_length":4000}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=14,
                ),
            ],
            [
                ChatChunk(
                    delta=(
                        "我继续读取了票务候选页。"
                        "天气仍需城市信息，高铁票仍需出发地，但这次结果来自真实候选页面。"
                    ),
                    finish_reason="stop",
                    total_tokens=18,
                ),
            ],
        ],
    )
    tools = [
        ToolDefinition(name="web_search", description="Search the web"),
        ToolDefinition(name="fetch_url", description="Fetch url"),
        ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
    ]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="page_ops",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url", "ui_get_snapshot"],
            retry_on_contract_breach=True,
            reason="explicit_page_request",
        ),
    )
    handler.request.messages = [
        ChatMessage(
            role="user",
            content="请帮我查一下今天的天气，然后联网查一下去北京的高铁票，再帮我阅读一下本页面都有什么内容",
        )
    ]
    handler.prep.messages = list(handler.request.messages)
    handler.request.input_variables = {
        "page_context": {
            "page_key": "admin.ai.agents",
            "page_title": "智能体名称",
        }
    }

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "我先给你整理目前能确认的三部分信息" in message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert not any(
        event.get("event") == "tool_start" and event.get("name") == "fetch_url"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_marks_normal_follow_up_round_without_recursive_contract_retry():
    captured = []
    completed = asyncio.Event()

    async def on_complete(result) -> None:
        captured.append(result)
        completed.set()

    engine = _RecordingStreamEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_search",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"runtime v2 rollout","max_results":5}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=10,
                )
            ],
            [
                ChatChunk(
                    delta="这里只基于搜索摘要做一个简单总结。",
                    finish_reason="stop",
                    total_tokens=14,
                )
            ],
        ]
    )
    handler = _build_handler(
        engine,
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=True,
            reason="explicit_web_request",
        ),
    )
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(engine.stream_call_kwargs) == 2
    assert engine.stream_call_kwargs[1].get("breach_retry_result") == (
        "normal_follow_up_round"
    )
    assert not any(
        call.get("breach_retry_result") == "contract_retry"
        for call in engine.stream_call_kwargs
    )
    assert captured
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "normal_follow_up_round"
        for event in handler._state.turn_events
    )
    assert not any(event.get("event") == "clear_content" for event in events)


@pytest.mark.asyncio
async def test_stream_handler_retry_emits_clear_content_before_follow_up_message() -> (
    None
):
    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="我先补查一下。",
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
                                "name": "query_db",
                                "arguments": '{"sql":"SELECT 1"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=12,
                ),
            ],
            [
                ChatChunk(
                    delta="已补救。",
                    finish_reason="stop",
                    total_tokens=18,
                ),
            ],
        ],
    )
    tools = [ToolDefinition(name="query_db", description="Query data")]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="record_ops",
            mode="required",
            allowed_tool_names=["query_db"],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
        intent_plan=[
            _build_pending_intent(
                allowed_tool_names=["query_db"],
                family="record_ops",
                source_text="补查数据",
            )
        ],
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_events = [event for event in events if event.get("event") == "message"]
    clear_events = [event for event in events if event.get("event") == "clear_content"]
    assert message_events[0]["delta"] == "我先补查一下。"
    assert clear_events
    first_clear_idx = events.index(clear_events[0])
    first_message_idx = events.index(message_events[0])
    final_message_idx = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "message"
        and event.get("delta") == "已补救。"
    )
    assert first_message_idx < first_clear_idx < final_message_idx
    assert any(
        event.get("event") == "tool_start" and event.get("name") == "query_db"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_emits_clear_content_on_retry() -> None:
    """retry 时先发 clear_content，再进入下一轮 tool retry。"""

    class _RetryEngine(_FakeEngine):
        def __init__(self) -> None:
            super().__init__(rounds=[])
            self._round = 0

        async def _stream_llm_chunks(self, **kwargs):
            _ = kwargs
            if self._round == 0:
                self._round += 1
                yield ChatChunk(delta="我不会", finish_reason="stop", total_tokens=10)
                return
            if self._round == 1:
                self._round += 1
                yield ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_retry",
                            "type": "function",
                            "function": {"name": "query_db", "arguments": "{}"},
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=15,
                )
                return

            self._round += 1
            yield ChatChunk(delta="已补救", finish_reason="stop", total_tokens=18)

    engine = _RetryEngine()
    handler = _build_handler(
        engine,
        tool_use_policy=ToolUsePolicy(
            mode="required",
            family="record_ops",
            allowed_tool_names=["query_db"],
            retry_on_contract_breach=True,
            reason="test_retry",
        ),
        intent_plan=[
            _build_pending_intent(
                allowed_tool_names=["query_db"],
                family="record_ops",
                source_text="测试 query_db",
            )
        ],
    )

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_events = [event for event in events if event.get("event") == "message"]
    clear_events = [event for event in events if event.get("event") == "clear_content"]

    assert len(message_events) >= 2
    assert message_events[0]["delta"] == "我不会"
    assert clear_events

    first_message_idx = events.index(message_events[0])
    first_clear_idx = events.index(clear_events[0])

    assert first_clear_idx > first_message_idx
    assert any(
        event.get("event") == "tool_start" and event.get("name") == "query_db"
        for event in events
    )


@pytest.mark.asyncio
async def test_stream_handler_retry_fallback_keeps_non_empty_final_assistant() -> None:
    """
    回放 576/577 关键形态：首轮能力否认触发 retry 后，最终 assistant 不应为空。
    """
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="我先补查一下。",
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
                                "name": "query_db",
                                "arguments": '{"sql":"SELECT 1"}',
                            },
                        },
                    ],
                    finish_reason="tool_calls",
                    total_tokens=12,
                ),
            ],
            [
                ChatChunk(
                    delta="这是补救后的最终答复。",
                    finish_reason="stop",
                    total_tokens=18,
                ),
            ],
        ],
    )
    tools = [ToolDefinition(name="query_db", description="Query data")]
    handler = _build_handler(
        engine,
        tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="record_ops",
            mode="required",
            allowed_tool_names=["query_db"],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
        intent_plan=[
            _build_pending_intent(
                allowed_tool_names=["query_db"],
                family="record_ops",
                source_text="runtime v2 rollout",
            )
        ],
    )
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert any(event.get("event") == "clear_content" for event in events)
    assert len(captured) == 1
    assistant_plain_messages = [
        message
        for message in captured[0].messages
        if message.get("role") == "assistant" and not message.get("tool_calls")
    ]
    assert assistant_plain_messages
    assert all(
        "我先补查一下" not in (message.get("content", "") or "")
        for message in assistant_plain_messages
    )
    assert (
        assistant_plain_messages[-1].get("content", "").strip()
        == "这是补救后的最终答复。"
    )


@pytest.mark.asyncio
async def test_stream_handler_streams_completed_tool_evidence_without_post_tool_retry():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_retry",
                            "type": "function",
                            "function": {
                                "name": "fetch_url",
                                "arguments": '{"url":"https://example.com/ai-news","max_length":4000}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=10,
                ),
            ]
        ],
    )
    engine.sandbox.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=ToolResult(
            tool_call_id="call_fetch_retry",
            name="fetch_url",
            success=True,
            output="Content from https://example.com/ai-news\nTitle: AI Daily\nDescription: Latest AI headlines and analysis.\n\nLead paragraph.",
            summary="AI Daily - Latest AI headlines and analysis.",
            summary_payload={
                "fetch_url": True,
                "ok": True,
                "error_type": "",
                "requested_url": "https://example.com/ai-news",
                "final_url": "https://example.com/ai-news",
                "title": "AI Daily",
                "description": "Latest AI headlines and analysis.",
                "summary": "AI Daily - Latest AI headlines and analysis.",
            },
        )
    )
    handler = _build_handler(
        engine,
        tools=[ToolDefinition(name="fetch_url", description="Fetch url")],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["fetch_url"],
            retry_on_contract_breach=False,
            reason="explicit_web_request",
        ),
        intent_plan=[
            _build_pending_intent(
                allowed_tool_names=["fetch_url"],
                family="web_research",
                source_text="联网查一下今日AI 最新要闻",
            )
        ],
    )
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "AI Daily - Latest AI headlines and analysis." in message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert len(captured) == 1
    assert captured[0].output == "AI Daily - Latest AI headlines and analysis."
    assert captured[0].turn_record["final_output_source"] == "tool_evidence_completed"
    assert captured[0].turn_record["post_tool_completion_state"] == (
        "tool_evidence_completed"
    )
    assert not any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "post_tool_follow_up_retry"
        for event in handler._state.turn_events
    )


@pytest.mark.asyncio
async def test_stream_handler_clears_preview_before_replaying_tool_evidence_output():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine()
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    async def _fake_run_with_turn_executor() -> TurnExecutionResult:
        handler._visible_stream_content = (
            "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网 - "
            "近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。"
        )
        handler._output = handler._visible_stream_content
        handler._runtime_turn_record = {
            "turn_outcome": "success",
            "protocol_path": "responses",
        }
        handler._state.preparation_diagnostics["final_output_source"] = (
            "tool_evidence_completed"
        )
        return TurnExecutionResult(
            output="根据已获取网页内容，长沙义务教育阶段学校今年暑假从7月6日开始。",
            total_tokens=18,
            completion_tokens_used=18,
            tool_results=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=18,
                output_tokens=18,
            ),
            partial=False,
            paused_for_consent=False,
            completion_reason="completed",
            final_output_source="tool_evidence_completed",
            action_buttons=None,
        )

    handler._run_with_turn_executor = _fake_run_with_turn_executor  # type: ignore[method-assign]

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    clear_indexes = [
        idx for idx, event in enumerate(events) if event.get("event") == "clear_content"
    ]
    message_indexes = [
        idx for idx, event in enumerate(events) if event.get("event") == "message"
    ]
    assert clear_indexes
    assert message_indexes
    assert clear_indexes[0] < message_indexes[0]
    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "长沙义务教育阶段学校今年暑假从7月6日开始" in message_text
    assert len(captured) == 1
    assert captured[0].output == message_text


@pytest.mark.asyncio
async def test_stream_handler_preserves_streamed_output_when_final_text_is_truncated_prefix():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine()
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    streamed_output = "第一段。第二段。第三段。"

    async def _fake_run_with_turn_executor() -> TurnExecutionResult:
        handler._visible_stream_content = streamed_output
        handler._output = streamed_output
        handler._runtime_turn_record = {
            "turn_outcome": "success",
            "protocol_path": "responses",
        }
        handler._state.preparation_diagnostics["final_output_source"] = "assistant"
        return TurnExecutionResult(
            output="第一段。第二段。",
            total_tokens=18,
            completion_tokens_used=18,
            tool_results=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content="第一段。第二段。"),
                total_tokens=18,
                output_tokens=18,
            ),
            partial=False,
            paused_for_consent=False,
            completion_reason="completed",
            final_output_source="assistant",
            action_buttons=None,
        )

    handler._run_with_turn_executor = _fake_run_with_turn_executor  # type: ignore[method-assign]

    async for _ in handler.generate():
        pass

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    assert captured[0].output == streamed_output


@pytest.mark.asyncio
async def test_stream_handler_keeps_finalized_output_when_shorter_text_is_not_prefix():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine()
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    async def _fake_run_with_turn_executor() -> TurnExecutionResult:
        handler._visible_stream_content = "草稿里提到旧信息，先不要持久化。"
        handler._output = handler._visible_stream_content
        handler._runtime_turn_record = {
            "turn_outcome": "success",
            "protocol_path": "responses",
        }
        handler._state.preparation_diagnostics["final_output_source"] = "assistant"
        return TurnExecutionResult(
            output="最终答案已经纠正。",
            total_tokens=18,
            completion_tokens_used=18,
            tool_results=[],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content="最终答案已经纠正。"),
                total_tokens=18,
                output_tokens=18,
            ),
            partial=False,
            paused_for_consent=False,
            completion_reason="completed",
            final_output_source="assistant",
            action_buttons=None,
        )

    handler._run_with_turn_executor = _fake_run_with_turn_executor  # type: ignore[method-assign]

    async for _ in handler.generate():
        pass

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    assert captured[0].output == "最终答案已经纠正。"


@pytest.mark.asyncio
async def test_stream_handler_no_result_completion_skips_auto_fetch_url():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    engine = _FakeEngine(
        rounds=[
            [
                ChatChunk(
                    delta="",
                    tool_calls=[
                        {
                            "id": "call_fetch_retry",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query":"today ai news","max_results":5}',
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                    total_tokens=10,
                ),
            ]
        ],
    )
    engine.sandbox.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=ToolResult(
            tool_call_id="call_fetch_retry",
            name="web_search",
            success=True,
            output="No results found for: today ai news",
            summary="baidu_public: 0 result(s)",
            summary_payload={
                "provider": "baidu_public",
                "provider_mode": "public",
                "provider_chain": ["public:baidu"],
                "attempted_backends": ["public:baidu"],
                "selected_backend": "public:baidu",
                "used_fallback": False,
                "status": "no_results",
                "result_count": 0,
                "cache_hit": False,
                "items": [],
            },
        )
    )
    intent = _build_pending_intent(
        allowed_tool_names=["web_search", "fetch_url"],
        family="web_research",
        source_text="联网查一下今日AI 最新要闻",
    )
    intent.completion_signals = ["fetch_url"]
    handler = _build_handler(
        engine,
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch url"),
        ],
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=False,
            reason="explicit_web_request",
        ),
        intent_plan=[intent],
    )
    handler.on_complete = on_complete

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert message_text
    assert not any(event.get("event") == "clear_content" for event in events)
    assert len(captured) == 1
    assert captured[0].output == message_text
    assert captured[0].turn_record["final_output_source"] == "tool_evidence_completed"
    assert captured[0].turn_record["post_tool_completion_state"] == "completed_no_result"
    assert captured[0].turn_record["auto_fetch_gate_reason"] == (
        "search_no_results_completed"
    )


@pytest.mark.asyncio
async def test_stream_handler_logs_failed_retry_when_required_policy_still_returns_text() -> (
    None
):
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
        intent_plan=[
            _build_pending_intent(
                allowed_tool_names=["web_search", "fetch_url"],
                family="web_research",
                source_text="没有联网能力",
            )
        ],
    )

    events: list[dict] = []
    handler.runtime_contract.log_tool_contract_diagnostics = MagicMock()
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    message_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert "仍然没有联网能力。" in message_text
    diag_mock = handler.runtime_contract.log_tool_contract_diagnostics
    assert diag_mock.call_count >= 2
    retry_results = [call.kwargs["retry_result"] for call in diag_mock.call_args_list]
    assert retry_results[0] == "retrying"
    assert retry_results[-1] == "failed"


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
        m
        for m in captured[0].messages
        if m.get("role") == "assistant" and m.get("tool_calls")
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

    assert (
        "".join(e.get("delta", "") for e in events if e.get("event") == "message")
        == "请先确认后再执行。"
    )
    assert len(captured) == 1
    assistant_messages = [
        m for m in captured[0].messages if m.get("role") == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0].get("tool_calls")


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
                    "tool_kind": "query_records",
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
                            "name": "query_records",
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
    tools = [ToolDefinition(name="query_records", description="Query data")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    tool_call_event = next(
        event
        for event in events
        if event.get("event") == "tool_call" and event.get("name") == "query_records"
    )
    assert tool_call_event.get("summary") == "按今天范围统计调用并按租户分组"
    assert tool_call_event.get("summary_payload") == {
        "tool_kind": "query_records",
        "tables": ["ai_call_logs", "tenants"],
        "metrics": ["COUNT(acl.id)"],
        "filters": ["today"],
    }


@pytest.mark.asyncio
async def test_stream_handler_runs_parallel_safe_web_search_batch_concurrently():
    class _TrackingSearchSandbox:
        def __init__(self) -> None:
            self.active_calls = 0
            self.max_parallel = 0

        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list,
            conversation_id: int,
        ):
            _ = definitions, conversation_id
            self.active_calls += 1
            self.max_parallel = max(self.max_parallel, self.active_calls)
            await asyncio.sleep(0.02)
            self.active_calls -= 1
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output=json.dumps({"query": arguments.get("query", "")}),
            )

    engine = _FakeEngine()
    engine.sandbox = _TrackingSearchSandbox()
    handler = _build_handler(
        engine,
        tools=[ToolDefinition(name="web_search", description="Search the web")],
    )
    adapter = StreamIOAdapter(handler)
    messages = [ChatMessage(role="user", content="查两条新闻")]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_search_1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"AI latest news"}',
                },
            },
            {
                "id": "call_search_2",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"OpenAI latest news"}',
                },
            },
        ],
        total_tokens=12,
    )

    result = await adapter.handle_tool_calls(
        response=response,
        tools=handler.prep.tools,
        messages=messages,
        starting_total_tokens=12,
        starting_completion_tokens=12,
    )

    assert len(result.tool_results) == 2
    assert [tool_result.tool_call_id for tool_result in result.tool_results] == [
        "call_search_1",
        "call_search_2",
    ]
    assert engine.sandbox.max_parallel >= 2


@pytest.mark.asyncio
async def test_handle_tool_calls_trims_unexecuted_tail_on_early_exit():
    from app.services.ai.conversation_service import ConversationService

    class _BudgetExitAfterFirstExecutionSandbox(_FakeSandbox):
        def __init__(self) -> None:
            super().__init__()
            self.execute_count = 0

        async def execute(
            self,
            tool_call_id: str,
            name: str,
            arguments: dict,
            definitions: list[ToolDefinition],
            conversation_id: int,
        ) -> ToolResult:
            _ = definitions, conversation_id
            self.execute_count += 1
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                success=True,
                output=json.dumps(
                    {
                        "name": name,
                        "page_key": arguments.get("page_key"),
                    }
                ),
            )

    engine = _FakeEngine()
    budget_sandbox = _BudgetExitAfterFirstExecutionSandbox()
    engine.sandbox = budget_sandbox
    tools = [
        ToolDefinition(name="ui_get_snapshot", description="Get UI snapshot"),
        ToolDefinition(name="fetch_url", description="Fetch URL"),
    ]
    handler = _build_handler(engine, tools=tools)
    handler._runtime_turn_record = {}
    handler._runtime_turn_record_source = None
    handler._runtime_turn_record_overlays = {}
    handler._state.budget_exit_reason = (
        lambda: (
            "tool_result_budget_exceeded"
            if budget_sandbox.execute_count >= 1
            else None
        )
    )
    adapter = StreamIOAdapter(handler)
    messages = [ChatMessage(role="user", content="继续读取页面并补来源")]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        tool_calls=[
            {
                "id": "call_snapshot",
                "type": "function",
                "function": {
                    "name": "ui_get_snapshot",
                    "arguments": '{"page_key":"tenant.crm.detail"}',
                },
            },
            {
                "id": "call_fetch",
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "arguments": '{"url":"https://example.com"}',
                },
            },
        ],
        total_tokens=24,
    )

    result = await adapter.handle_tool_calls(
        response=response,
        tools=handler.prep.tools,
        messages=messages,
        starting_total_tokens=24,
        starting_completion_tokens=24,
    )

    assert [tool_result.name for tool_result in result.tool_results] == [
        "ui_get_snapshot"
    ]
    assert result.response is None

    assistant_round = messages[1]
    assert assistant_round.role == "assistant"
    assert [tc["id"] for tc in (assistant_round.tool_calls or [])] == [
        "call_snapshot",
    ]
    assert [msg.tool_call_id for msg in messages if msg.role == "tool"] == [
        "call_snapshot",
    ]

    sanitized = ConversationService.sanitize_tool_messages(messages)
    assert [msg.role for msg in sanitized] == ["user", "assistant", "tool"]
    assert [tc["id"] for tc in (sanitized[1].tool_calls or [])] == [
        "call_snapshot",
    ]


@pytest.mark.asyncio
async def test_parse_error_abort_after_consecutive_ui_action_failures():
    """
    parse error 连续 3 次后触发熔断，停止工具循环并输出恢复提示。
    验证富文本审计方案：parse error 分支纳入熔断计数。
    """
    # 3 个 ui_click 调用，每个 arguments 为非法 JSON
    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "ui_click",
                                "arguments": "{bad json 1",
                            },
                        },
                    {
                            "id": "c2",
                            "type": "function",
                            "function": {
                                "name": "ui_click",
                                "arguments": "{bad json 2",
                            },
                        },
                    {
                            "id": "c3",
                            "type": "function",
                            "function": {
                                "name": "ui_click",
                                "arguments": "{bad json 3",
                            },
                        },
                ],
                total_tokens=100,
            ),
        ],
    )
    tools = [ToolDefinition(name="ui_click", description="Click UI element")]
    handler = _build_handler(engine, tools=tools)

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    # 应有 3 个 tool_call 失败事件
    failed_calls = [
        e for e in events if e.get("event") == "tool_call" and e.get("success") is False
    ]
    assert len(failed_calls) >= 3

    # 熔断后 output 应包含恢复提示（不再依赖旧 multiple_failures 文案 key）
    output = handler._output or ""
    assert output
    assert (
        "Multiple page operations failed" in output
        or "页面操作多次失败" in output
        or "暂时中断" in output
    )


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


@pytest.mark.asyncio
async def test_done_waits_for_on_complete_and_merges_callback_extra():
    order: list[str] = []

    async def on_complete(_result) -> dict[str, object]:
        order.append("on_complete_start")
        await asyncio.sleep(0)
        order.append("on_complete_done")
        return {
            "persistence_committed": True,
            "persisted_message_count": 2,
        }

    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content="完成"),
                tool_calls=None,
                total_tokens=20,
            ),
        ],
    )
    handler = _build_handler(engine)
    handler.on_complete = on_complete

    done_payload: dict | None = None
    seen_turn_stage = False
    async for raw in handler.generate():
        if not raw.strip().startswith("data: {"):
            continue
        payload = _parse_sse_payload(raw)
        if payload.get("event") == "turn_stage":
            seen_turn_stage = True
        if payload.get("event") == "done":
            order.append("done")
            done_payload = payload

    assert order == ["on_complete_start", "on_complete_done", "done"]
    assert seen_turn_stage is True
    assert done_payload is not None
    assert done_payload.get("persistence_committed") is True
    assert done_payload.get("persisted_message_count") == 2
    assert done_payload.get("completion_reason") == "completed"
    assert done_payload.get("turn_flow_complete") is True
    assert done_payload.get("final_stage_status") == "completed"
    assert "trace_id" in done_payload


@pytest.mark.asyncio
async def test_stream_emits_tool_selection_skipped_stage_when_optimizer_selects_zero():
    engine = _FakeEngine(
        call_llm_responses=[
            ChatResponse(
                message=ChatMessage(role="assistant", content="已完成"),
                tool_calls=None,
                total_tokens=12,
            ),
        ],
    )
    handler = _build_handler(engine)
    handler.prep.optimize_event = {"total": 15, "selected": 0, "execution_path": "normal"}

    stage_updates: list[dict] = []
    async for raw in handler.generate():
        if not raw.strip().startswith("data: {"):
            continue
        payload = _parse_sse_payload(raw)
        if payload.get("event") == "turn_stage_update":
            stage_updates.append(payload)

    assert any(
        (event.get("stage") or {}).get("type") == "tool_selection"
        and (event.get("stage") or {}).get("status") == "skipped"
        for event in stage_updates
    )
