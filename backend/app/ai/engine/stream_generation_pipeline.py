# FROZEN: do not add new dependencies
"""Focused helpers for StreamExecutionHandler.generate()."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage
from app.core.i18n import _

from .conversation_result_projector import build_execution_result, build_turn_projection
from .final_output_policy import (
    build_untrusted_final_output_fallback,
    is_trusted_assistant_final_output_source,
    resolve_skip_final_assistant,
)
from .recovery_manager import RecoveryManager
from .stream_error_utils import trace_payload as _trace_payload
from .stream_finalization_pipeline import (
    StreamFinalizationArtifacts,
    build_done_event_payload,
    build_result_turn_record,
)
from .stream_generation_view import build_stream_generation_view
from .stream_replay_events import (
    build_immediate_turn_events,
    build_replay_events,
)
from .turn_flow_projector import (
    build_initial_turn_flow_events,
    build_turn_answer_card_event,
    build_turn_flow_view_model,
)
from .types import ExecutionResult

if TYPE_CHECKING:
    from .turn_executor import TurnExecutionResult


_PARTIAL_FAILURE_COMPLETION_REASONS = frozenset(
    {
        "error",
        "provider_failure_after_partial_progress",
        "provider_timeout",
        "provider_unavailable",
        "provider_error",
        "tool_error",
        "tool_round_failed",
        "stream_execution_error",
        "terminal_failure",
    }
)


def _resolve_generation_view(handler: Any) -> Any:
    explicit = getattr(handler, "_stream_generation_view", None)
    if callable(explicit):
        return explicit()
    return build_stream_generation_view(handler)


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

    for canonical_event in build_initial_turn_flow_events(
        optimize_event=optimize_event
    ):
        events.append(SSEChunkEncoder.encode(_trace_payload(canonical_event)))

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
        dict(getattr(response, "metadata", {}) or {}) if response is not None else {}
    )
    runtime_model_info = response_metadata.get("runtime_model_info")
    if isinstance(runtime_model_info, dict):
        view.runtime_model_info = dict(runtime_model_info)
    view.replace_runtime_turn_record(
        response_metadata.get("runtime_turn_record"),
    )
    return response_metadata


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
            metadata={"action_buttons": action_buttons} if action_buttons else None,
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


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_partial_failure_salvage_risk(
    *,
    completion_reason: str,
    provider_failure_kind: str | None,
) -> bool:
    normalized_reason = _normalize_token(completion_reason)
    normalized_failure_kind = _normalize_token(provider_failure_kind)
    if normalized_reason in _PARTIAL_FAILURE_COMPLETION_REASONS:
        return True
    return bool(
        normalized_failure_kind
        and normalized_failure_kind not in {"none", "budget_exit"}
    )


def _outputs_overlap(left: str, right: str) -> bool:
    normalized_left = str(left or "").strip()
    normalized_right = str(right or "").strip()
    if not normalized_left or not normalized_right:
        return False
    return (
        normalized_left == normalized_right
        or normalized_left.startswith(normalized_right)
        or normalized_right.startswith(normalized_left)
    )


def _resolve_trustworthy_partial_failure_output(
    *,
    finalized_output: str,
    visible_assistant_output: str,
    streamed_output: str,
) -> str:
    if finalized_output and (
        _outputs_overlap(finalized_output, visible_assistant_output)
        or _outputs_overlap(finalized_output, streamed_output)
    ):
        return finalized_output
    if visible_assistant_output and (
        not streamed_output
        or _outputs_overlap(visible_assistant_output, streamed_output)
    ):
        return visible_assistant_output
    if streamed_output:
        return streamed_output
    return ""


def _safe_partial_failure_output() -> str:
    return str(_("common.server_error") or "").strip() or (
        "The assistant could not finish this turn. Please retry."
    )


def _is_generic_untrusted_fallback_output(output: str) -> bool:
    normalized_output = str(output or "").strip()
    if not normalized_output:
        return False
    return normalized_output == build_untrusted_final_output_fallback()


def _recover_completed_output_from_evidence(
    view: Any,
    *,
    finalized_output: str,
    trusted_stream_output: str,
    tool_results: list[Any] | None,
) -> tuple[str, str | None]:
    if trusted_stream_output:
        return "", None
    if not _is_generic_untrusted_fallback_output(finalized_output):
        return "", None

    intent_plan = list(view.intent_plan or [])
    if not RecoveryManager.has_completed_output_evidence(
        intent_plan,
        tool_results=list(tool_results or []),
    ):
        return "", None

    recovered_output = str(
        RecoveryManager.build_completed_output(
            intent_plan,
            tool_results=list(tool_results or []),
            reason="completed",
        )
        or ""
    ).strip()
    if not recovered_output or _is_generic_untrusted_fallback_output(recovered_output):
        return "", None
    return recovered_output, "recovery_evidence"


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
    visible_assistant_output = view.last_visible_assistant_content(
        current_turn_messages
    )
    streamed_output = view.visible_stream_content.strip()
    stream_local_output = view.output.strip()
    finalized_output = str(output or "").strip()
    output = _resolve_turn_output(
        visible_assistant_output=visible_assistant_output,
        streamed_output=streamed_output,
        stream_local_output=stream_local_output,
        finalized_output=finalized_output,
    )
    failure_salvage_risk = _is_partial_failure_salvage_risk(
        completion_reason=completion_reason,
        provider_failure_kind=view.provider_failure_kind,
    )
    if failure_salvage_risk:
        output = _resolve_trustworthy_partial_failure_output(
            finalized_output=finalized_output,
            visible_assistant_output=visible_assistant_output,
            streamed_output=streamed_output,
        )
    if not output and view.provider_failure_kind == "budget_exit":
        output = view.build_budget_exit_fallback_output(tool_results=tool_results)
    elif not output:
        if failure_salvage_risk:
            output = _safe_partial_failure_output()
        else:
            output = RecoveryManager.build_partial_output(
                view.intent_plan,
                tool_results=tool_results,
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
    view = _resolve_generation_view(handler)
    current_turn_messages = messages[turn_start_message_index:]
    visible_assistant_output = view.last_visible_assistant_content(
        current_turn_messages
    )
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
    turn_start_message_index: int,
    output: str,
    response: Any,
    tool_results: list[Any] | None,
    action_buttons: list[dict[str, str]] | None,
    final_output_source: str | None,
) -> tuple[str, list[str], str | None]:
    view = _resolve_generation_view(handler)
    current_turn_messages = messages[turn_start_message_index:]
    streamed_output = view.visible_stream_content.strip()
    finalized_output = str(output or "").strip()
    trusted_final_source = is_trusted_assistant_final_output_source(final_output_source)
    if not trusted_final_source:
        trusted_stream_output = (
            view.last_visible_assistant_content(current_turn_messages)
            or streamed_output
        )
        state_source = getattr(view.state, "_source", None)
        diagnostics_payload = getattr(state_source, "preparation_diagnostics", {}) or {}
        safe_untrusted_fallback_available = bool(
            diagnostics_payload.get("untrusted_final_output_fallback_applied")
            or diagnostics_payload.get("stripped_untrusted_final_output")
        )
        recovered_output, recovered_output_source = (
            _recover_completed_output_from_evidence(
                view,
                finalized_output=finalized_output,
                trusted_stream_output=trusted_stream_output,
                tool_results=tool_results,
            )
        )
        if recovered_output:
            output = recovered_output
            if response is not None and getattr(response, "message", None) is not None:
                response.message.content = recovered_output
            _append_output_if_missing(
                handler=handler,
                messages=messages,
                current_turn_messages=current_turn_messages,
                output=recovered_output,
                streamed_output=streamed_output,
                action_buttons=action_buttons,
                skip_final_assistant=False,
            )
            replay_chunks = (
                view.chunk_text_for_streaming(recovered_output)
                if view.should_replay_finalized_output(
                    streamed_output=streamed_output,
                    finalized_output=recovered_output,
                )
                else []
            )
            return output, replay_chunks, recovered_output_source
        if (
            finalized_output
            and not trusted_stream_output
            and safe_untrusted_fallback_available
        ):
            output = finalized_output
            if response is not None and getattr(response, "message", None) is not None:
                response.message.content = finalized_output
            _append_output_if_missing(
                handler=handler,
                messages=messages,
                current_turn_messages=current_turn_messages,
                output=finalized_output,
                streamed_output=streamed_output,
                action_buttons=action_buttons,
                skip_final_assistant=False,
            )
            replay_chunks = (
                view.chunk_text_for_streaming(finalized_output)
                if view.should_replay_finalized_output(
                    streamed_output=streamed_output,
                    finalized_output=finalized_output,
                )
                else []
            )
            return output, replay_chunks, final_output_source
        if (
            trusted_stream_output
            and finalized_output
            and not _is_generic_untrusted_fallback_output(finalized_output)
            and not _outputs_overlap(finalized_output, trusted_stream_output)
        ):
            output = finalized_output
            if response is not None and getattr(response, "message", None) is not None:
                response.message.content = finalized_output
            _append_output_if_missing(
                handler=handler,
                messages=messages,
                current_turn_messages=current_turn_messages,
                output=finalized_output,
                streamed_output=streamed_output,
                action_buttons=action_buttons,
                skip_final_assistant=False,
            )
            replay_chunks = (
                view.chunk_text_for_streaming(finalized_output)
                if view.should_replay_finalized_output(
                    streamed_output=streamed_output,
                    finalized_output=finalized_output,
                )
                else []
            )
            return output, replay_chunks, final_output_source

        output = trusted_stream_output
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = trusted_stream_output
        _append_output_if_missing(
            handler=handler,
            messages=messages,
            current_turn_messages=current_turn_messages,
            output=trusted_stream_output,
            streamed_output=streamed_output,
            action_buttons=action_buttons,
            skip_final_assistant=not bool(trusted_stream_output),
        )
        return output, [], final_output_source

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
        current_turn_messages=current_turn_messages,
        output=output,
        streamed_output=streamed_output,
        action_buttons=action_buttons,
        reasoning_content=reasoning_content,
    )

    if output != streamed_output:
        return output, view.chunk_text_for_streaming(output), final_output_source
    return output, [], final_output_source


def _build_replay_events(
    handler: Any,
    **kwargs: Any,
) -> list[str]:
    return build_replay_events(
        streamed_output=_resolve_generation_view(
            handler
        ).visible_stream_content.strip(),
        finalized_output=str(kwargs.get("output") or "").strip(),
        final_output_source=kwargs.get("final_output_source"),
        partial_reply_stream_chunks=kwargs.get("partial_reply_stream_chunks") or [],
        completed_reply_stream_chunks=kwargs.get("completed_reply_stream_chunks") or [],
    )


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
    response_output = str(
        getattr(getattr(response, "message", None), "content", None) or ""
    ).strip()
    if not str(output or "").strip() and response_output:
        output = response_output
    response_metadata = sync_response_runtime_metadata(handler, response=response)

    cleaned_output, action_buttons = view.extract_action_buttons(output)
    if action_buttons:
        output = cleaned_output
    immediate_events = build_immediate_turn_events(
        action_buttons=action_buttons,
        rag_sources=rag_sources,
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
    elif (
        str(output or "").strip() or view.visible_stream_content.strip()
    ) and not skip_final_assistant:
        output, completed_reply_stream_chunks, final_output_source = (
            _finalize_completed_output(
                handler,
                messages=messages,
                turn_start_message_index=turn_start_message_index,
                output=output,
                response=response,
                tool_results=tool_results,
                action_buttons=action_buttons,
                final_output_source=final_output_source,
            )
        )

    diagnostics_payload = view.build_diagnostics_payload()
    diagnostics_payload["final_output_source"] = final_output_source
    result_turn_record, resolved_protocol_path = build_result_turn_record(
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
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload=diagnostics_payload,
        turn_record=turn_projection.turn_record,
        rag_sources=rag_sources,
        tool_results=tool_results,
        output=str(output or ""),
        completion_reason=completion_reason,
        interrupted=paused_for_consent,
        error=None,
    )
    diagnostics_payload["turn_flow"] = turn_flow
    turn_projection.turn_record["turn_flow"] = turn_flow
    turn_record_metadata = dict(turn_projection.turn_record.get("metadata") or {})
    turn_record_metadata["turn_flow"] = turn_flow
    turn_projection.turn_record["metadata"] = turn_record_metadata

    answer_card_event = build_turn_answer_card_event(turn_flow)
    if answer_card_event is not None:
        immediate_events.append(
            SSEChunkEncoder.encode(_trace_payload(answer_card_event))
        )

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

    replay_events = build_replay_events(
        streamed_output=view.visible_stream_content.strip(),
        finalized_output=str(output or "").strip(),
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
    payload = build_done_event_payload(
        request=view.request,
        artifacts=artifacts,
        on_complete_extra=on_complete_extra,
    )
    return SSEChunkEncoder.encode(_trace_payload(payload))


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
    success: bool = False,
    partial: bool = True,
) -> ExecutionResult:
    view = _resolve_generation_view(handler)
    view.refresh_runtime_turn_record()
    diagnostics_payload = view.build_diagnostics_payload()
    final_output_source = diagnostics_payload.get("final_output_source")
    result_turn_record, resolved_protocol_path = build_result_turn_record(
        handler,
        diagnostics_payload=diagnostics_payload,
        response_metadata={},
    )
    turn_projection = build_turn_projection(
        raw_turn_record=result_turn_record,
        diagnostics_payload=diagnostics_payload,
        execution_path=view.execution_path,
        completion_reason=completion_reason,
        partial=partial,
        final_output_source=final_output_source,
        protocol_path=resolved_protocol_path,
        default_turn_outcome="success" if success else None,
        force_completion_reason_in_turn_record=success,
    )
    turn_flow = build_turn_flow_view_model(
        diagnostics_payload=turn_projection.diagnostics,
        turn_record=turn_projection.turn_record,
        rag_sources=rag_sources,
        tool_results=tool_results,
        output=str(output or ""),
        completion_reason=completion_reason,
        interrupted=interrupted,
        error=error,
    )
    turn_projection.diagnostics["turn_flow"] = turn_flow
    turn_projection.turn_record["turn_flow"] = turn_flow
    turn_record_metadata = dict(turn_projection.turn_record.get("metadata") or {})
    turn_record_metadata["turn_flow"] = turn_flow
    turn_projection.turn_record["metadata"] = turn_record_metadata

    return build_execution_result(
        success=success,
        output=output,
        messages=view.messages_to_dicts(messages),
        tool_results=tool_results,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        conversation_id=view.request.conversation_id,
        runtime_model_info=view.runtime_model_info,
        error=error,
        partial=partial,
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
            (view.provider_failure_kind or "none") if include_provider_state else "none"
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
