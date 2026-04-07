from __future__ import annotations

import pytest

from app.ai.runtime.query_engine import ConversationQueryEngine
from app.ai.types import ChatChunk, ChatMessage


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


@pytest.mark.asyncio
async def test_runtime_query_engine_marks_partial_provider_failure_after_meaningful_chunk() -> None:
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
async def test_runtime_query_engine_preserves_specific_partial_termination_reason() -> None:
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
