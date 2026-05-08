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
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage
from app.core.logging import LogManager

from .base import BaseEngine
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
from .stream_execution_runtime import StreamIOAdapter, run_stream_execution
from .stream_generation_view import StreamGenerationView, build_stream_generation_view
from .stream_output_projection import (
    build_budget_exit_fallback_output as _build_budget_exit_fallback_output_impl,
)
from .stream_output_projection import (
    build_text_round_response as _build_text_round_response_impl,
)
from .stream_output_projection import (
    current_turn_has_finalized_output as _current_turn_has_finalized_output_impl,
)
from .stream_output_projection import (
    last_visible_assistant_content as _last_visible_assistant_content_impl,
)
from .stream_output_projection import (
    should_preserve_streamed_assistant_output as _should_preserve_streamed_assistant_output_impl,
)
from .stream_output_projection import (
    should_replay_finalized_output as _should_replay_finalized_output_impl,
)
from .stream_output_projection import (
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
from .turn_executor import TurnExecutor
from .types import (
    ExecutionRequest,
    ExecutionResult,
    PreparedExecution,
)

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult
    from app.models.ai.agent import Agent

    from .base import BaseEngine

logger = LogManager.get_logger("ai.engine.stream_handler")


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
        return build_stream_generation_view(self)

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
