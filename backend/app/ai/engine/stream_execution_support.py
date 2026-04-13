"""Execution loop helpers and IO adapter for StreamExecutionHandler.generate()."""
from __future__ import annotations
import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage, ChatResponse
from app.core.response import (
    build_error_event,
    build_exception_debug,
    build_public_error_text,
)
from app.enums.common import UserRoleEnum
from app.middleware.trace import trace_id_var
from .base import log_user_type_for_call_log
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
from .stream_llm_round_support import (
    StreamRoundState,
    finalize_model_round,
    handle_stream_chunk,
    prepare_stream_round,
)
from .stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
    run_stream_tool_batch,
)
from .turn_executor import ToolBatchResult
from .tool_execution_helpers import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult

    from .execution_state_machine import ExecutionStateMachine
    from .stream_handler import StreamExecutionHandler
    from .turn_executor import ModelRoundResult
    from .types import ToolUsePolicy

class StreamIOAdapter:
    """Transport adapter for streaming TurnExecutor execution."""

    def __init__(self, handler: StreamExecutionHandler) -> None:
        self.handler = handler

    @staticmethod
    def _normalize_tool_call_outcome(
        outcome: tuple[Any, ...],
    ) -> tuple[ChatResponse | None, list[Any], int, int]:
        return _normalize_tool_call_outcome_impl(outcome)

    def _selected_skill_names(self) -> list[str]:
        capability_bundle = getattr(self.handler.prep, "capability_bundle", None)
        if capability_bundle is None:
            return []
        return list(getattr(capability_bundle, "selected_skill_names", []) or [])

    def _context_sources(self) -> list[Any]:
        capability_bundle = getattr(self.handler.prep, "capability_bundle", None)
        if capability_bundle is None:
            return []
        return list(getattr(capability_bundle, "context_sources", []) or [])

    def _request_with_defaults(self) -> Any:
        request = self.handler.request
        required_attrs = (
            "interaction_mode",
            "input_variables",
            "billing_context",
            "tool_use_policy",
            "user_role",
            "interaction_updates",
        )
        if all(hasattr(request, attr) for attr in required_attrs):
            return request
        payload = dict(getattr(request, "__dict__", {}) or {})
        payload.setdefault("interaction_mode", "confirm")
        payload.setdefault("input_variables", {})
        payload.setdefault("billing_context", None)
        payload.setdefault("tool_use_policy", self.handler.prep.tool_use_policy)
        payload.setdefault("user_role", UserRoleEnum.TENANT_ADMIN.value)
        payload.setdefault("interaction_updates", None)
        return SimpleNamespace(**payload)

    def _sync_runtime_metadata(self, metadata: dict[str, Any] | None) -> None:
        if not isinstance(metadata, dict):
            return
        runtime_model_info = metadata.get("runtime_model_info")
        if isinstance(runtime_model_info, dict):
            generation_view = self.handler._stream_generation_view()
            generation_view.runtime_model_info = dict(runtime_model_info)
            sandbox = getattr(self.handler.engine, "sandbox", None)
            if sandbox is not None and hasattr(sandbox, "set_runtime_model_info"):
                sandbox.set_runtime_model_info(runtime_model_info)
        raw_turn_record = metadata.get("runtime_turn_record")
        self.handler._stream_generation_view().replace_runtime_turn_record(raw_turn_record)

    async def call_llm(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        tool_use_policy: ToolUsePolicy,
        **kwargs: Any,
    ) -> ModelRoundResult:
        round_kind = str(kwargs.get("breach_retry_result") or "").strip()
        runtime_context = await prepare_stream_round(self, round_kind=round_kind)
        req_role = getattr(
            self.handler.request,
            "user_role",
            UserRoleEnum.TENANT_ADMIN.value,
        )
        state = StreamRoundState()
        async for chunk in self.handler.engine._stream_llm_chunks(
            agent=self.handler.agent,
            messages=messages,
            tenant_id=self.handler.request.tenant_id,
            conversation_id=self.handler.request.conversation_id,
            route_result=self.handler.prep.route_result,
            tools=tools,
            execution_path=getattr(self.handler.prep, "execution_path", None),
            user_id=getattr(self.handler.request, "user_id", None),
            billing_context=getattr(self.handler.request, "billing_context", None),
            log_user_type=log_user_type_for_call_log(req_role),
            runtime_context=runtime_context,
            all_tool_names=[
                tool.name
                for tool in (getattr(self.handler.prep, "all_tools", None) or [])
            ],
            selected_skill_names=self._selected_skill_names(),
            context_sources=self._context_sources(),
            tool_use_policy=tool_use_policy,
            **kwargs,
        ):
            await handle_stream_chunk(
                self,
                state,
                chunk=chunk,
            )

        return finalize_model_round(self, state)

    async def handle_tool_calls(
        self,
        *,
        response: ChatResponse,
        tools: list[ToolDefinition],
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> ToolBatchResult:
        request_proxy = self._request_with_defaults()
        tool_calls = list(response.tool_calls or response.message.tool_calls or [])
        tool_calls, _truncated_after_navigation = (
            self.handler.runtime_contract.truncate_tool_calls_after_navigation(tool_calls)
        )
        starting_total_tokens = int(kwargs.get("starting_total_tokens") or 0)
        starting_completion_tokens = int(
            kwargs.get("starting_completion_tokens") or 0
        )
        reasoning_content = str(
            response.message.reasoning_content or response.message.content or ""
        ).strip() or None
        runtime_outcome = await run_stream_tool_batch(
            runtime=StreamToolBatchRuntimeInput(
                sandbox=self.handler.engine.sandbox,
                request=request_proxy,
                response=response,
                tools=tools,
                all_tools=self.handler.prep.all_tools,
                tool_consent_modes=self.handler.prep.tool_consent_modes,
                messages=messages,
                tool_calls=tool_calls,
                starting_total_tokens=starting_total_tokens,
                starting_completion_tokens=starting_completion_tokens,
                reasoning_content=reasoning_content,
            ),
            callbacks=StreamToolBatchCallbacks(
                emit_event=self.handler._emit_runtime_event,
                budget_exit_reason=self.handler._state.budget_exit_reason,
                register_budget_exit=self.handler._register_budget_exit,
                build_text_round_response=self.handler._build_text_round_response,
            ),
        )
        if runtime_outcome.output_override is not None:
            self.handler._stream_generation_view().output = runtime_outcome.output_override

        return ToolBatchResult(
            response=runtime_outcome.response,
            tool_results=runtime_outcome.tool_results,
            total_tokens=runtime_outcome.total_tokens,
            completion_tokens_used=runtime_outcome.completion_tokens_used,
        )

    async def finalize_partial_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        output, final_total_tokens, final_completion_tokens = (
            await self.handler.runtime_contract.finalize_partial_output(
                agent=self.handler.agent,
                request=self.handler.request,
                prep=self.handler.prep,
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                selected_skill_names=self._selected_skill_names(),
                context_sources=self._context_sources(),
            )
        )
        stream_local_output = str(self.handler._stream_generation_view().output or "").strip()
        if not str(output or "").strip() and stream_local_output:
            output = stream_local_output
        return output, final_total_tokens, final_completion_tokens

    async def finalize_completed_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        output, final_total_tokens, final_completion_tokens = (
            await self.handler.runtime_contract.finalize_completed_output(
                agent=self.handler.agent,
                request=self.handler.request,
                prep=self.handler.prep,
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                selected_skill_names=self._selected_skill_names(),
                context_sources=self._context_sources(),
            )
        )
        stream_local_output = str(self.handler._stream_generation_view().output or "").strip()
        if not str(output or "").strip() and stream_local_output:
            output = stream_local_output
        return output, final_total_tokens, final_completion_tokens

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.handler.runtime_contract.should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.handler.runtime_contract.should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
            continuation=continuation,
        )

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response is None:
            return None, None, {}
        return self.handler.runtime_contract.analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]:
        return self.handler.runtime_contract.restrict_tools_to_names(
            tools,
            allowed_tool_names,
        )

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: Any,
        tools: list[Any],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None:
        self.handler.runtime_contract.log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=policy,
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result=retry_result,
            continuation=continuation,
        )

    async def emit_chunk(self, text: str) -> None:
        if text:
            await self.handler._emit_runtime_event(
                {
                    "event": "message",
                    "delta": text,
                }
            )


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


__all__ = ["StreamIOAdapter", "run_stream_execution"]
