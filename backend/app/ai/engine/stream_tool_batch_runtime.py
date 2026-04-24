"""Stream tool-batch runtime extracted from the SSE transport adapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import is_ui_page_tool_name
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.ai.web_search.types import STATUS_NO_RESULTS
from app.core.i18n import _

from . import tool_processor as tool_processor_mod
from .turn_flow_projector import (
    build_tool_execution_result_event,
    build_tool_execution_started_event,
)


@dataclass(slots=True)
class StreamToolBatchRuntimeInput:
    sandbox: Any
    request: Any
    response: ChatResponse
    tools: list[ToolDefinition]
    all_tools: list[ToolDefinition] | None
    tool_consent_modes: dict[str, str]
    messages: list[ChatMessage]
    tool_calls: list[dict[str, Any]]
    starting_total_tokens: int
    starting_completion_tokens: int
    reasoning_content: str | None
    page_op_abort_threshold: int = 3


@dataclass(slots=True)
class StreamToolBatchCallbacks:
    emit_event: Callable[[dict[str, Any]], Awaitable[None]]
    emit_chunk: Callable[[str], Awaitable[None]]
    budget_exit_reason: Callable[[], str | None]
    register_budget_exit: Callable[[str | None], None]
    build_text_round_response: Callable[..., ChatResponse]


@dataclass(slots=True)
class StreamToolBatchRuntimeOutcome:
    response: ChatResponse | None
    tool_results: list[ToolResult]
    total_tokens: int
    completion_tokens_used: int
    output_override: str | None = None
    effective_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    paused_for_confirmation: bool = False
    page_op_aborted: bool = False


@dataclass(slots=True)
class _StreamToolBatchState:
    assistant_tool_message: ChatMessage
    assistant_tool_message_index: int
    round_tool_results: list[ToolResult] = field(default_factory=list)
    follow_up_messages: list[ChatMessage] = field(default_factory=list)
    round_has_confirmation: bool = False
    round_stopped_early: bool = False
    page_op_failures: int = 0
    page_op_aborted: bool = False
    output_override: str | None = None


def _tool_call_processor_cls():
    """Resolve the processor lazily so the runtime uses the current processor binding."""
    return tool_processor_mod.ToolCallProcessor


def _tool_call_has_pending_evidence(tool_call: dict[str, Any]) -> bool:
    pending_consent = tool_call.get("pending_consent")
    if isinstance(pending_consent, dict):
        return True
    pending_confirmation = tool_call.get("pending_confirmation")
    return isinstance(pending_confirmation, dict)


def _trim_tool_calls_after_early_exit(
    *,
    tool_calls: list[dict[str, Any]],
    messages: list[ChatMessage],
    assistant_tool_message: ChatMessage,
    assistant_tool_message_index: int,
    round_stopped_early: bool,
) -> list[dict[str, Any]]:
    if not round_stopped_early:
        return tool_calls

    preserved_tool_call_ids = {
        str(message.tool_call_id).strip()
        for message in messages[assistant_tool_message_index + 1 :]
        if message.role == "tool" and str(message.tool_call_id or "").strip()
    }
    trimmed_tool_calls = [
        tool_call
        for tool_call in tool_calls
        if (
            str(tool_call.get("id") or "").strip() in preserved_tool_call_ids
            or _tool_call_has_pending_evidence(tool_call)
        )
    ]
    assistant_tool_message.tool_calls = trimmed_tool_calls or None
    return trimmed_tool_calls


def _prepare_parallel_readonly_batch(
    *,
    processor: Any,
    tool_calls: list[dict[str, Any]],
) -> (
    list[tuple[dict[str, Any], str, str, dict[str, Any], dict[str, str | None]]] | None
):
    if len(tool_calls) <= 1:
        return None
    prepared: list[
        tuple[dict[str, Any], str, str, dict[str, Any], dict[str, str | None]]
    ] = []
    for tool_call in tool_calls:
        tc_id = str(tool_call.get("id") or "").strip()
        func = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        func_name = str(func.get("name") or "").strip()
        raw_args = func.get("arguments", "{}")
        arguments, parse_error = processor.parse_arguments(raw_args)
        if parse_error or arguments is None:
            return None
        if not processor.is_parallel_safe_tool_call(func_name, arguments):
            return None
        if processor.check_consent(func_name, arguments) in {"reject", "ask"}:
            return None
        prepared.append(
            (
                tool_call,
                tc_id,
                func_name,
                arguments,
                processor.get_skill_info(func_name),
            )
        )
    return prepared


def _build_page_abort_output(
    response: ChatResponse,
    translation_key: str,
) -> str:
    prefix = str(response.message.content or "").strip()
    suffix = _(translation_key)
    if prefix:
        return f"{prefix}\n\n{suffix}"
    return suffix


def _is_no_result_web_search(result: ToolResult) -> bool:
    if result.name != "web_search":
        return False
    payload = (
        dict(result.summary_payload)
        if isinstance(result.summary_payload, dict)
        else {}
    )
    status = str(payload.get("status") or "").strip()
    if status == STATUS_NO_RESULTS:
        return True
    raw_result_count = payload.get("result_count")
    try:
        result_count = int(raw_result_count) if raw_result_count is not None else None
    except (TypeError, ValueError):
        result_count = None
    return result_count is not None and result_count <= 0


def _should_emit_tool_result_preview(
    *,
    result: ToolResult,
    follow_up_message: ChatMessage | None,
    current_response_text: str,
) -> bool:
    result_summary = str(result.summary or "").strip()
    if (
        not result.success
        or not result_summary
        or follow_up_message is not None
        or current_response_text
        or result.name not in {"fetch_url", "web_search"}
    ):
        return False
    return not _is_no_result_web_search(result)


def _attach_canonical_tool_result_detail(
    tool_call: dict[str, Any],
    *,
    result: ToolResult,
) -> None:
    """Persist rich tool result detail onto canonical tool-call payloads."""
    tool_call["success"] = bool(result.success)
    if result.output:
        tool_call["output"] = result.output
    if result.error:
        tool_call["error"] = result.error
    if result.error_type:
        tool_call["error_type"] = result.error_type


async def _apply_single_result(
    *,
    runtime: StreamToolBatchRuntimeInput,
    callbacks: StreamToolBatchCallbacks,
    processor: Any,
    state: _StreamToolBatchState,
    tool_call: dict[str, Any],
    tc_id: str,
    func_name: str,
    skill_info: dict[str, str | None],
    result: ToolResult,
    tc_duration: int,
    tool_message: ChatMessage | None,
    follow_up_message: ChatMessage | None,
) -> bool:
    processor.annotate_tool_call(
        tool_call,
        duration_ms=tc_duration,
        result=result,
        skill_info=skill_info,
    )
    _attach_canonical_tool_result_detail(
        tool_call,
        result=result,
    )
    state.round_tool_results.append(result)
    await callbacks.emit_event(
        processor.build_tool_call_event(
            result,
            tc_duration,
            skill_info,
            name_override=func_name,
        )
    )
    await callbacks.emit_event(
        build_tool_execution_result_event(
            tool_name=func_name or result.name,
            success=bool(result.success),
            duration_ms=int(tc_duration or 0),
            tool_call_id=tc_id or result.tool_call_id,
        )
    )
    result_summary = str(result.summary or "").strip()
    current_response_text = str(runtime.response.message.content or "").strip()
    if _should_emit_tool_result_preview(
        result=result,
        follow_up_message=follow_up_message,
        current_response_text=current_response_text,
    ):
        await callbacks.emit_chunk(result_summary)
    if tool_message is not None:
        runtime.messages.append(tool_message)
    if follow_up_message is not None:
        state.follow_up_messages.append(follow_up_message)

    confirmation_payload = processor.check_confirmation_output(result)
    if confirmation_payload:
        processor.annotate_tool_call(
            tool_call,
            pending_confirmation=processor.build_pending_confirmation_payload(
                confirmation_payload,
                func_name,
            ),
        )
        state.round_has_confirmation = True
        await callbacks.emit_event(
            processor.build_confirmation_event(confirmation_payload, func_name)
        )

    is_page_op = is_ui_page_tool_name(func_name) if func_name else False
    if is_page_op:
        if result.success:
            state.page_op_failures = 0
        else:
            state.page_op_failures += 1
            if state.page_op_failures >= runtime.page_op_abort_threshold:
                state.page_op_aborted = True
                state.output_override = _build_page_abort_output(
                    runtime.response,
                    "page_operation.error.multiple_failures_sequence",
                )
                return True

    tool_result_budget_reason = callbacks.budget_exit_reason()
    if tool_result_budget_reason:
        callbacks.register_budget_exit(tool_result_budget_reason)
        return True
    return False


async def _run_parallel_batch(
    *,
    runtime: StreamToolBatchRuntimeInput,
    callbacks: StreamToolBatchCallbacks,
    processor: Any,
    state: _StreamToolBatchState,
    parallel_batch: list[
        tuple[dict[str, Any], str, str, dict[str, Any], dict[str, str | None]]
    ],
) -> None:
    for tool_call, tc_id, func_name, arguments, skill_info in parallel_batch:
        processor.annotate_tool_call(tool_call, skill_info=skill_info)
        await callbacks.emit_event(
            processor.build_tool_start_event(
                func_name,
                arguments,
                skill_info,
                tool_call_id=tc_id,
            )
        )
        await callbacks.emit_event(
            build_tool_execution_started_event(
                tool_name=func_name,
                tool_call_id=tc_id,
            )
        )
    singles = await asyncio.gather(
        *[
            processor.process_single(
                tool_call,
                conversation_id=runtime.request.conversation_id or 0,
            )
            for tool_call, *_ in parallel_batch
        ]
    )
    for (
        tool_call,
        tc_id,
        func_name,
        _arguments,
        skill_info,
    ), single in zip(parallel_batch, singles, strict=False):
        if single.tool_result is None:
            continue
        should_stop = await _apply_single_result(
            runtime=runtime,
            callbacks=callbacks,
            processor=processor,
            state=state,
            tool_call=tool_call,
            tc_id=tc_id,
            func_name=func_name,
            skill_info=skill_info,
            result=single.tool_result,
            tc_duration=int(single.duration_ms or 0),
            tool_message=single.tool_message,
            follow_up_message=single.follow_up_message,
        )
        if should_stop:
            state.round_stopped_early = True
            break


async def _run_sequential_batch(
    *,
    runtime: StreamToolBatchRuntimeInput,
    callbacks: StreamToolBatchCallbacks,
    processor: Any,
    state: _StreamToolBatchState,
) -> None:
    for tool_call in runtime.tool_calls:
        tc_id = str(tool_call.get("id") or "").strip()
        func = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        func_name = str(func.get("name") or "").strip()
        raw_args = func.get("arguments", "{}")
        arguments, parse_error = processor.parse_arguments(raw_args)
        if parse_error:
            err_result = ToolResult(
                tool_call_id=tc_id,
                name=func_name or "unknown",
                success=False,
                error=_("page_operation.error.json_parse_failed"),
                error_type=parse_error,
            )
            processor.annotate_tool_call(
                tool_call,
                duration_ms=0,
                result=err_result,
                skill_info=processor.get_skill_info(func_name),
            )
            _attach_canonical_tool_result_detail(
                tool_call,
                result=err_result,
            )
            state.round_tool_results.append(err_result)
            await callbacks.emit_event(
                processor.build_tool_call_event(
                    err_result,
                    0,
                    processor.get_skill_info(func_name),
                    name_override=func_name or err_result.name,
                )
            )
            await callbacks.emit_event(
                build_tool_execution_result_event(
                    tool_name=func_name or err_result.name,
                    success=False,
                    duration_ms=0,
                    tool_call_id=tc_id or err_result.tool_call_id,
                )
            )
            runtime.messages.append(processor.build_tool_message(err_result, tc_id))
            is_page_op = is_ui_page_tool_name(func_name) if func_name else False
            if is_page_op:
                state.page_op_failures += 1
                if state.page_op_failures >= runtime.page_op_abort_threshold:
                    state.page_op_aborted = True
                    state.round_stopped_early = True
                    state.output_override = _build_page_abort_output(
                        runtime.response,
                        "page_operation.error.multiple_failures_parse",
                    )
                    break
            continue

        skill_info = processor.get_skill_info(func_name)
        processor.annotate_tool_call(tool_call, skill_info=skill_info)
        consent = processor.check_consent(func_name, arguments)
        if consent == "reject":
            runtime.messages.append(processor.build_consent_reject_message(tc_id))
            await callbacks.emit_event(
                processor.build_consent_reject_event(
                    func_name,
                    skill_info,
                )
            )
            continue
        if consent == "ask":
            processor.annotate_tool_call(
                tool_call,
                pending_consent=processor.build_pending_consent_payload(
                    func_name,
                    arguments,
                    skill_info,
                ),
            )
            runtime.messages.append(
                processor.build_consent_ask_message(
                    tc_id,
                    func_name,
                    arguments,
                )
            )
            await callbacks.emit_event(
                processor.build_consent_ask_event(
                    func_name,
                    arguments,
                    skill_info,
                    interaction_mode_effective=str(
                        getattr(processor, "_interaction_mode", "") or ""
                    ).strip()
                    or None,
                )
            )
            state.round_has_confirmation = True
            continue

        await callbacks.emit_event(
            processor.build_tool_start_event(
                func_name,
                arguments,
                skill_info,
                tool_call_id=tc_id,
            )
        )
        await callbacks.emit_event(
            build_tool_execution_started_event(
                tool_name=func_name,
                tool_call_id=tc_id,
            )
        )
        started = time.perf_counter()
        result, tc_duration = await processor.execute_tool(
            tc_id,
            func_name,
            arguments,
            conversation_id=runtime.request.conversation_id or 0,
        )
        if tc_duration <= 0:
            tc_duration = int((time.perf_counter() - started) * 1000)
        should_stop = await _apply_single_result(
            runtime=runtime,
            callbacks=callbacks,
            processor=processor,
            state=state,
            tool_call=tool_call,
            tc_id=tc_id,
            func_name=func_name,
            skill_info=skill_info,
            result=result,
            tc_duration=tc_duration,
            tool_message=processor.build_tool_message(result, tc_id),
            follow_up_message=processor.build_attachment_relay_message(result),
        )
        if should_stop:
            state.round_stopped_early = True
            break


async def run_stream_tool_batch(
    *,
    runtime: StreamToolBatchRuntimeInput,
    callbacks: StreamToolBatchCallbacks,
) -> StreamToolBatchRuntimeOutcome:
    processor_cls = _tool_call_processor_cls()
    processor = processor_cls(
        sandbox=runtime.sandbox,
        tools=runtime.tools,
        all_tools=runtime.all_tools,
        consent_modes=runtime.tool_consent_modes,
        approved_pending_consent_tools=processor_cls.approved_pending_consent_tool_names(
            runtime.request.interaction_updates,
        ),
        interaction_mode=runtime.request.interaction_mode,
    )
    assistant_tool_message = processor.build_assistant_tool_call_message(
        content=runtime.response.message.content or "",
        tool_calls=runtime.tool_calls,
        reasoning_content=runtime.reasoning_content,
        metadata=(
            dict(runtime.response.metadata or {})
            if isinstance(runtime.response.metadata, dict)
            else None
        ),
    )
    runtime.messages.append(assistant_tool_message)
    state = _StreamToolBatchState(
        assistant_tool_message=assistant_tool_message,
        assistant_tool_message_index=len(runtime.messages) - 1,
    )

    parallel_batch = _prepare_parallel_readonly_batch(
        processor=processor,
        tool_calls=runtime.tool_calls,
    )
    if parallel_batch is not None:
        await _run_parallel_batch(
            runtime=runtime,
            callbacks=callbacks,
            processor=processor,
            state=state,
            parallel_batch=parallel_batch,
        )
    else:
        await _run_sequential_batch(
            runtime=runtime,
            callbacks=callbacks,
            processor=processor,
            state=state,
        )

    effective_tool_calls = _trim_tool_calls_after_early_exit(
        tool_calls=runtime.tool_calls,
        messages=runtime.messages,
        assistant_tool_message=assistant_tool_message,
        assistant_tool_message_index=state.assistant_tool_message_index,
        round_stopped_early=state.round_stopped_early,
    )

    if (
        state.follow_up_messages
        and not state.round_has_confirmation
        and not state.page_op_aborted
    ):
        runtime.messages.extend(state.follow_up_messages)

    if state.page_op_aborted:
        if state.output_override:
            await callbacks.emit_chunk(state.output_override)
        text_response = callbacks.build_text_round_response(
            content=state.output_override or "",
            reasoning_content=runtime.reasoning_content or "",
            total_tokens=runtime.starting_total_tokens,
        )
        return StreamToolBatchRuntimeOutcome(
            response=text_response,
            tool_results=state.round_tool_results,
            total_tokens=runtime.starting_total_tokens,
            completion_tokens_used=runtime.starting_completion_tokens,
            output_override=state.output_override,
            effective_tool_calls=effective_tool_calls,
            page_op_aborted=True,
        )

    if state.round_has_confirmation:
        consent_response = ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=runtime.response.message.content or "",
                tool_calls=effective_tool_calls or None,
                reasoning_content=runtime.reasoning_content,
                metadata=(
                    dict(runtime.response.metadata or {})
                    if isinstance(runtime.response.metadata, dict)
                    else None
                ),
            ),
            total_tokens=runtime.starting_total_tokens,
            output_tokens=runtime.starting_completion_tokens,
            tool_calls=effective_tool_calls or None,
            metadata={
                **(
                    dict(runtime.response.metadata or {})
                    if isinstance(runtime.response.metadata, dict)
                    else {}
                ),
                "skip_final_assistant": True,
            },
        )
        return StreamToolBatchRuntimeOutcome(
            response=consent_response,
            tool_results=state.round_tool_results,
            total_tokens=runtime.starting_total_tokens,
            completion_tokens_used=runtime.starting_completion_tokens,
            effective_tool_calls=effective_tool_calls,
            paused_for_confirmation=True,
        )

    return StreamToolBatchRuntimeOutcome(
        response=None,
        tool_results=state.round_tool_results,
        total_tokens=runtime.starting_total_tokens,
        completion_tokens_used=runtime.starting_completion_tokens,
        effective_tool_calls=effective_tool_calls,
    )


__all__ = [
    "StreamToolBatchCallbacks",
    "StreamToolBatchRuntimeInput",
    "StreamToolBatchRuntimeOutcome",
    "run_stream_tool_batch",
]
