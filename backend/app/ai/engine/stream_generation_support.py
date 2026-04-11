"""Focused helpers for StreamExecutionHandler.generate()."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage

from .conversation_result_projector import (
    build_execution_result,
    build_turn_projection,
    coerce_turn_record_payload,
)
from .final_output_policy import resolve_skip_final_assistant
from .recovery_manager import RecoveryManager
from .stream_error_utils import trace_payload as _trace_payload
from .stream_generation_view import ensure_stream_generation_view
from .types import ExecutionResult

if TYPE_CHECKING:
    from .turn_executor import TurnExecutionResult


@dataclass(slots=True)
class StreamFinalizationArtifacts:
    result: ExecutionResult
    diagnostics_payload: dict[str, Any]
    response_metadata: dict[str, Any]
    resolved_protocol_path: str
    immediate_events: list[str] = field(default_factory=list)
    replay_events: list[str] = field(default_factory=list)


def _resolve_generation_view(handler: Any) -> Any:
    explicit = getattr(handler, "_stream_generation_view", None)
    if callable(explicit):
        return explicit()
    return ensure_stream_generation_view(handler)


def reset_stream_state(handler: Any) -> None:
    _resolve_generation_view(handler).reset_runtime_state()


def build_initial_events(
    handler: Any,
    *,
    optimize_event: Any,
) -> list[str]:
    view = _resolve_generation_view(handler)
    request = view.request
    events: list[str] = []

    if request.conversation_id:
        events.append(
            SSEChunkEncoder.encode(
                _trace_payload(
                    {
                        "event": "conversation",
                        "conversation_id": request.conversation_id,
                    }
                )
            )
        )

    current_page_context = (
        request.input_variables.get("page_context")
        if isinstance(getattr(request, "input_variables", None), dict)
        else None
    )
    if isinstance(current_page_context, dict):
        view.update_turn_progress(
            last_page_key=str(current_page_context.get("page_key") or "").strip() or None
        )

    kb_feedback = getattr(request, "knowledge_base_feedback", None)
    if isinstance(kb_feedback, dict) and kb_feedback.get("dropped_knowledge_base_ids"):
        events.append(
            SSEChunkEncoder.encode(
                _trace_payload(
                    {
                        "event": "knowledge_base_feedback",
                        **kb_feedback,
                    }
                )
            )
        )

    if optimize_event is not None:
        events.append(
            SSEChunkEncoder.encode(
                {"event": "optimizing_tools", **optimize_event}
                if isinstance(optimize_event, dict)
                else optimize_event
            )
        )

    return events


async def drain_runtime_events(
    handler: Any,
    *,
    executor_task: asyncio.Task[Any],
    wait_timeout: float = 0.05,
    keepalive_interval_ticks: int = 300,
) -> AsyncIterator[str]:
    queue = _resolve_generation_view(handler).event_queue
    keepalive_counter = 0
    while True:
        if executor_task.done() and queue.empty():
            break
        try:
            queued_event = await asyncio.wait_for(
                queue.get(),
                timeout=wait_timeout,
            )
        except asyncio.TimeoutError:
            keepalive_counter += 1
            if keepalive_counter >= keepalive_interval_ticks:
                keepalive_counter = 0
                yield SSEChunkEncoder.keepalive()
            continue

        keepalive_counter = 0
        yield queued_event


def sync_response_runtime_metadata(
    handler: Any,
    *,
    response: Any,
) -> dict[str, Any]:
    view = _resolve_generation_view(handler)
    response_metadata = (
        dict(getattr(response, "metadata", {}) or {})
        if response is not None
        else {}
    )
    runtime_model_info = response_metadata.get("runtime_model_info")
    if isinstance(runtime_model_info, dict):
        view.runtime_model_info = dict(runtime_model_info)
    view.replace_runtime_turn_record(
        response_metadata.get("runtime_turn_record"),
    )
    return response_metadata


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
    action_buttons: list[dict[str, str]] | None = None,
    reasoning_content: str | None = None,
) -> None:
    messages.append(
        ChatMessage(
            role="assistant",
            content=output,
            reasoning_content=reasoning_content,
            metadata=_assistant_message_metadata(action_buttons),
        )
    )


def _resolve_turn_output(
    *,
    visible_assistant_output: str,
    streamed_output: str,
    stream_local_output: str,
    finalized_output: str,
) -> str:
    if finalized_output:
        return finalized_output
    if visible_assistant_output:
        return visible_assistant_output
    if stream_local_output:
        return stream_local_output
    return streamed_output


def _append_output_if_missing(
    *,
    handler: Any,
    messages: list[ChatMessage],
    current_turn_messages: list[ChatMessage],
    output: str,
    streamed_output: str,
    action_buttons: list[dict[str, str]] | None,
    skip_final_assistant: bool = False,
    reasoning_content: str | None = None,
) -> None:
    view = _resolve_generation_view(handler)
    if not output or skip_final_assistant:
        return
    current_turn_has_output = view.current_turn_has_finalized_output(
        messages=current_turn_messages,
        streamed_output=streamed_output,
        finalized_output=str(output or "").strip(),
    )
    if current_turn_has_output:
        return
    _append_assistant_message(
        messages,
        output=output,
        action_buttons=action_buttons,
        reasoning_content=reasoning_content,
    )


def _finalize_partial_output(
    handler: Any,
    *,
    messages: list[ChatMessage],
    turn_start_message_index: int,
    output: str,
    tool_results: list[Any],
    action_buttons: list[dict[str, str]] | None,
    completion_reason: str,
) -> tuple[str, list[str]]:
    view = _resolve_generation_view(handler)
    current_turn_messages = messages[turn_start_message_index:]
    visible_assistant_output = view.last_visible_assistant_content(current_turn_messages)
    streamed_output = view.visible_stream_content.strip()
    stream_local_output = view.output.strip()
    finalized_output = str(output or "").strip()
    output = _resolve_turn_output(
        visible_assistant_output=visible_assistant_output,
        streamed_output=streamed_output,
        stream_local_output=stream_local_output,
        finalized_output=finalized_output,
    )
    if not output and view.provider_failure_kind == "budget_exit":
        output = view.build_budget_exit_fallback_output(tool_results=tool_results)
    elif not output:
        output = RecoveryManager.build_partial_output(
            view.intent_plan,
            reason=completion_reason or "return_partial",
            provider_failure_kind=view.provider_failure_kind,
        )

    view.output = output
    _append_output_if_missing(
        handler=handler,
        messages=messages,
        current_turn_messages=current_turn_messages,
        output=output,
        streamed_output=streamed_output,
        action_buttons=action_buttons,
    )

    if view.should_replay_finalized_output(
        streamed_output=streamed_output,
        finalized_output=str(output or "").strip(),
    ):
        return output, view.chunk_text_for_streaming(output)
    return output, []


def _finalize_paused_output(
    handler: Any,
    *,
    messages: list[ChatMessage],
    turn_start_message_index: int,
    action_buttons: list[dict[str, str]] | None,
    skip_final_assistant: bool,
) -> tuple[str, list[str]]:
    view = ensure_stream_generation_view(handler)
    current_turn_messages = messages[turn_start_message_index:]
    visible_assistant_output = view.last_visible_assistant_content(current_turn_messages)
    streamed_output = view.visible_stream_content.strip()
    output = _resolve_turn_output(
        visible_assistant_output=visible_assistant_output,
        streamed_output=streamed_output,
        stream_local_output=view.output.strip(),
        finalized_output="",
    )

    view.output = output
    _append_output_if_missing(
        handler=handler,
        messages=messages,
        current_turn_messages=current_turn_messages,
        output=output,
        streamed_output=streamed_output,
        action_buttons=action_buttons,
        skip_final_assistant=skip_final_assistant,
    )

    if view.should_replay_finalized_output(
        streamed_output=streamed_output,
        finalized_output=str(output or "").strip(),
    ):
        return output, view.chunk_text_for_streaming(output)
    return output, []


def _finalize_completed_output(
    handler: Any,
    *,
    messages: list[ChatMessage],
    output: str,
    response: Any,
    action_buttons: list[dict[str, str]] | None,
    final_output_source: str | None,
) -> tuple[str, list[str]]:
    view = ensure_stream_generation_view(handler)
    streamed_output = view.visible_stream_content.strip()
    finalized_output = str(output or "").strip()
    if view.should_preserve_streamed_assistant_output(
        final_output_source=final_output_source,
        streamed_output=streamed_output,
        finalized_output=finalized_output,
    ):
        output = streamed_output
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = streamed_output

    reasoning_content = (
        str(
            getattr(getattr(response, "message", None), "reasoning_content", None)
            or view.reasoning_output
            or ""
        ).strip()
        or None
    )
    _append_output_if_missing(
        handler=handler,
        messages=messages,
        current_turn_messages=messages,
        output=output,
        streamed_output=streamed_output,
        action_buttons=action_buttons,
        reasoning_content=reasoning_content,
    )

    if output != streamed_output:
        return output, view.chunk_text_for_streaming(output)
    return output, []


def _build_result_turn_record(
    handler: Any,
    *,
    diagnostics_payload: dict[str, Any],
    response_metadata: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    view = _resolve_generation_view(handler)
    raw_turn_record = view.runtime_turn_record
    view.refresh_runtime_turn_record()
    refreshed_turn_record = coerce_turn_record_payload(view.runtime_turn_record)
    if raw_turn_record is not None:
        raw_payload = coerce_turn_record_payload(raw_turn_record)
        if raw_payload:
            raw_payload.update(refreshed_turn_record)
            result_turn_record = raw_payload
        else:
            result_turn_record = refreshed_turn_record
    else:
        result_turn_record = refreshed_turn_record
    resolved_protocol_path = view.resolved_protocol_path(
        diagnostics_payload=diagnostics_payload,
        turn_record=result_turn_record,
        response_metadata=response_metadata,
    )
    return result_turn_record, resolved_protocol_path


def _encode_message_events(chunks: list[str]) -> list[str]:
    return [
        SSEChunkEncoder.encode(
            {
                "event": "message",
                "delta": chunk,
            }
        )
        for chunk in chunks
    ]


def _build_replay_events(
    handler: Any,
    *,
    output: str,
    final_output_source: str | None,
    partial_reply_stream_chunks: list[str],
    completed_reply_stream_chunks: list[str],
) -> list[str]:
    streamed_output = _resolve_generation_view(handler).visible_stream_content.strip()
    should_clear_replayed_output = _should_clear_replayed_output(
        streamed_output=streamed_output,
        finalized_output=str(output or "").strip(),
        final_output_source=final_output_source,
        partial_reply_stream_chunks=partial_reply_stream_chunks,
        completed_reply_stream_chunks=completed_reply_stream_chunks,
    )

    events: list[str] = []
    if should_clear_replayed_output:
        events.append(SSEChunkEncoder.encode({"event": "clear_content"}))
    events.extend(_encode_message_events(partial_reply_stream_chunks))
    events.extend(_encode_message_events(completed_reply_stream_chunks))
    return events


def _should_clear_replayed_output(
    *,
    streamed_output: str,
    finalized_output: str,
    final_output_source: str | None,
    partial_reply_stream_chunks: list[str],
    completed_reply_stream_chunks: list[str],
) -> bool:
    return bool(
        streamed_output
        and finalized_output
        and finalized_output != streamed_output
        and final_output_source in {"tool_evidence_completed", "budget_fallback"}
        and (partial_reply_stream_chunks or completed_reply_stream_chunks)
    )


def _resolve_done_turn_outcome(
    *,
    diagnostics_payload: dict[str, Any] | None,
    turn_record: dict[str, Any] | None,
) -> Any:
    if isinstance(diagnostics_payload, dict) and diagnostics_payload.get("turn_outcome"):
        return diagnostics_payload.get("turn_outcome")
    if isinstance(turn_record, dict):
        return turn_record.get("turn_outcome")
    return None


def finalize_successful_turn(
    handler: Any,
    *,
    messages: list[ChatMessage],
    rag_sources: list[dict[str, Any]] | None,
    turn_start_message_index: int,
    turn_execution: TurnExecutionResult,
    logger: Any,
) -> StreamFinalizationArtifacts:
    view = _resolve_generation_view(handler)
    output = turn_execution.output
    total_tokens = turn_execution.total_tokens
    tool_results = list(turn_execution.tool_results)
    view.completion_tokens_used = turn_execution.completion_tokens_used
    response = turn_execution.response
    response_metadata = sync_response_runtime_metadata(handler, response=response)

    cleaned_output, action_buttons = view.extract_action_buttons(output)
    immediate_events: list[str] = []
    if action_buttons:
        output = cleaned_output
        immediate_events.append(
            SSEChunkEncoder.encode(
                {
                    "event": "action_buttons",
                    "buttons": action_buttons,
                }
            )
        )
    if rag_sources:
        immediate_events.append(
            SSEChunkEncoder.encode(
                {
                    "event": "rag_sources",
                    "sources": rag_sources,
                }
            )
        )

    duration_ms = int((time.perf_counter() - view.start_time) * 1000)
    partial = bool(turn_execution.partial)
    paused_for_consent = bool(turn_execution.paused_for_consent)
    completion_reason = turn_execution.completion_reason or "completed"
    final_output_source = turn_execution.final_output_source
    skip_final_assistant = resolve_skip_final_assistant(
        response_metadata=response_metadata,
        paused_for_consent=paused_for_consent,
    )
    partial_reply_stream_chunks: list[str] = []
    completed_reply_stream_chunks: list[str] = []

    if partial:
        output, partial_reply_stream_chunks = _finalize_partial_output(
            handler,
            messages=messages,
            turn_start_message_index=turn_start_message_index,
            output=output,
            tool_results=tool_results,
            action_buttons=action_buttons,
            completion_reason=completion_reason,
        )
    elif paused_for_consent:
        output, partial_reply_stream_chunks = _finalize_paused_output(
            handler,
            messages=messages,
            turn_start_message_index=turn_start_message_index,
            action_buttons=action_buttons,
            skip_final_assistant=skip_final_assistant,
        )
    elif output and not skip_final_assistant:
        output, completed_reply_stream_chunks = _finalize_completed_output(
            handler,
            messages=messages,
            output=output,
            response=response,
            action_buttons=action_buttons,
            final_output_source=final_output_source,
        )

    diagnostics_payload = view.build_diagnostics_payload()
    diagnostics_payload["final_output_source"] = final_output_source
    result_turn_record, resolved_protocol_path = _build_result_turn_record(
        handler,
        diagnostics_payload=diagnostics_payload,
        response_metadata=response_metadata,
    )
    turn_projection = build_turn_projection(
        raw_turn_record=result_turn_record,
        diagnostics_payload=diagnostics_payload,
        execution_path=view.execution_path,
        completion_reason=completion_reason,
        partial=partial,
        final_output_source=final_output_source,
        protocol_path=resolved_protocol_path,
    )
    diagnostics_payload = turn_projection.diagnostics

    result = build_execution_result(
        success=not partial,
        output=output,
        messages=view.messages_to_dicts(messages),
        tool_results=tool_results,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        conversation_id=view.request.conversation_id,
        runtime_model_info=view.runtime_model_info,
        partial=partial,
        interrupted=paused_for_consent,
        completion_reason=completion_reason,
        rag_sources=rag_sources,
        rag_source_kinds=view.rag_source_kinds,
        context_compacted=view.context_compacted,
        memory_flush_triggered=view.memory_flush_triggered,
        memory_recalled=view.memory_recalled,
        prune_stats=view.prune_stats,
        tool_planner=view.tool_planner,
        turn_projection=turn_projection,
        intent_plan=view.intent_plan,
        execution_path=view.execution_path,
        execution_budget=view.budget_snapshot,
        recovery_history=view.recovery_history_dicts,
        provider_failure_kind=view.provider_failure_kind,
        provider_events=view.provider_events,
    )
    if completion_reason == "length":
        logger.warning(
            "Response hit output length limit: agent={} model={} total_tokens={} conversation_id={}",
            view.request.agent_id,
            (view.runtime_model_info or {}).get("model_name"),
            total_tokens,
            view.request.conversation_id,
        )

    if paused_for_consent:
        result.success = False

    replay_events = _build_replay_events(
        handler,
        output=output,
        final_output_source=final_output_source,
        partial_reply_stream_chunks=partial_reply_stream_chunks,
        completed_reply_stream_chunks=completed_reply_stream_chunks,
    )
    return StreamFinalizationArtifacts(
        result=result,
        diagnostics_payload=diagnostics_payload,
        response_metadata=response_metadata,
        resolved_protocol_path=resolved_protocol_path,
        immediate_events=immediate_events,
        replay_events=replay_events,
    )


def build_done_event(
    handler: Any,
    *,
    artifacts: StreamFinalizationArtifacts,
    on_complete_extra: dict[str, Any] | None,
) -> str:
    view = _resolve_generation_view(handler)
    return SSEChunkEncoder.encode(
        _trace_payload(
            {
                "event": "done",
                "conversation_id": view.request.conversation_id,
                "total_tokens": artifacts.result.total_tokens,
                "duration_ms": artifacts.result.duration_ms,
                "context_compacted": artifacts.result.context_compacted,
                "memory_flush_triggered": artifacts.result.memory_flush_triggered,
                "memory_recalled": artifacts.result.memory_recalled,
                "prune_stats": artifacts.result.prune_stats,
                "rag_source_kinds": artifacts.result.rag_source_kinds,
                "turn_record": artifacts.result.turn_record
                or artifacts.diagnostics_payload,
                "turn_outcome": _resolve_done_turn_outcome(
                    diagnostics_payload=artifacts.diagnostics_payload,
                    turn_record=artifacts.result.turn_record,
                ),
                "termination_reason": artifacts.result.completion_reason,
                "protocol_path": artifacts.resolved_protocol_path,
                "selected_tool_names": (
                    artifacts.diagnostics_payload.get("selected_tool_names")
                    if isinstance(artifacts.diagnostics_payload, dict)
                    else None
                ),
                "selected_skill_names": (
                    artifacts.diagnostics_payload.get("selected_skill_names")
                    if isinstance(artifacts.diagnostics_payload, dict)
                    else None
                ),
                "context_sources": (
                    artifacts.diagnostics_payload.get("context_sources")
                    if isinstance(artifacts.diagnostics_payload, dict)
                    else None
                ),
                **(on_complete_extra or {}),
            }
        )
    )


def append_partial_assistant_output(
    messages: list[ChatMessage],
    *,
    output: str,
    reasoning_output: str | None,
) -> None:
    if not output:
        return
    messages.append(
        ChatMessage(
            role="assistant",
            content=output,
            reasoning_content=(str(reasoning_output or "").strip() or None),
        )
    )


def build_terminal_result(
    handler: Any,
    *,
    messages: list[ChatMessage],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    tool_results: list[Any],
    duration_ms: int,
    error: str,
    completion_reason: str,
    interrupted: bool,
    include_provider_state: bool,
) -> ExecutionResult:
    view = _resolve_generation_view(handler)
    view.refresh_runtime_turn_record()
    diagnostics_payload = view.build_diagnostics_payload()
    final_output_source = diagnostics_payload.get("final_output_source")
    result_turn_record, resolved_protocol_path = _build_result_turn_record(
        handler,
        diagnostics_payload=diagnostics_payload,
        response_metadata={},
    )
    turn_projection = build_turn_projection(
        raw_turn_record=result_turn_record,
        diagnostics_payload=diagnostics_payload,
        execution_path=view.execution_path,
        completion_reason=completion_reason,
        partial=True,
        final_output_source=final_output_source,
        protocol_path=resolved_protocol_path,
    )

    return build_execution_result(
        success=False,
        output=output,
        messages=view.messages_to_dicts(messages),
        tool_results=tool_results,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        conversation_id=view.request.conversation_id,
        runtime_model_info=view.runtime_model_info,
        error=error,
        partial=True,
        interrupted=interrupted,
        completion_reason=completion_reason,
        rag_sources=rag_sources,
        rag_source_kinds=view.rag_source_kinds,
        context_compacted=view.context_compacted,
        memory_flush_triggered=view.memory_flush_triggered,
        memory_recalled=view.memory_recalled,
        prune_stats=view.prune_stats,
        tool_planner=view.tool_planner,
        turn_projection=turn_projection,
        intent_plan=view.intent_plan,
        execution_path=view.execution_path,
        execution_budget=view.budget_snapshot,
        recovery_history=view.recovery_history_dicts,
        provider_failure_kind=(
            view.provider_failure_kind or "none"
            if include_provider_state
            else "none"
        ),
        provider_events=(view.provider_events if include_provider_state else None),
    )


__all__ = [
    "StreamFinalizationArtifacts",
    "append_partial_assistant_output",
    "build_done_event",
    "build_initial_events",
    "build_terminal_result",
    "drain_runtime_events",
    "finalize_successful_turn",
    "reset_stream_state",
    "sync_response_runtime_metadata",
]
