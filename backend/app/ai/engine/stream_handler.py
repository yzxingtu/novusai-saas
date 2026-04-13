"""
SSE Streaming Execution Handler / SSE 流式执行处理器

Extracted from ConversationEngine._sse_generator, encapsulates the SSE event generation main loop.
Includes real-time tool call push, confirmation interception, DSML tag cleanup, error handling.
从 ConversationEngine._sse_generator 提取，封装 SSE 事件生成主循环。
包括工具调用实时推送、确认拦截、DSML 标签清理、错误处理。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum

from .base import BaseEngine, log_user_type_for_call_log
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
from .stream_execution_support import run_stream_execution
from .stream_generation_view import StreamGenerationView, ensure_stream_generation_view
from .stream_llm_round_support import (
    StreamRoundState,
    finalize_model_round,
    handle_stream_chunk,
    prepare_stream_round,
)
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
        generation_view = self._stream_generation_view()
        if not generation_view.visible_stream_content:
            return
        await self._emit_runtime_event({"event": "clear_content"})
        generation_view.visible_stream_content = ""
        generation_view.output = ""
        generation_view.reasoning_output = ""

    async def generate(self) -> AsyncIterator[str]:
        """SSE event generator main loop / SSE 事件生成器主循环"""
        async for event in run_stream_execution(self, logger=logger):
            yield event

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
