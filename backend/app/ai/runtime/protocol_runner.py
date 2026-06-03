"""Protocol execution runner for runtime-v2 query engine."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.runtime.contracts import TurnCommand
from app.ai.runtime.tool_executor import ToolExecutor
from app.ai.runtime.types import ProtocolPath, TurnRecord
from app.ai.types import ChatChunk, ChatResponse


class ProtocolRunner:
    """Executes protocol-specific calls without owning fallback policy."""

    def __init__(self, *, adapter: Any, strict_contract: bool = False) -> None:
        self.adapter = adapter
        self.strict_contract = strict_contract

    @staticmethod
    def attach_turn_record(
        chunk: ChatChunk,
        *,
        protocol_path: ProtocolPath,
        turn_record: TurnRecord,
    ) -> ChatChunk:
        metadata = dict(chunk.metadata or {})
        metadata.setdefault("runtime_protocol_path", protocol_path)
        metadata["runtime_turn_record"] = turn_record
        chunk.metadata = metadata
        return chunk

    async def chat(
        self,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        turn_record: TurnRecord,
    ) -> ChatResponse:
        adapter_kwargs = command.to_adapter_kwargs(protocol_path=protocol_path)
        protocol_chat = getattr(self.adapter, "execute_protocol_chat", None)
        if callable(protocol_chat):
            response = await protocol_chat(
                wire_api=protocol_path,
                **adapter_kwargs,
            )
        else:
            response = await self.adapter.chat(**adapter_kwargs)
        if self.strict_contract:
            ToolExecutor.enforce_required_contract(
                tool_choice=command.tool_choice,
                output_text=response.message.content,
                tool_calls=response.tool_calls or response.message.tool_calls,
                turn_record=turn_record,
            )
        return response

    async def stream(
        self,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        turn_record: TurnRecord,
    ) -> AsyncIterator[ChatChunk]:
        adapter_kwargs = command.to_adapter_kwargs(protocol_path=protocol_path)
        protocol_stream = getattr(self.adapter, "execute_protocol_stream", None)
        stream_iterable = (
            protocol_stream(
                wire_api=protocol_path,
                **adapter_kwargs,
            )
            if callable(protocol_stream)
            else self.adapter.stream_chat(**adapter_kwargs)
        )
        async for chunk in stream_iterable:
            yield self.attach_turn_record(
                chunk,
                protocol_path=protocol_path,
                turn_record=turn_record,
            )

    @staticmethod
    def response_to_chunk(response: ChatResponse) -> ChatChunk:
        finish_reason = response.finish_reason
        if not finish_reason:
            finish_reason = (
                "tool_calls"
                if (response.tool_calls or response.message.tool_calls)
                else "stop"
            )
        return ChatChunk(
            delta=response.message.content or "",
            reasoning_delta=response.message.reasoning_content or "",
            role=response.message.role,
            finish_reason=finish_reason,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            tool_calls=response.tool_calls or response.message.tool_calls,
            metadata=dict(response.metadata or {}),
        )
