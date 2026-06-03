"""
Test type: behavioral
Scope: StreamExecutionHandler real streaming behavior and terminal SSE semantics.
Mock strategy: runtime flow stays real; only transport/external infra seams are faked.
"""

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
    handler._output = "内部工具原始预览：校历条目尚未整理。"
    adapter = StreamIOAdapter(handler)

    handler.runtime_contract.finalize_completed_output = AsyncMock(
        return_value=(
            "根据内部工具结果，长沙义务教育阶段学校今年暑假从7月6日开始。",
            18,
            18,
        )
    )
    (
        output,
        total_tokens,
        completion_tokens_used,
    ) = await adapter.finalize_completed_output(
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
    assert "长沙义务教育阶段学校今年暑假从7月6日开始" in output
    assert "内部工具原始预览" not in output
    assert total_tokens == 18
    assert completion_tokens_used == 18


@pytest.mark.asyncio
async def test_stream_io_adapter_keeps_finalized_partial_output_over_stream_preview():
    handler = _build_handler(_FakeEngine())
    handler._output = "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网"
    adapter = StreamIOAdapter(handler)

    handler.runtime_contract.finalize_partial_output = AsyncMock(
        return_value=(
            "我先把目前能确认的内容给你：长沙义务教育阶段学校今年暑假从7月6日开始。",
            18,
            18,
        )
    )
    (
        output,
        total_tokens,
        completion_tokens_used,
    ) = await adapter.finalize_partial_output(
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
    assert "长沙义务教育阶段学校今年暑假从7月6日开始" in output
    assert "特殊教育学校_新浪财经_新浪网" not in output
    assert total_tokens == 18
    assert completion_tokens_used == 18


def test_stream_io_adapter_request_defaults_use_trusted_auto() -> None:
    handler = _build_handler(_FakeEngine())
    adapter = StreamIOAdapter(handler)

    request_proxy = adapter._request_with_defaults()

    assert request_proxy.interaction_mode == "trusted_auto"


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
async def test_stream_handler_preserves_runtime_protocol_for_zero_chunk_provider_timeout() -> (
    None
):
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
async def test_stream_handler_cancelled_after_provider_timeout_preserves_timeout_done_reason() -> (
    None
):
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    handler = _build_handler(_FakeEngine())
    handler.on_complete = on_complete

    async def _raise_cancelled_after_timeout():
        handler._state.register_provider_failure(
            kind="provider_timeout",
            event={"kind": "provider_timeout", "protocol_path": "responses"},
        )
        raise asyncio.CancelledError("cancelled after provider timeout")

    handler._run_with_turn_executor = _raise_cancelled_after_timeout

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    result = captured[0]
    assert result.interrupted is True
    assert result.completion_reason == "provider_timeout"
    assert result.provider_failure_kind == "provider_timeout"

    done_payload = next(event for event in events if event.get("event") == "done")
    assert done_payload["completion_reason"] == "provider_timeout"
    assert done_payload["termination_reason"] == "provider_timeout"
    assert not any(event.get("error") is True for event in events)

    fallback_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    )
    assert fallback_text.strip()


@pytest.mark.asyncio
async def test_stream_handler_provider_timeout_uses_low_noise_logging() -> None:
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    handler = _build_handler(_BrokenProviderTimeoutEngine())
    handler.on_complete = on_complete

    with patch("app.ai.engine.stream_handler.logger") as logger_mock:
        async for _raw in handler.generate():
            pass

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    logger_mock.error.assert_not_called()
    logger_mock.warning.assert_not_called()
    logger_mock.info.assert_called()


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
        thinking = _parse_sse_payload(
            await asyncio.wait_for(agen.__anext__(), timeout=0.2)
        )
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
async def test_stream_handler_emits_retrieval_evidence_before_first_message():
    engine = _FakeEngine(
        rounds=[[ChatChunk(delta="完成", finish_reason="stop", total_tokens=3)]],
    )
    handler = _build_handler(engine)
    handler.prep.rag_sources = [
        {
            "doc_id": 21,
            "doc_name": "runtime.md",
            "id": "kb-live-1",
            "kind": "knowledge_base",
            "knowledge_base_id": 7,
            "knowledge_base_name": "实时知识库",
            "snippet": "流式开始前已命中知识库资料",
        }
    ]

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    evidence_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "turn_evidence"
        and (event.get("evidence") or {}).get("id") == "kb-live-1"
    )
    message_index = next(
        index for index, event in enumerate(events) if event.get("event") == "message"
    )
    evidence = events[evidence_index]["evidence"]
    assert evidence_index < message_index
    assert evidence["kind"] == "knowledge_base"
    assert evidence["knowledge_base_name"] == "实时知识库"
    assert evidence["snippet"] == "流式开始前已命中知识库资料"


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
    running_evidence_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "turn_evidence"
        and (event.get("evidence") or {}).get("tool_call_id") == "call_1"
        and (event.get("evidence") or {}).get("status") == "running"
    )
    completed_evidence_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "turn_evidence"
        and (event.get("evidence") or {}).get("tool_call_id") == "call_1"
        and (event.get("evidence") or {}).get("status") == "success"
    )
    done_index = next(
        index for index, event in enumerate(events) if event.get("event") == "done"
    )
    assert running_evidence_index < completed_evidence_index < done_index
    completed_evidence = events[completed_evidence_index]["evidence"]
    assert completed_evidence["tool_name"] == "query_db"
    assert completed_evidence["duration_ms"] >= 0
    assert completed_evidence["output"] == '{"ok": true}'
    msg_deltas = [e["delta"] for e in events if e.get("event") == "message"]
    assert "查询完成" in "".join(msg_deltas) and "。" in "".join(msg_deltas)


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
        if event.get("event") == "message" and event.get("delta") == "已补救。"
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
            "内部工具原始预览：校历条目尚未整理，包含多个学校阶段。"
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
            output="根据内部工具结果，长沙义务教育阶段学校今年暑假从7月6日开始。",
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
async def test_interrupted_calls_on_complete_with_partial_result():
    """
    中断（CancelledError）时 on_complete 应收到 partial ExecutionResult，且 SSE 以 interrupted done 收口。
    """
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    events: list[dict] = []

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

    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    if handler._background_tasks:
        await asyncio.wait_for(
            asyncio.gather(*list(handler._background_tasks)),
            timeout=1,
        )

    done_payload = next(event for event in events if event.get("event") == "done")
    assert len(captured) == 1
    r = captured[0]
    assert r.partial is True
    assert r.interrupted is True
    assert r.completion_reason == "interrupted"
    assert r.success is False
    assert r.output == "部"
    assert r.messages is not None
    assert done_payload["completion_reason"] == "interrupted"
    assert done_payload["termination_reason"] == "interrupted"


@pytest.mark.asyncio
async def test_interrupted_without_visible_output_still_emits_readable_message():
    """
    无正文即被 CancelledError 中断时，仍要落成可读 interrupted 文案，而不是空白 assistant。
    """
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    handler = _build_handler(_FakeEngine())
    handler.on_complete = on_complete

    async def _raise_cancelled_without_output():
        raise asyncio.CancelledError("simulated cancel before visible output")

    handler._run_with_turn_executor = _raise_cancelled_without_output

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    done_payload = next(event for event in events if event.get("event") == "done")
    fallback_text = "".join(
        event.get("delta", "") for event in events if event.get("event") == "message"
    ).strip()

    assert len(captured) == 1
    result = captured[0]
    assert result.interrupted is True
    assert result.completion_reason == "interrupted"
    assert result.output.strip()
    assert fallback_text
    assert done_payload["completion_reason"] == "interrupted"
    assert done_payload["termination_reason"] == "interrupted"


@pytest.mark.asyncio
async def test_transport_disconnect_cancel_does_not_synthesize_error_reply():
    from app.ai.engine.types import ExecutionResult

    captured: list[ExecutionResult] = []
    completed = asyncio.Event()

    async def on_complete(result: ExecutionResult) -> None:
        captured.append(result)
        completed.set()

    handler = _build_handler(_FakeEngine())
    handler.on_complete = on_complete

    async def _raise_transport_disconnect_cancel():
        raise asyncio.CancelledError(
            "Cancelled via cancel scope 0xabc by <Task pending name='Task-118' "
            "coro=<RequestResponseCycle.run_asgi() running at httptools_impl.py:416>>"
        )

    handler._run_with_turn_executor = _raise_transport_disconnect_cancel

    events: list[dict] = []
    async for raw in handler.generate():
        if raw.strip().startswith("data: {"):
            events.append(_parse_sse_payload(raw))

    await asyncio.wait_for(completed.wait(), timeout=1)

    assert len(captured) == 1
    result = captured[0]
    assert result.interrupted is True
    assert result.output == ""
    assert result.diagnostics["transport_disconnect"] is True
    assert result.turn_record["transport_disconnect"] is True
    assert result.turn_record["metadata"]["transport_disconnect"] is True
    assert not any(event.get("event") == "message" for event in events)

    done_payload = next(event for event in events if event.get("event") == "done")
    assert done_payload["completion_reason"] == "interrupted"
    assert done_payload["termination_reason"] == "interrupted"


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
    handler.prep.optimize_event = {
        "total": 15,
        "selected": 0,
        "execution_path": "normal",
    }

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
