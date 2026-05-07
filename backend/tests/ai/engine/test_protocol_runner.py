from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.runtime.contracts import ProtocolGuardContract, TurnCommand
from app.ai.runtime.protocol_runner import ProtocolRunner
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@pytest.mark.asyncio
async def test_protocol_runner_chat_passes_strict_protocol_overrides() -> None:
    adapter = AsyncMock()
    adapter.execute_protocol_chat = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )
    )
    runner = ProtocolRunner(adapter=adapter)
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        temperature=0.2,
        max_tokens=256,
        top_p=0.9,
        tools=None,
        tool_choice=None,
        extra_kwargs={"tenant_id": 1},
    )

    await runner.chat(
        protocol_path="responses",
        command=command,
        turn_record=TurnRecord(),
    )

    kwargs = adapter.execute_protocol_chat.await_args.kwargs
    assert kwargs["wire_api"] == "responses"
    assert kwargs["_runtime_force_wire_api"] == "responses"
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is True
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True
    assert kwargs["tenant_id"] == 1


@pytest.mark.asyncio
async def test_protocol_runner_stream_passes_strict_protocol_overrides() -> None:
    async def _stream():
        yield ChatChunk(delta="ok", metadata={})

    def _execute_protocol_stream(**kwargs):
        _ = kwargs
        return _stream()

    adapter = MagicMock()
    adapter.execute_protocol_stream = MagicMock(side_effect=_execute_protocol_stream)
    runner = ProtocolRunner(adapter=adapter)
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
    )

    chunks = [
        chunk
        async for chunk in runner.stream(
            protocol_path="chat_completions",
            command=command,
            turn_record=TurnRecord(),
        )
    ]

    assert len(chunks) == 1
    kwargs = adapter.execute_protocol_stream.call_args.kwargs
    assert kwargs["wire_api"] == "chat_completions"
    assert kwargs["_runtime_force_wire_api"] == "chat_completions"
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is True
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is True


@pytest.mark.asyncio
async def test_protocol_runner_respects_explicit_guard_contract() -> None:
    adapter = AsyncMock()
    adapter.execute_protocol_chat = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            metadata={},
        )
    )
    runner = ProtocolRunner(adapter=adapter)
    command = TurnCommand(
        messages=[ChatMessage(role="user", content="hello")],
        model="gpt-5.4",
        protocol_guards=ProtocolGuardContract(
            disable_cross_protocol_fallback=False,
            disable_sync_rescue=False,
        ),
    )

    await runner.chat(
        protocol_path="responses",
        command=command,
        turn_record=TurnRecord(),
    )

    kwargs = adapter.execute_protocol_chat.await_args.kwargs
    assert (
        kwargs[ProtocolGuardContract.RUNTIME_DISABLE_CROSS_PROTOCOL_FALLBACK] is False
    )
    assert kwargs[ProtocolGuardContract.RUNTIME_DISABLE_SYNC_RESCUE] is False
