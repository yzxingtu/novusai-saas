"""Runtime recovery policy for protocol fallback and rescue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import app.ai.runtime.protocol_recovery_semantics as recovery_semantics
from app.ai.runtime.tool_executor import ToolExecutor
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatChunk, ChatResponse


@dataclass
class ObservedStream:
    chunk_count: int = 0
    has_visible_output: bool = False
    has_reasoning_output: bool = False
    has_tool_calls: bool = False
    has_progress_signal: bool = False
    output_parts: list[str] = field(default_factory=list)
    collected_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    progress_kinds: list[str] = field(default_factory=list)

    @property
    def is_meaningful(self) -> bool:
        return (
            self.has_visible_output or self.has_reasoning_output or self.has_tool_calls
        )

    @property
    def blocks_fallback(self) -> bool:
        return self.has_visible_output or self.has_tool_calls

    @property
    def output_text(self) -> str:
        return "".join(self.output_parts)

    def observe(
        self,
        chunk: ChatChunk,
        *,
        progress_kinds: list[str] | None = None,
    ) -> None:
        self.chunk_count += 1

        delta = getattr(chunk, "delta", None)
        reasoning_delta = getattr(chunk, "reasoning_delta", None)
        tool_calls = getattr(chunk, "tool_calls", None)

        if ToolExecutor.has_visible_output(delta):
            self.has_visible_output = True
            self.output_parts.append(str(delta or ""))
        if ToolExecutor.has_reasoning_output(reasoning_delta):
            self.has_reasoning_output = True
        if ToolExecutor.has_tool_calls(tool_calls):
            self.has_tool_calls = True
            for tool_call in tool_calls or []:
                if isinstance(tool_call, dict):
                    self.collected_tool_calls.append(tool_call)

        for progress_kind in progress_kinds or []:
            normalized = str(progress_kind or "").strip()
            if not normalized:
                continue
            self.has_progress_signal = True
            if normalized not in self.progress_kinds:
                self.progress_kinds.append(normalized)


class StreamObservationError(RuntimeError):
    def __init__(self, *, cause: Exception, observed: ObservedStream) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.observed = observed


class ProtocolRecoveryPolicy:
    _RATE_LIMIT_ERROR_CLASS_NAMES = recovery_semantics.RATE_LIMIT_ERROR_CLASS_NAMES
    _TIMEOUT_ERROR_CLASS_NAMES = recovery_semantics.TIMEOUT_ERROR_CLASS_NAMES
    _CONNECTION_ERROR_CLASS_NAMES = recovery_semantics.CONNECTION_ERROR_CLASS_NAMES
    _KNOWN_PARTIAL_FAILURE_REASONS = frozenset(
        {
            "provider_failure_after_partial_progress",
            "budget_exit",
            "tool_timeout",
            "tool_execution_error",
            "provider_timeout",
            "provider_rate_limit",
            "provider_unavailable",
            "provider_http_5xx",
            "provider_bad_response",
            "server_interrupt",
            "interrupted",
            "elapsed_budget_exceeded",
            "completion_budget_exceeded",
            "tool_round_budget_exceeded",
            "retry_budget_exhausted",
            "prompt_budget_exceeded",
            "tool_result_budget_exceeded",
            "candidate_tool_budget_exceeded",
        }
    )

    @staticmethod
    def response_blocks_fallback(response: ChatResponse) -> bool:
        return ToolExecutor.has_meaningful_chunk(
            delta=response.message.content,
            tool_calls=response.tool_calls or response.message.tool_calls,
        )

    @classmethod
    def partial_failure_reason(cls, exc: BaseException) -> str:
        for attr_name in (
            "partial_exit_reason",
            "termination_reason",
            "completion_reason",
            "provider_failure_kind",
            "failure_kind",
            "reason",
        ):
            value = getattr(exc, attr_name, None)
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized:
                continue
            if normalized in cls._KNOWN_PARTIAL_FAILURE_REASONS:
                return normalized
            if " " not in normalized:
                return normalized
        if "timeout" in exc.__class__.__name__.lower():
            return "tool_timeout"
        if exc.__class__.__name__ in {"CancelledError", "GeneratorExit"}:
            return "interrupted"
        return "provider_failure_after_partial_progress"

    @staticmethod
    def extract_status_code(exc: BaseException) -> int | None:
        return recovery_semantics.extract_status_code(exc)

    @classmethod
    def fallback_block_reason(cls, exc: BaseException) -> str | None:
        return recovery_semantics.fallback_block_reason(exc)

    @classmethod
    def should_skip_sync_rescue_after_stream_error(
        cls,
        error: BaseException | None,
    ) -> bool:
        return recovery_semantics.should_skip_sync_rescue_after_stream_error(error)

    @classmethod
    def should_cross_protocol_fallback_from_responses_error(
        cls,
        *,
        capabilities: Any,
        error: BaseException,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        use_responses_api: bool,
        fallback_switch_enabled: bool,
    ) -> bool:
        return recovery_semantics.should_cross_protocol_fallback_from_responses_error(
            capabilities=capabilities,
            error=error,
            tools=tools,
            tool_choice=tool_choice,
            use_responses_api=use_responses_api,
            fallback_switch_enabled=fallback_switch_enabled,
        )

    @staticmethod
    def extract_progress_kinds(metadata: dict[str, Any] | None) -> list[str]:
        if not isinstance(metadata, dict):
            return []

        return []

    @classmethod
    def chunk_is_meaningful(cls, chunk: ChatChunk) -> bool:
        return ToolExecutor.has_meaningful_chunk(
            delta=getattr(chunk, "delta", None),
            reasoning_delta=getattr(chunk, "reasoning_delta", None),
            tool_calls=getattr(chunk, "tool_calls", None),
        )

    @classmethod
    def chunk_should_emit_immediately(cls, chunk: ChatChunk) -> bool:
        if cls.extract_progress_kinds(getattr(chunk, "metadata", None)):
            return True
        return cls.chunk_is_meaningful(chunk)

    @staticmethod
    def empty_stream_reason(
        observed: ObservedStream,
        *,
        error_type: str | None = None,
    ) -> str:
        if error_type:
            if observed.has_progress_signal:
                return (
                    "stream_exception_after_progress_before_meaningful_chunk:"
                    f"{error_type}"
                )
            return f"stream_exception_before_first_meaningful_chunk:{error_type}"
        if observed.has_progress_signal:
            return "stream_progress_only_no_meaningful_output"
        return "stream_empty_no_output"

    @staticmethod
    def record_stream_failure_metadata(
        turn_record: TurnRecord,
        *,
        observed: ObservedStream,
        cause: Exception,
    ) -> None:
        turn_record.metadata["stream_failure_chunk_count"] = observed.chunk_count
        turn_record.metadata["stream_failure_has_meaningful_chunk"] = (
            observed.is_meaningful
        )
        turn_record.metadata["stream_failure_blocks_fallback"] = (
            observed.blocks_fallback
        )
        turn_record.metadata["stream_failure_error_type"] = type(cause).__name__
        if observed.has_progress_signal:
            turn_record.metadata[
                "stream_failure_after_progress_only"
            ] = not observed.is_meaningful
        if observed.has_reasoning_output and not observed.blocks_fallback:
            turn_record.metadata[
                "stream_failure_reasoning_only_before_visible_output"
            ] = True


__all__ = [
    "ObservedStream",
    "ProtocolRecoveryPolicy",
    "StreamObservationError",
]
