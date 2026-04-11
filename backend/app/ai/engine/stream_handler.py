"""
SSE Streaming Execution Handler / SSE 流式执行处理器

Extracted from ConversationEngine._sse_generator, encapsulates the SSE event generation main loop.
Includes real-time tool call push, confirmation interception, DSML tag cleanup, error handling.
从 ConversationEngine._sse_generator 提取，封装 SSE 事件生成主循环。
包括工具调用实时推送、确认拦截、DSML 标签清理、错误处理。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.core.response import (
    build_error_event,
    build_exception_debug,
    build_public_error_text,
)
from app.enums.common import UserRoleEnum
from app.middleware.trace import trace_id_var

from .base import BaseEngine, log_user_type_for_call_log
from .budget_guard import BudgetGuard
from .execution_state_machine import ExecutionStateMachine
from .failure_classifier import FailureClassifier
from .stream_completion_support import (
    await_on_complete_before_done as _await_on_complete_before_done_impl,
)
from .stream_completion_support import (
    pop_post_done_callback as _pop_post_done_callback_impl,
)
from .stream_completion_support import (
    schedule_background_callback as _schedule_background_callback_impl,
)
from .stream_completion_support import (
    start_on_complete_task as _start_on_complete_task_impl,
)
from .stream_error_utils import (
    resolve_stream_public_error_message as _resolve_stream_public_error_message,
)
from .stream_generation_support import (
    append_partial_assistant_output as _append_partial_assistant_output_impl,
)
from .stream_generation_support import build_done_event as _build_done_event_impl
from .stream_generation_support import (
    build_initial_events as _build_initial_events_impl,
)
from .stream_generation_support import (
    build_terminal_result as _build_terminal_result_impl,
)
from .stream_generation_support import (
    drain_runtime_events as _drain_runtime_events_impl,
)
from .stream_generation_support import (
    finalize_successful_turn as _finalize_successful_turn_impl,
)
from .stream_generation_support import reset_stream_state as _reset_stream_state_impl
from .stream_generation_view import StreamGenerationView, ensure_stream_generation_view
from .stream_output_helpers import (
    build_budget_exit_fallback_output as _build_budget_exit_fallback_output_impl,
)
from .stream_output_helpers import (
    build_text_round_response as _build_text_round_response_impl,
)
from .stream_output_helpers import (
    current_turn_has_finalized_output as _current_turn_has_finalized_output_impl,
)
from .stream_output_helpers import (
    last_visible_assistant_content as _last_visible_assistant_content_impl,
)
from .stream_output_helpers import (
    should_preserve_streamed_assistant_output as _should_preserve_streamed_assistant_output_impl,
)
from .stream_output_helpers import (
    should_replay_finalized_output as _should_replay_finalized_output_impl,
)
from .stream_output_helpers import (
    tool_loop_round_limit as _tool_loop_round_limit_impl,
)
from .stream_runtime_contract import build_stream_runtime_contract
from .stream_runtime_record_support import (
    apply_runtime_turn_record_overlays as _apply_runtime_turn_record_overlays_impl,
)
from .stream_runtime_record_support import (
    ensure_runtime_turn_record as _ensure_runtime_turn_record_impl,
)
from .stream_runtime_record_support import (
    refresh_runtime_turn_record as _refresh_runtime_turn_record_impl,
)
from .stream_runtime_record_support import (
    register_budget_exit as _register_budget_exit_impl,
)
from .stream_runtime_record_support import (
    replace_runtime_turn_record as _replace_runtime_turn_record_impl,
)
from .stream_runtime_record_support import (
    resolved_protocol_path as _resolved_protocol_path_impl,
)
from .stream_runtime_record_support import (
    update_turn_progress as _update_turn_progress_impl,
)
from .stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
    run_stream_tool_batch,
)
from .stream_tool_call_helpers import (
    chunk_text_for_streaming as _chunk_text_for_streaming_impl,
)
from .stream_tool_call_helpers import (
    extract_action_buttons as _extract_action_buttons_impl,
)
from .stream_tool_call_helpers import (
    finalize_stream_tool_calls as _finalize_stream_tool_calls_impl,
)
from .stream_tool_call_helpers import (
    merge_stream_tool_calls as _merge_stream_tool_calls_impl,
)
from .stream_tool_call_helpers import (
    normalize_stream_tool_call as _normalize_stream_tool_call_impl,
)
from .tool_execution_helpers import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
from .turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from .types import (
    ExecutionRequest,
    ExecutionResult,
    PreparedExecution,
    ToolUsePolicy,
)

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult
    from app.models.ai.agent import Agent

    from .base import BaseEngine

logger = LogManager.get_logger("ai.engine.stream_handler")


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
            self.handler._runtime_model_info = dict(runtime_model_info)
            sandbox = getattr(self.handler.engine, "sandbox", None)
            if sandbox is not None and hasattr(sandbox, "set_runtime_model_info"):
                sandbox.set_runtime_model_info(runtime_model_info)
        raw_turn_record = metadata.get("runtime_turn_record")
        self.handler._replace_runtime_turn_record(raw_turn_record)

    async def call_llm(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        tool_use_policy: ToolUsePolicy,
        **kwargs: Any,
    ) -> ModelRoundResult:
        aggregated_output = ""
        aggregated_reasoning = ""
        aggregated_tool_calls: list[dict[str, Any]] = []
        total_tokens = 0
        completion_tokens_used = 0
        finish_reason = "stop"
        native_search_observed = False

        round_kind = str(kwargs.get("breach_retry_result") or "").strip()
        if round_kind in {"contract_retry", "intent_retry"}:
            await self.handler._emit_clear_content_if_needed()
        elif self.handler._clear_before_next_message:
            self.handler._clear_before_next_message = False
            await self.handler._emit_clear_content_if_needed()

        runtime_context = self.handler._next_runtime_context
        self.handler._next_runtime_context = None
        req_role = getattr(
            self.handler.request,
            "user_role",
            UserRoleEnum.TENANT_ADMIN.value,
        )
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
            self._sync_runtime_metadata(getattr(chunk, "metadata", None))
            # Forward web_search keepalive as SSE event to prevent connection timeout
            # 转发 web_search keepalive 为 SSE 事件防止连接超时
            chunk_meta = getattr(chunk, "metadata", None)
            if isinstance(chunk_meta, dict) and chunk_meta.get("web_search_in_progress"):
                native_search_observed = True
                await self.handler._emit_runtime_event(
                    {"event": "status", "status": "web_search_in_progress"}
                )
            if chunk.reasoning_delta:
                aggregated_reasoning += chunk.reasoning_delta
                self.handler._reasoning_output = aggregated_reasoning
                await self.handler._emit_runtime_event(
                    {
                        "event": "thinking",
                        "delta": chunk.reasoning_delta,
                    }
                )
            if chunk.delta:
                aggregated_output += chunk.delta
                self.handler._visible_stream_content += chunk.delta
                self.handler._output = self.handler._visible_stream_content
                await self.handler._emit_runtime_event(
                    {
                        "event": "message",
                        "delta": chunk.delta,
                    }
                )
            if chunk.tool_calls:
                aggregated_tool_calls = self.handler._merge_stream_tool_calls(
                    aggregated_tool_calls,
                    chunk.tool_calls,
                )
            if chunk.total_tokens is not None:
                total_tokens = int(chunk.total_tokens or 0)
            if chunk.output_tokens is not None:
                completion_tokens_used = int(chunk.output_tokens or 0)
            finish_reason = chunk.finish_reason or finish_reason

        finalized_tool_calls = self.handler._finalize_stream_tool_calls(
            aggregated_tool_calls,
        )
        if completion_tokens_used <= 0:
            completion_tokens_used = int(total_tokens or 0)

        completion_reason = BudgetGuard.completion_reason(
            self.handler._state.budget,
            completion_tokens=completion_tokens_used,
            total_tokens=total_tokens,
        )
        if completion_reason and aggregated_output.strip() and finalized_tool_calls:
            finalized_tool_calls = []
            finish_reason = "stop"

        self.handler._clear_before_next_message = bool(
            finalized_tool_calls and aggregated_output.strip()
        )
        self.handler._total_tokens = int(total_tokens or 0)
        self.handler._completion_tokens_used = int(completion_tokens_used or 0)
        response = ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=aggregated_output,
                reasoning_content=aggregated_reasoning or None,
                tool_calls=finalized_tool_calls or None,
            ),
            total_tokens=total_tokens,
            output_tokens=completion_tokens_used,
            finish_reason=(
                "tool_calls" if finalized_tool_calls else (finish_reason or "stop")
            ),
            tool_calls=finalized_tool_calls or None,
        )
        return ModelRoundResult(
            response=response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            native_search_observed=native_search_observed,
        )

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
            self.handler._output = runtime_outcome.output_override

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
        stream_local_output = str(self.handler._output or "").strip()
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
        stream_local_output = str(self.handler._output or "").strip()
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


class StreamExecutionHandler:
    """
    SSE Streaming Execution Handler / SSE 流式执行处理器

    Encapsulates ConversationEngine._sse_generator logic as an independent class.
    Accesses _stream_llm_chunks / _messages_to_dicts via engine reference.
    将 ConversationEngine._sse_generator 的完整逻辑封装为独立类。

    Event types / 事件类型：
    - message: Content delta / 内容增量
    - tool_call: Tool call result / 工具调用结果
    - thinking: AI executing tool / AI 正在执行工具
    - optimizing_tools: Tool optimization event / 工具优化事件
    - rag_sources: RAG reference sources / RAG 引用来源
    - confirmation_request: User confirmation needed / 需要用户确认
    - done: Completion / 完成
    - [DONE]: SSE end marker / SSE 结束标记
    """

    def __init__(
        self,
        engine: BaseEngine,
        agent: Agent,
        request: ExecutionRequest,
        prep: PreparedExecution,
        start_time: float,
        on_complete: Callable[[ExecutionResult], Awaitable[dict[str, Any] | None]]
        | None = None,
    ):
        self.engine = engine
        self.agent = agent
        self.request = request
        self.prep = prep
        self.start_time = start_time
        self.on_complete = on_complete
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._event_queue: asyncio.Queue[str] = asyncio.Queue()
        self._interrupted_stage = "stream_initializing"
        self._state = ExecutionStateMachine.from_prepared_execution(prep)
        self.runtime_contract = build_stream_runtime_contract(engine)
        self._total_tokens = 0
        self._completion_tokens_used = 0
        self._visible_stream_content = ""
        self._clear_before_next_message = False
        self._next_runtime_context = getattr(prep, "stream_runtime", None)

    def _register_tool_failures(self, tool_results: list[ToolResult]) -> None:
        tool_failure_kind, tool_failure_events = (
            FailureClassifier.classify_tool_results(tool_results)
        )
        if tool_failure_kind != "none":
            for event in tool_failure_events:
                self._state.register_provider_failure(
                    kind=tool_failure_kind,
                    event=event,
                )

    def _schedule_on_complete(self, result: ExecutionResult) -> None:
        self._start_on_complete_task(
            result,
            defer_post_done=False,
        )

    @staticmethod
    def _pop_post_done_callback(
        extra: dict[str, Any] | None,
    ) -> Callable[[], Awaitable[None]] | None:
        return _pop_post_done_callback_impl(extra)

    def _schedule_background_callback(
        self,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        _schedule_background_callback_impl(self, callback, logger=logger)

    def _start_on_complete_task(
        self,
        result: ExecutionResult,
        *,
        defer_post_done: bool,
    ) -> asyncio.Task[dict[str, Any] | None] | None:
        return _start_on_complete_task_impl(
            self,
            result,
            defer_post_done=defer_post_done,
            logger=logger,
        )

    async def _await_on_complete_before_done(
        self,
        result: ExecutionResult,
    ) -> dict[str, Any] | None:
        return await _await_on_complete_before_done_impl(
            self,
            result,
            logger=logger,
        )

    def _apply_runtime_turn_record_overlays(self) -> None:
        _apply_runtime_turn_record_overlays_impl(self)

    def _replace_runtime_turn_record(self, raw_turn_record: Any) -> None:
        _replace_runtime_turn_record_impl(self, raw_turn_record)

    def _refresh_runtime_turn_record(self) -> None:
        _refresh_runtime_turn_record_impl(self)

    def _ensure_runtime_turn_record(self) -> dict[str, Any]:
        return _ensure_runtime_turn_record_impl(self)

    def _update_turn_progress(self, **fields: Any) -> None:
        _update_turn_progress_impl(self, **fields)

    def _register_budget_exit(self, reason: str | None) -> None:
        _register_budget_exit_impl(self, reason)

    def _tool_loop_round_limit(self, tools: list[ToolDefinition]) -> int:
        return _tool_loop_round_limit_impl(self, tools)

    @staticmethod
    def _build_text_round_response(
        *,
        content: str,
        reasoning_content: str,
        total_tokens: int,
    ):
        return _build_text_round_response_impl(
            content=content,
            reasoning_content=reasoning_content,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _last_visible_assistant_content(messages: list[ChatMessage]) -> str:
        return _last_visible_assistant_content_impl(messages)

    @staticmethod
    def _current_turn_has_finalized_output(
        *,
        messages: list[ChatMessage],
        streamed_output: str,
        finalized_output: str,
    ) -> bool:
        return _current_turn_has_finalized_output_impl(
            messages=messages,
            streamed_output=streamed_output,
            finalized_output=finalized_output,
        )

    @staticmethod
    def _should_replay_finalized_output(
        *,
        streamed_output: str,
        finalized_output: str,
    ) -> bool:
        return _should_replay_finalized_output_impl(
            streamed_output=streamed_output,
            finalized_output=finalized_output,
        )

    @staticmethod
    def _should_preserve_streamed_assistant_output(
        *,
        final_output_source: str | None,
        streamed_output: str,
        finalized_output: str,
    ) -> bool:
        return _should_preserve_streamed_assistant_output_impl(
            final_output_source=final_output_source,
            streamed_output=streamed_output,
            finalized_output=finalized_output,
        )

    def _build_budget_exit_fallback_output(
        self,
        *,
        tool_results: list[ToolResult],
    ) -> str:
        return _build_budget_exit_fallback_output_impl(
            self,
            tool_results=tool_results,
        )

    def _resolved_protocol_path(
        self,
        *,
        diagnostics_payload: dict[str, Any] | None = None,
        turn_record: dict[str, Any] | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> str:
        return _resolved_protocol_path_impl(
            self,
            diagnostics_payload=diagnostics_payload,
            turn_record=turn_record,
            response_metadata=response_metadata,
        )

    def _stream_generation_view(self) -> StreamGenerationView:
        return ensure_stream_generation_view(self)

    async def _run_with_turn_executor(self):
        """Run the shared TurnExecutor with streaming transport hooks."""
        return await TurnExecutor.run(
            state=self._state,
            io=StreamIOAdapter(self),
            prep=self.prep,
            request=self.request,
            agent=self.agent,
        )

    async def _emit_runtime_event(self, payload: dict[str, Any]) -> None:
        await self._event_queue.put(SSEChunkEncoder.encode(payload))

    async def _emit_clear_content_if_needed(self) -> None:
        if not self._visible_stream_content:
            return
        await self._emit_runtime_event({"event": "clear_content"})
        self._visible_stream_content = ""
        self._output = ""
        self._reasoning_output = ""

    async def generate(self) -> AsyncIterator[str]:
        """SSE event generator main loop / SSE 事件生成器主循环"""
        messages = self.prep.messages
        rag_sources = self.prep.rag_sources
        _optimize_event = self.prep.optimize_event
        turn_start_message_index = len(messages)
        generation_view = self._stream_generation_view()

        total_tokens = 0
        all_tool_results: list[ToolResult] = []
        output = ""
        executor_task: asyncio.Task[Any] | None = None
        _reset_stream_state_impl(generation_view)

        try:
            self._interrupted_stage = "stream_generating"
            for initial_event in _build_initial_events_impl(
                generation_view,
                optimize_event=_optimize_event,
            ):
                yield initial_event

            executor_task = asyncio.create_task(self._run_with_turn_executor())
            async for queued_event in _drain_runtime_events_impl(
                generation_view,
                executor_task=executor_task,
            ):
                yield queued_event

            turn_execution = await executor_task
            output = turn_execution.output
            total_tokens = turn_execution.total_tokens
            all_tool_results = list(turn_execution.tool_results)
            artifacts = _finalize_successful_turn_impl(
                generation_view,
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

            on_complete_extra = await self._await_on_complete_before_done(
                artifacts.result
            )
            post_done_callback = self._pop_post_done_callback(on_complete_extra)
            if post_done_callback is not None:
                self._schedule_background_callback(post_done_callback)
            yield _build_done_event_impl(
                generation_view,
                artifacts=artifacts,
                on_complete_extra=on_complete_extra,
            )
            yield SSEChunkEncoder.done()

        except Exception as exc:
            if executor_task is not None and not executor_task.done():
                executor_task.cancel()
                with suppress(BaseException):
                    await executor_task
            public_error_message = _resolve_stream_public_error_message(exc)
            logger.error(
                "Stream execution failed: agent={} error={}",
                self.agent.id,
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
                        extra={"conversation_id": self.request.conversation_id},
                    )
                )
            except Exception as yield_exc:
                logger.debug(
                    "stream_handler error yield skipped (client disconnected?): {}",
                    yield_exc,
                )

            # Partial persist: pass accumulated state so history is not lost / 中断时传递已累积状态，避免历史丢失
            if self.on_complete and not self._on_complete_called:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                partial_output = getattr(self, "_output", None) or output
                partial_tokens = getattr(self, "_total_tokens", None)
                if partial_tokens is None:
                    partial_tokens = total_tokens
                _append_partial_assistant_output_impl(
                    messages,
                    output=partial_output,
                    reasoning_output=getattr(self, "_reasoning_output", None),
                )
                failed_result = _build_terminal_result_impl(
                    generation_view,
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
                on_complete_extra = await self._await_on_complete_before_done(
                    failed_result
                )
                post_done_callback = self._pop_post_done_callback(on_complete_extra)
                if post_done_callback is not None:
                    self._schedule_background_callback(post_done_callback)

            try:
                yield SSEChunkEncoder.done()
            except Exception as yield_done_exc:
                logger.debug(
                    "stream_handler done yield skipped (client disconnected?): {}",
                    yield_done_exc,
                )

        except BaseException as exc:
            if executor_task is not None and not executor_task.done():
                executor_task.cancel()
                with suppress(BaseException):
                    await executor_task
            # Catch CancelledError / GeneratorExit and other non-Exception exceptions / 捕获 CancelledError / GeneratorExit 等非 Exception 异常
            logger.error(
                "Stream BaseException: agent={} type={} error={}",
                self.agent.id,
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )
            self._update_turn_progress(interrupted_stage=self._interrupted_stage)
            if self.on_complete and not self._on_complete_called:
                duration_ms = int((time.perf_counter() - self.start_time) * 1000)
                partial_output = getattr(self, "_output", None) or output
                partial_tokens = getattr(self, "_total_tokens", None)
                if partial_tokens is None:
                    partial_tokens = total_tokens
                _append_partial_assistant_output_impl(
                    messages,
                    output=partial_output,
                    reasoning_output=getattr(self, "_reasoning_output", None),
                )
                interrupted_result = _build_terminal_result_impl(
                    generation_view,
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
                self._schedule_on_complete(interrupted_result)
            raise  # Must re-raise BaseException / 必须重新抛出 BaseException

    def _chunk_text_for_streaming(self, text: str, chunk_size: int = 32) -> list[str]:
        return _chunk_text_for_streaming_impl(text, chunk_size=chunk_size)

    @staticmethod
    def _normalize_stream_tool_call(tool_call: Any) -> dict[str, Any] | None:
        return _normalize_stream_tool_call_impl(tool_call)

    @classmethod
    def _merge_stream_tool_calls(
        cls,
        existing: list[dict[str, Any]],
        incoming: list[Any],
    ) -> list[dict[str, Any]]:
        return _merge_stream_tool_calls_impl(existing, incoming)

    @staticmethod
    def _finalize_stream_tool_calls(
        calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return _finalize_stream_tool_calls_impl(calls, logger=logger)

    # ========================================
    # Action Buttons Parsing / Action Buttons 解析
    # ========================================

    _ACTION_START = "[ACTIONS]"
    _ACTION_END = "[/ACTIONS]"

    @staticmethod
    def _extract_action_buttons(
        output: str,
    ) -> tuple[str, list[dict[str, str]] | None]:
        return _extract_action_buttons_impl(
            output,
            action_start=StreamExecutionHandler._ACTION_START,
            action_end=StreamExecutionHandler._ACTION_END,
            logger=logger,
        )


__all__ = ["StreamExecutionHandler"]
