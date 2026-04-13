"""Execution loop helpers for StreamExecutionHandler.generate()."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from app.ai.sse import SSEChunkEncoder
from app.core.response import (
    build_error_event,
    build_exception_debug,
    build_public_error_text,
)
from app.middleware.trace import trace_id_var

from .stream_error_utils import resolve_stream_public_error_message
from .stream_generation_support import (
    append_partial_assistant_output,
    build_done_event,
    build_initial_events,
    build_terminal_result,
    drain_runtime_events,
    finalize_successful_turn,
    reset_stream_state,
)
from .stream_generation_view import ensure_stream_generation_view


async def _cancel_executor_task(task: asyncio.Task[Any] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with suppress(BaseException):
        await task


async def _handle_stream_exception(
    handler: Any,
    *,
    exc: Exception,
    executor_task: asyncio.Task[Any] | None,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    logger: Any,
) -> AsyncIterator[str]:
    await _cancel_executor_task(executor_task)

    public_error_message = resolve_stream_public_error_message(exc)
    logger.error(
        "Stream execution failed: agent={} error={}",
        getattr(handler.agent, "id", None),
        str(exc),
        exc_info=True,
    )
    try:
        yield SSEChunkEncoder.encode(
            build_error_event(
                code="STREAM_EXECUTION_ERROR",
                message=public_error_message,
                trace_id=trace_id_var.get() or None,
                debug=build_exception_debug(exc),
                extra={"conversation_id": handler.request.conversation_id},
            )
        )
    except Exception as yield_exc:
        logger.debug(
            "stream_handler error yield skipped (client disconnected?): {}",
            yield_exc,
        )

    view = ensure_stream_generation_view(handler)
    if handler.on_complete and not view.runtime.on_complete_called:
        duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
        partial_output = view.output or output
        partial_tokens = view.total_tokens
        if partial_tokens is None:
            partial_tokens = total_tokens
        append_partial_assistant_output(
            messages,
            output=partial_output,
            reasoning_output=view.reasoning_output,
        )
        failed_result = build_terminal_result(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            output=partial_output,
            total_tokens=partial_tokens,
            tool_results=all_tool_results,
            duration_ms=duration_ms,
            error=build_public_error_text(message=public_error_message),
            completion_reason="error",
            interrupted=False,
            include_provider_state=True,
        )
        on_complete_extra = await handler._await_on_complete_before_done(failed_result)
        post_done_callback = handler._pop_post_done_callback(on_complete_extra)
        if post_done_callback is not None:
            handler._schedule_background_callback(post_done_callback)

    try:
        yield SSEChunkEncoder.done()
    except Exception as yield_done_exc:
        logger.debug(
            "stream_handler done yield skipped (client disconnected?): {}",
            yield_done_exc,
        )


async def _handle_stream_base_exception(
    handler: Any,
    *,
    exc: BaseException,
    executor_task: asyncio.Task[Any] | None,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    logger: Any,
) -> AsyncIterator[str]:
    await _cancel_executor_task(executor_task)
    logger.error(
        "Stream BaseException: agent={} type={} error={}",
        getattr(handler.agent, "id", None),
        type(exc).__name__,
        str(exc),
        exc_info=True,
    )
    handler._update_turn_progress(interrupted_stage=handler._interrupted_stage)

    view = ensure_stream_generation_view(handler)
    if handler.on_complete and not view.runtime.on_complete_called:
        duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
        partial_output = view.output or output
        partial_tokens = view.total_tokens
        if partial_tokens is None:
            partial_tokens = total_tokens
        append_partial_assistant_output(
            messages,
            output=partial_output,
            reasoning_output=view.reasoning_output,
        )
        interrupted_result = build_terminal_result(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            output=partial_output,
            total_tokens=partial_tokens,
            tool_results=all_tool_results,
            duration_ms=duration_ms,
            error=build_public_error_text(
                message="Execution interrupted",
                detail=f"{type(exc).__name__}: {exc}",
            ),
            completion_reason="interrupted",
            interrupted=True,
            include_provider_state=False,
        )
        handler._schedule_on_complete(interrupted_result)

    if False:  # pragma: no cover - keep async-generator contract explicit
        yield ""


async def run_stream_execution(
    handler: Any,
    *,
    logger: Any,
) -> AsyncIterator[str]:
    messages = handler.prep.messages
    rag_sources = handler.prep.rag_sources
    optimize_event = handler.prep.optimize_event
    turn_start_message_index = len(messages)

    total_tokens = 0
    all_tool_results: list[Any] = []
    output = ""
    executor_task: asyncio.Task[Any] | None = None
    reset_stream_state(handler)

    try:
        handler._interrupted_stage = "stream_generating"
        for initial_event in build_initial_events(
            handler,
            optimize_event=optimize_event,
        ):
            yield initial_event

        executor_task = asyncio.create_task(handler._run_with_turn_executor())
        async for queued_event in drain_runtime_events(
            handler,
            executor_task=executor_task,
        ):
            yield queued_event

        turn_execution = await executor_task
        output = turn_execution.output
        total_tokens = turn_execution.total_tokens
        all_tool_results = list(turn_execution.tool_results)
        artifacts = finalize_successful_turn(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            turn_start_message_index=turn_start_message_index,
            turn_execution=turn_execution,
            logger=logger,
        )
        for immediate_event in artifacts.immediate_events:
            yield immediate_event
        for replay_event in artifacts.replay_events:
            yield replay_event

        on_complete_extra = await handler._await_on_complete_before_done(artifacts.result)
        post_done_callback = handler._pop_post_done_callback(on_complete_extra)
        if post_done_callback is not None:
            handler._schedule_background_callback(post_done_callback)
        yield build_done_event(
            handler,
            artifacts=artifacts,
            on_complete_extra=on_complete_extra,
        )
        yield SSEChunkEncoder.done()

    except Exception as exc:
        async for event in _handle_stream_exception(
            handler,
            exc=exc,
            executor_task=executor_task,
            messages=messages,
            rag_sources=rag_sources,
            output=output,
            total_tokens=total_tokens,
            all_tool_results=all_tool_results,
            logger=logger,
        ):
            yield event

    except BaseException as exc:
        async for event in _handle_stream_base_exception(
            handler,
            exc=exc,
            executor_task=executor_task,
            messages=messages,
            rag_sources=rag_sources,
            output=output,
            total_tokens=total_tokens,
            all_tool_results=all_tool_results,
            logger=logger,
        ):
            yield event
        raise


__all__ = ["run_stream_execution"]
