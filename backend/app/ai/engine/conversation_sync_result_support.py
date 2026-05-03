"""Sync execution result helpers for ConversationEngine.execute()."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.core.i18n import _
from app.core.response import resolve_public_error_message

from .conversation_result_projector import build_execution_result, build_turn_projection
from .execution_state_machine import ExecutionStateMachine
from .failure_classifier import FailureClassifier
from .final_output_policy import (
    is_trusted_assistant_final_output_source,
    resolve_skip_final_assistant,
)
from .recovery_manager import RecoveryManager
from .stream_handler import StreamExecutionHandler
from .types import ExecutionRequest, ExecutionResult

MessagesToDicts = Callable[[list[ChatMessage]], list[dict[str, Any]]]


def _assistant_message_metadata(
    action_buttons: list[dict[str, str]] | None,
) -> dict[str, Any] | None:
    if action_buttons:
        return {"action_buttons": action_buttons}
    return None


def _append_assistant_message(
    messages: list[ChatMessage],
    *,
    output: str,
    action_buttons: list[dict[str, str]] | None,
) -> None:
    messages.append(
        ChatMessage(
            role="assistant",
            content=output,
            metadata=_assistant_message_metadata(action_buttons),
        )
    )


def _append_assistant_message_if_missing(
    messages: list[ChatMessage],
    *,
    output: str,
    action_buttons: list[dict[str, str]] | None,
) -> None:
    if not output:
        return
    if messages:
        last_message = messages[-1]
        if (
            last_message.role == "assistant"
            and str(last_message.content or "").strip() == output.strip()
        ):
            return
    _append_assistant_message(
        messages,
        output=output,
        action_buttons=action_buttons,
    )


def _should_surface_exception_partial_output(provider_failure_kind: str) -> bool:
    # Sync callers have no prior streamed assistant body, so generated recovery
    # text should stay visible instead of collapsing into an empty assistant turn.
    return True


def _resolve_exception_final_output_source(
    *,
    partial_output: str,
    state: ExecutionStateMachine | None,
    tool_results: list[ToolResult],
) -> str | None:
    if not str(partial_output or "").strip():
        return None
    intent_plan = list(state.intent_plan) if state is not None else []
    if RecoveryManager.has_completed_output_evidence(
        intent_plan,
        tool_results=tool_results,
    ):
        return "recovery_evidence"
    return "partial_output"


def build_sync_success_result(
    *,
    output: str,
    response: ChatResponse | None,
    messages: list[ChatMessage],
    tool_results: list[ToolResult],
    total_tokens: int,
    start_time: float,
    request: ExecutionRequest,
    prep: Any,
    state: ExecutionStateMachine,
    paused_for_consent: bool,
    partial: bool,
    completion_reason: str | None,
    final_output_source: str | None,
    messages_to_dicts: MessagesToDicts,
) -> ExecutionResult:
    cleaned_output, action_buttons = StreamExecutionHandler._extract_action_buttons(
        output
    )
    if action_buttons:
        output = cleaned_output

    response_metadata = dict(getattr(response, "metadata", {}) or {})
    skip_final_assistant = resolve_skip_final_assistant(
        response_metadata=response_metadata,
        paused_for_consent=paused_for_consent,
    )
    allow_final_output_append = partial or is_trusted_assistant_final_output_source(
        final_output_source
    )
    if output and not skip_final_assistant and allow_final_output_append:
        _append_assistant_message(
            messages,
            output=output,
            action_buttons=action_buttons,
        )

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    turn_projection = build_turn_projection(
        raw_turn_record=response_metadata.get("runtime_turn_record"),
        diagnostics_payload=state.build_diagnostics_payload(),
        execution_path=prep.execution_path,
        completion_reason=completion_reason,
        partial=partial,
        final_output_source=final_output_source,
    )
    result = build_execution_result(
        success=not partial,
        output=output,
        messages=messages_to_dicts(messages),
        tool_results=tool_results,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        conversation_id=request.conversation_id,
        runtime_model_info=response_metadata.get("runtime_model_info"),
        error="" if not partial else output,
        partial=partial,
        interrupted=paused_for_consent,
        completion_reason=completion_reason,
        rag_sources=prep.rag_sources,
        rag_source_kinds=prep.rag_source_kinds,
        context_compacted=prep.context_compacted,
        memory_flush_triggered=prep.memory_flush_triggered,
        memory_recalled=prep.memory_recalled,
        prune_stats=prep.prune_stats,
        tool_planner=prep.tool_planner,
        turn_projection=turn_projection,
        intent_plan=list(state.intent_plan),
        execution_path=prep.execution_path,
        execution_budget=(
            state.budget.snapshot() if state.budget is not None else None
        ),
        recovery_history=[
            decision_item.to_dict() for decision_item in state.recovery_history
        ],
        provider_failure_kind=state.provider_failure_kind,
        provider_events=list(state.provider_events),
    )
    if paused_for_consent:
        result.success = False
    return result


def build_sync_exception_result(
    *,
    exc: Exception,
    request: ExecutionRequest,
    messages: list[ChatMessage],
    tool_results: list[ToolResult],
    state: ExecutionStateMachine | None,
    prep: Any | None,
    start_time: float,
    messages_to_dicts: MessagesToDicts,
) -> ExecutionResult:
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    kind, event = FailureClassifier.classify_exception(exc)
    partial_output = ""
    diagnostics_payload: dict[str, Any] | None = None
    decision = None
    if state is not None and kind != "none":
        state.transition("failed" if kind != "budget_exit" else "partial_exit")
        state.register_provider_failure(kind=kind, event=event or None)
        diagnostics_payload = state.build_diagnostics_payload()
        decision = RecoveryManager.decide(
            state.intent_plan,
            budget=state.budget,
            provider_failure_kind=state.provider_failure_kind,
        )
        if decision is not None:
            partial_output = RecoveryManager.build_partial_output(
                state.intent_plan,
                tool_results=tool_results,
                reason=decision.reason or "execution_exception",
                provider_failure_kind=state.provider_failure_kind,
            )
            state.preparation_diagnostics["final_output_source"] = (
                _resolve_exception_final_output_source(
                    partial_output=partial_output,
                    state=state,
                    tool_results=tool_results,
                )
            )

    recovered_from_provider_failure = False
    recovered_provider_failure_kind = ""
    recovered_provider_events: list[dict[str, Any]] = []
    if state is not None:
        recovered_provider_failure_kind = str(state.provider_failure_kind or "").strip()
        recovered_provider_events = list(state.provider_events or [])
        recovered_intents, recovered_output = (
            RecoveryManager.recover_web_search_output_from_evidence(
                list(state.intent_plan or []),
                tool_results=tool_results,
            )
        )
        if recovered_output:
            recovered_from_provider_failure = True
            partial_output = recovered_output
            state.intent_plan = recovered_intents
            state.preparation_diagnostics.update(
                {
                    "final_output_source": "recovery_evidence",
                    "provider_failure_recovered_from_tool_evidence": True,
                    "recovered_provider_failure_kind": recovered_provider_failure_kind,
                    "recovered_provider_events": recovered_provider_events,
                }
            )
            state.provider_failure_kind = "none"
            state.provider_events = []
            state.transition("completed")
            diagnostics_payload = state.build_diagnostics_payload()

    if (
        state is not None
        and not partial_output
        and RecoveryManager.has_completed_output_evidence(
            list(state.intent_plan or []),
            tool_results=tool_results,
        )
    ):
        partial_output = str(
            RecoveryManager.build_completed_output(
                list(state.intent_plan or []),
                tool_results=tool_results,
                reason="provider_failure_recovery",
            )
            or ""
        ).strip()

    final_output_source = _resolve_exception_final_output_source(
        partial_output=partial_output,
        state=state,
        tool_results=tool_results,
    )
    if recovered_from_provider_failure:
        final_output_source = "recovery_evidence"
    elif (
        state is not None
        and final_output_source == "recovery_evidence"
        and partial_output
    ):
        recovered_from_provider_failure = True
        state.preparation_diagnostics.update(
            {
                "provider_failure_recovered_from_tool_evidence": True,
                "recovered_provider_failure_kind": recovered_provider_failure_kind,
                "recovered_provider_events": recovered_provider_events,
            }
        )
        state.provider_failure_kind = "none"
        state.provider_events = []
        state.transition("completed")
        diagnostics_payload = state.build_diagnostics_payload()
    surfaced_output = (
        partial_output
        if (
            _should_surface_exception_partial_output(kind)
            or is_trusted_assistant_final_output_source(final_output_source)
        )
        else ""
    )
    if surfaced_output and recovered_from_provider_failure:
        _append_assistant_message_if_missing(
            messages,
            output=surfaced_output,
            action_buttons=None,
        )

    completion_reason = (
        decision.reason
        if partial_output and decision is not None and decision.reason
        else "error"
    )
    turn_projection = build_turn_projection(
        raw_turn_record=None,
        diagnostics_payload=diagnostics_payload or {},
        execution_path=(prep.execution_path if prep is not None else None),
        completion_reason=(
            "completed" if recovered_from_provider_failure else completion_reason
        ),
        partial=bool(partial_output) and not recovered_from_provider_failure,
        final_output_source=final_output_source,
        default_turn_outcome="success" if recovered_from_provider_failure else None,
        force_completion_reason_in_turn_record=recovered_from_provider_failure,
    )
    return build_execution_result(
        success=recovered_from_provider_failure,
        output=surfaced_output,
        messages=(messages_to_dicts(messages) if messages else []),
        tool_results=tool_results,
        total_tokens=0,
        duration_ms=duration_ms,
        conversation_id=request.conversation_id,
        runtime_model_info=None,
        error=(
            ""
            if recovered_from_provider_failure
            else resolve_public_error_message(
                exc,
                fallback_message=_("common.server_error"),
            )
        ),
        partial=bool(partial_output) and not recovered_from_provider_failure,
        completion_reason=(
            "completed" if recovered_from_provider_failure else completion_reason
        ),
        rag_sources=(prep.rag_sources if prep is not None else None),
        rag_source_kinds=(prep.rag_source_kinds if prep is not None else []),
        context_compacted=bool(getattr(prep, "context_compacted", False)),
        memory_flush_triggered=bool(getattr(prep, "memory_flush_triggered", False)),
        memory_recalled=bool(getattr(prep, "memory_recalled", False)),
        prune_stats=getattr(prep, "prune_stats", None),
        tool_planner=getattr(prep, "tool_planner", None),
        turn_projection=turn_projection,
        intent_plan=list(state.intent_plan) if state is not None else [],
        execution_path=(prep.execution_path if prep is not None else None),
        execution_budget=(
            state.budget.snapshot()
            if state is not None and state.budget is not None
            else None
        ),
        recovery_history=[
            decision_item.to_dict()
            for decision_item in (state.recovery_history if state else [])
        ],
        provider_failure_kind="none" if recovered_from_provider_failure else kind,
        provider_events=[]
        if recovered_from_provider_failure
        else ([event] if event else []),
    )


__all__ = [
    "build_sync_exception_result",
    "build_sync_success_result",
]
