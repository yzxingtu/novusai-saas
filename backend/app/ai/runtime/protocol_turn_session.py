"""Mutable turn session helpers for runtime-v2 protocol execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.runtime.contracts import ProtocolExecutionPlan, TurnCommand
from app.ai.runtime.protocol_planner import ProtocolPlanner
from app.ai.runtime.types import ContextSource, FallbackRecord, ProtocolPath, TurnRecord
from app.ai.types import ChatMessage, ChatResponse


@dataclass
class ProtocolTurnSession:
    command: TurnCommand
    plan: ProtocolExecutionPlan
    turn_record: TurnRecord

    @classmethod
    def create(
        cls,
        *,
        planner: ProtocolPlanner,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
        selected_skill_names: list[str] | None = None,
        context_sources: list[ContextSource] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> ProtocolTurnSession:
        command = TurnCommand(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
            extra_kwargs=dict(extra_kwargs or {}),
        )
        plan = planner.plan_turn(
            tools=command.tools,
            selected_skill_names=command.selected_skill_names,
            context_sources=command.context_sources,
        )
        turn_record = TurnRecord(
            protocol_path=plan.preferred_protocol,
            selected_tool_names=list(plan.selected_tool_names),
            selected_skill_names=list(plan.selected_skill_names),
            context_sources=list(plan.context_sources),
        )
        return cls(
            command=command,
            plan=plan,
            turn_record=turn_record,
        )

    def use_protocol(self, protocol: ProtocolPath) -> None:
        self.turn_record.protocol_path = protocol

    def next_protocol(self, index: int) -> ProtocolPath | None:
        if index + 1 >= len(self.plan.protocol_chain):
            return None
        return self.plan.protocol_chain[index + 1]

    def append_fallback(self, index: int, *, from_protocol: ProtocolPath, reason: str) -> bool:
        next_protocol = self.next_protocol(index)
        if next_protocol is None:
            return False
        self.turn_record.fallback_history.append(
            FallbackRecord(
                from_protocol=from_protocol,
                to_protocol=next_protocol,
                reason=reason,
            )
        )
        return True

    def mark_failed(
        self,
        *,
        termination_reason: str = "error",
        block_reason: str | None = None,
    ) -> None:
        if block_reason:
            self.turn_record.metadata["protocol_fallback_blocked_reason"] = block_reason
        self.turn_record.turn_outcome = "failed"
        self.turn_record.termination_reason = termination_reason

    def mark_partial_failure(self, *, termination_reason: str) -> None:
        self.turn_record.turn_outcome = "partial"
        self.turn_record.termination_reason = termination_reason

    def finalize_chat_success(self, response: ChatResponse) -> ChatResponse:
        self.turn_record.turn_outcome = "success"
        self.turn_record.termination_reason = (
            "protocol_fallback" if self.turn_record.fallback_history else "completed"
        )
        metadata = dict(response.metadata or {})
        metadata["runtime_turn_record"] = self.turn_record
        response.metadata = metadata
        return response

    def finalize_stream_success(self, *, emitted_chunk_count: int) -> None:
        self.turn_record.turn_outcome = "success"
        self.turn_record.termination_reason = (
            "protocol_fallback" if self.turn_record.fallback_history else "completed"
        )
        self.turn_record.metadata["stream_chunk_count"] = emitted_chunk_count

    def finalize_sync_rescue_success(self, *, emitted_chunk_count: int) -> None:
        if self.turn_record.fallback_history:
            self.turn_record.fallback_history[-1].recovered = True
            self.turn_record.fallback_history[-1].metadata["recovery_path"] = (
                "sync_chat_completions"
            )
        self.turn_record.turn_outcome = "success"
        self.turn_record.termination_reason = "protocol_fallback"
        self.turn_record.metadata["sync_rescue"] = True
        self.turn_record.metadata["stream_chunk_count"] = emitted_chunk_count + 1

    def finalize_stream_empty_failure(self, *, reason: str) -> None:
        self.turn_record.turn_outcome = "failed"
        self.turn_record.termination_reason = "stream_empty_after_fallback"
        self.turn_record.metadata["sync_rescue"] = True
        self.turn_record.metadata["stream_empty_reason"] = reason


__all__ = ["ProtocolTurnSession"]
