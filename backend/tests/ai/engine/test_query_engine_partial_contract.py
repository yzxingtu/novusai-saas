"""
Test type: behavioral
Scope: ConversationQueryEngine rescue and retry stop-loss behavior.
Mock strategy: only adapter/protocol transport edges are faked; runtime decisions are real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.exceptions import ProviderError, ProviderTimeoutError
from app.ai.runtime.query_engine import ConversationQueryEngine
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class _BoomAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise RuntimeError("provider failed after partial progress")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _BudgetExitAfterChunkError(RuntimeError):
    termination_reason = "elapsed_budget_exceeded"


class _BudgetAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise _BudgetExitAfterChunkError("elapsed budget exceeded")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _ToolTimeoutAfterChunkError(RuntimeError):
    provider_failure_kind = "tool_timeout"


class _ToolTimeoutAfterChunkAdapter:
    wire_api = "chat_completions"

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="partial reply", role="assistant")
        raise _ToolTimeoutAfterChunkError("tool timeout after partial chunk")

    async def chat(self, **kwargs):
        _ = kwargs
        raise AssertionError("sync rescue should not be used in this test")


class _ReasoningOnlyThenErrorAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise RuntimeError("responses stream interrupted after reasoning")

    async def chat(self, **kwargs):
        _ = kwargs
        self.chat_calls += 1
        return ChatResponse(
            message=ChatMessage(role="assistant", content="rescued reply"),
            finish_reason="stop",
            model="gpt-5.4",
        )


class _ReasoningOnlyThenTimeoutAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise ProviderTimeoutError(
            "provider timed out",
            provider_code="openai_compatible",
            model_code="gpt-5.4",
        )

    async def chat(self, **kwargs):
        _ = kwargs
        self.chat_calls += 1
        raise AssertionError("timeout path should not trigger sync rescue")


class _ReasoningOnlyThenRetryableRescueAdapter:
    wire_api = "responses"
    protocol_capabilities = SimpleNamespace(
        primary_wire_api="responses",
        allowed_wire_apis=("responses",),
        allowed_cross_protocol_fallbacks={},
        allow_adapter_cross_protocol_fallback=False,
    )

    def __init__(self) -> None:
        self.chat_calls = 0
        self.chat_kwargs: list[dict] = []

    async def stream_chat(self, **kwargs):
        _ = kwargs
        yield ChatChunk(delta="", reasoning_delta="先检查公开资料", role="assistant")
        raise RuntimeError("responses stream interrupted after reasoning")

    async def chat(self, **kwargs):
        self.chat_kwargs.append(dict(kwargs))
        self.chat_calls += 1
        if self.chat_calls == 1:
            raise ProviderError(
                "service unavailable",
                provider_code="openai_compatible",
                model_code="gpt-5.4",
                error_code="503",
            )
        return ChatResponse(
            message=ChatMessage(role="assistant", content="rescued after retry"),
            finish_reason="stop",
            model="gpt-5.4",
        )


@pytest.mark.asyncio
async def test_runtime_query_engine_marks_partial_provider_failure_after_meaningful_chunk() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_BoomAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(RuntimeError, match="provider failed after partial progress"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert (
        query_engine.turn_record.termination_reason
        == "provider_failure_after_partial_progress"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_preserves_specific_partial_termination_reason() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_BudgetAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(_BudgetExitAfterChunkError, match="elapsed budget exceeded"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert query_engine.turn_record.termination_reason == "elapsed_budget_exceeded"


@pytest.mark.asyncio
async def test_runtime_query_engine_preserves_typed_tool_timeout_reason() -> None:
    query_engine = ConversationQueryEngine(
        adapter=_ToolTimeoutAfterChunkAdapter(),
        strict_contract=False,
    )

    with pytest.raises(_ToolTimeoutAfterChunkError, match="tool timeout"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert query_engine.turn_record.turn_outcome == "partial"
    assert query_engine.turn_record.termination_reason == "tool_timeout"


@pytest.mark.asyncio
async def test_runtime_query_engine_sync_rescues_reasoning_only_stream_failure_without_fallback_chain() -> (
    None
):
    adapter = _ReasoningOnlyThenErrorAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    chunks = await query_engine.run_stream_turn(
        messages=[ChatMessage(role="user", content="继续")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
    )

    assert [chunk.reasoning_delta for chunk in chunks if chunk.reasoning_delta] == [
        "先检查公开资料"
    ]
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["rescued reply"]
    assert adapter.chat_calls == 1
    assert query_engine.turn_record.turn_outcome == "success"
    assert query_engine.turn_record.termination_reason == "protocol_fallback"
    assert query_engine.turn_record.metadata["sync_rescue"] is True
    assert query_engine.turn_record.metadata["sync_rescue_source"] == "stream_error"


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_sync_rescue_reasoning_only_timeout_failure() -> (
    None
):
    adapter = _ReasoningOnlyThenTimeoutAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    with pytest.raises(ProviderTimeoutError, match="provider timed out"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert adapter.chat_calls == 0
    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.metadata["protocol_fallback_blocked_reason"] == (
        "provider_timeout"
    )


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_retry_sync_rescue_after_retryable_failure(
    monkeypatch,
) -> None:
    adapter = _ReasoningOnlyThenRetryableRescueAdapter()
    query_engine = ConversationQueryEngine(
        adapter=adapter,
        strict_contract=False,
    )

    async def _noop_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.ai.runtime.query_engine.asyncio.sleep", _noop_sleep)

    with pytest.raises(ProviderError, match="service unavailable"):
        await query_engine.run_stream_turn(
            messages=[ChatMessage(role="user", content="继续")],
            model="gpt-5.4",
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=None,
            tool_choice=None,
            supports_vision=False,
            supports_audio=False,
            supports_video=False,
        )

    assert adapter.chat_calls == 1
    assert adapter.chat_kwargs[0]["_runtime_reasoning_effort_override"] == "low"
    assert query_engine.turn_record.turn_outcome == "failed"
    assert query_engine.turn_record.metadata["sync_rescue_attempt_count"] == 1
    assert query_engine.turn_record.metadata["sync_rescue_retry_count"] == 0


@pytest.mark.asyncio
async def test_runtime_query_engine_does_not_inject_invalid_runtime_retry_override() -> (
    None
):
    query_engine = ConversationQueryEngine(
        adapter=_ReasoningOnlyThenTimeoutAdapter(),
        strict_contract=False,
    )

    captured_extra_kwargs: list[dict[str, object]] = []

    async def _fake_chat(*, protocol_path, command, turn_record):
        _ = protocol_path, turn_record
        captured_extra_kwargs.append(dict(command.extra_kwargs or {}))
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            finish_reason="stop",
            model="gpt-5.4",
        )

    query_engine.runner.chat = _fake_chat  # type: ignore[method-assign]

    response = await query_engine.run_chat_turn(
        messages=[ChatMessage(role="user", content="继续")],
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=None,
        top_p=1.0,
        tools=None,
        tool_choice=None,
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
    )

    assert response.message.content == "ok"
    assert "_runtime_client_max_retries_override" not in captured_extra_kwargs[0]
    assert "timeout_seconds" not in captured_extra_kwargs[0]
