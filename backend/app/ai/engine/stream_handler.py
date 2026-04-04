"""
SSE Streaming Execution Handler / SSE 流式执行处理器

Extracted from ConversationEngine._sse_generator, encapsulates the SSE event generation main loop.
Includes real-time tool call push, confirmation interception, DSML tag cleanup, error handling.
从 ConversationEngine._sse_generator 提取，封装 SSE 事件生成主循环。
包括工具调用实时推送、确认拦截、DSML 标签清理、错误处理。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.ai.page_locale import resolve_page_locale
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage
from app.core.i18n import _
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
from .intent_planner import IntentPlanner
from .path_selector import PathSelector
from .recovery_manager import RecoveryManager
from .types import (
    ExecutionRequest,
    ExecutionResult,
    IntentPlan,
    PreparedExecution,
    ToolUsePolicy,
)

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult
    from app.models.ai.agent import Agent

    from .base import BaseEngine
    from .tool_processor import ToolCallProcessor

logger = LogManager.get_logger("ai.engine.stream_handler")


def _trace_payload(data: dict[str, Any]) -> dict[str, Any]:
    trace_id = trace_id_var.get()
    if trace_id and "trace_id" not in data:
        return {**data, "trace_id": trace_id}
    return data


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
        self._interrupted_stage = "stream_initializing"
        self._state = ExecutionStateMachine.from_prepared_execution(prep)
        self._total_tokens = 0
        self._completion_tokens_used = 0

    def _register_tool_failures(self, tool_results: list[ToolResult]) -> None:
        tool_failure_kind, tool_failure_events = FailureClassifier.classify_tool_results(
            tool_results
        )
        if tool_failure_kind != "none":
            for event in tool_failure_events:
                self._state.register_provider_failure(
                    kind=tool_failure_kind,
                    event=event,
                )

    def _schedule_on_complete(self, result: ExecutionResult) -> None:
        """Run on_complete in background before client disconnect can cancel it.

        在发送 `done` 事件前启动后台回调，避免前端收到完成事件后立即断开 SSE，
        导致消息持久化 / 统计 / 记忆提取回调被请求取消一并杀掉。
        """
        if not self.on_complete or self._on_complete_called:
            return

        self._on_complete_called = True

        async def _runner() -> None:
            try:
                if self.prep.context_engine is not None:
                    await self.prep.context_engine.after_turn(
                        self.agent,
                        self.request,
                        result,
                    )
                await self.on_complete(result)
            except Exception as cb_exc:
                logger.error("on_complete callback error: {}", str(cb_exc))
            except BaseException as cb_base_exc:
                logger.error(
                    "on_complete callback base exception: type={} error={}",
                    type(cb_base_exc).__name__,
                    str(cb_base_exc),
                    exc_info=True,
                )

        task = asyncio.create_task(_runner())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _ensure_runtime_turn_record(self) -> dict[str, Any]:
        if not isinstance(self._runtime_turn_record, dict):
            self._runtime_turn_record = {}
        return self._runtime_turn_record

    def _update_turn_progress(self, **fields: Any) -> None:
        record = self._ensure_runtime_turn_record()
        progress = (
            dict(record.get("tool_loop_progress") or {})
            if isinstance(record.get("tool_loop_progress"), dict)
            else {}
        )
        for key, value in fields.items():
            if key == "tool_loop_progress" and isinstance(value, dict):
                progress.update(value)
                continue
            if value is None:
                continue
            record[key] = value
        if progress:
            record["tool_loop_progress"] = progress

    def _register_budget_exit(self, reason: str | None) -> None:
        if not reason:
            return
        self._state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": reason},
        )
        self._update_turn_progress(
            budget_exit_reason=reason,
            tool_loop_progress={"budget_exit_reason": reason},
        )

    def _tool_loop_round_limit(self, tools: list[ToolDefinition]) -> int:
        budget = getattr(self.prep, "execution_budget", None)
        if budget is not None and budget.max_tool_rounds > 0:
            return (
                int(budget.max_tool_rounds)
                + max(1, int(budget.max_retry_per_intent or 0))
                + 1
            )
        tool_count = len(getattr(self.prep, "all_tools", None) or tools or [])
        intent_count = len(getattr(self.prep, "intent_plan", None) or [])
        return max(3, min(6, tool_count + max(1, intent_count) + 1))

    @staticmethod
    def _build_text_round_response(
        *,
        content: str,
        reasoning_content: str,
        total_tokens: int,
    ):
        from app.ai.types import ChatResponse

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=content,
                reasoning_content=reasoning_content or None,
            ),
            total_tokens=total_tokens,
            finish_reason="stop",
        )

    @staticmethod
    def _last_visible_assistant_content(messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role != "assistant" or message.tool_calls:
                continue
            content = str(message.content or "").strip()
            if content:
                return content
        return ""

    def _build_budget_exit_fallback_output(
        self,
        *,
        tool_results: list[ToolResult],
    ) -> str:
        locale = resolve_page_locale(getattr(self.request, "input_variables", None))
        key = (
            "ai.stream.partial.tool_budget_after_success"
            if any(result.success for result in tool_results)
            else "ai.stream.partial.budget_exit"
        )
        return _(key, locale=locale)

    async def generate(self) -> AsyncIterator[str]:
        """SSE event generator main loop / SSE 事件生成器主循环"""
        from .conversation import _strip_model_fc_tokens
        from .tool_processor import ToolCallProcessor

        messages = self.prep.messages
        tools = self.prep.tools
        all_tools = self.prep.all_tools
        rag_sources = self.prep.rag_sources
        _optimize_event = self.prep.optimize_event
        _tool_consent_modes = self.prep.tool_consent_modes

        total_tokens = 0
        all_tool_results: list[ToolResult] = []
        output = ""
        self._output = ""  # Used for partial persist on interrupt  # 补充说明 / note
        self._reasoning_output = ""  # For chain-of-thought models, used in partial persist  # 补充说明 / note
        self._total_tokens = 0
        self._runtime_model_info: dict[str, Any] | None = None
        self._runtime_turn_record: dict[str, Any] | None = None
        self._on_complete_called = False
        initial_budget_exit = self._state.budget_exit_reason()

        try:
            self._interrupted_stage = "stream_generating"
            next_runtime_context = getattr(self.prep, "stream_runtime", None)
            if self.request.conversation_id:
                # Publish conversation id early so frontend keeps the session / 尽早下发 conversation id 以便前端保持会话
                # even when the stream is interrupted before the final done event.
                yield SSEChunkEncoder.encode(
                    _trace_payload(
                        {
                            "event": "conversation",
                            "conversation_id": self.request.conversation_id,
                        }
                    )
                )
            current_page_context = (
                self.request.input_variables.get("page_context")
                if isinstance(getattr(self.request, "input_variables", None), dict)
                else None
            )
            if isinstance(current_page_context, dict):
                self._update_turn_progress(
                    last_page_key=str(current_page_context.get("page_key") or "").strip()
                    or None
                )
            kb_feedback = getattr(self.request, "knowledge_base_feedback", None)
            if isinstance(kb_feedback, dict) and kb_feedback.get(
                "dropped_knowledge_base_ids"
            ):
                yield SSEChunkEncoder.encode(
                    _trace_payload(
                        {
                            "event": "knowledge_base_feedback",
                            **kb_feedback,
                        }
                    )
                )

            processor = ToolCallProcessor(
                sandbox=self.engine.sandbox,
                tools=tools,
                all_tools=all_tools,
                consent_modes=_tool_consent_modes,
                approved_pending_consent_tools=ToolCallProcessor.approved_pending_consent_tool_names(
                    self.request.interaction_updates,
                ),
            )
            bundle_selected_skill_names = (
                list(
                    getattr(self.prep.capability_bundle, "selected_skill_names", [])
                    or []
                )
                if getattr(self.prep, "capability_bundle", None) is not None
                else []
            )
            bundle_context_sources = (
                getattr(self.prep.capability_bundle, "context_sources", None)
                if getattr(self.prep, "capability_bundle", None) is not None
                else None
            )

            # Push tool optimization event / 推送工具优化事件
            if _optimize_event is not None:
                yield SSEChunkEncoder.encode(
                    {"event": "optimizing_tools", **_optimize_event}
                    if isinstance(_optimize_event, dict)
                    else _optimize_event
                )

            if initial_budget_exit:
                self._register_budget_exit(initial_budget_exit)
            elif tools:
                # ---- With tools: tool call loop + final reply streaming ---- / 有工具：工具调用循环 + 最终回复流式推送
                async for event in self._generate_with_tools(
                    messages,
                    tools,
                    processor,
                    all_tool_results,
                    _strip_model_fc_tokens,
                ):
                    yield event
                    # Extract output and total_tokens from events
                    # (shared state via self._output / self._total_tokens)
                    # 从事件中提取 output 和 total_tokens

                output = self._output
                total_tokens = self._total_tokens
            else:
                # ---- Without tools: real streaming push ---- / 无工具：真实流式推送
                self._reasoning_output = ""
                _req_role = getattr(
                    self.request,
                    "user_role",
                    UserRoleEnum.TENANT_ADMIN.value,
                )
                async for chunk in self.engine._stream_llm_chunks(
                    agent=self.agent,
                    messages=messages,
                    tenant_id=self.request.tenant_id,
                    conversation_id=self.request.conversation_id,
                    route_result=self.prep.route_result,
                    user_id=getattr(self.request, "user_id", None),
                    billing_context=getattr(self.request, "billing_context", None),
                    log_user_type=log_user_type_for_call_log(_req_role),
                    runtime_context=next_runtime_context,
                    all_tool_names=[tool.name for tool in self.prep.all_tools],
                    selected_skill_names=bundle_selected_skill_names,
                    context_sources=bundle_context_sources,
                ):
                    if self._runtime_model_info is None and isinstance(
                        getattr(chunk, "metadata", None), dict
                    ):
                        self._runtime_model_info = chunk.metadata.get(
                            "runtime_model_info",
                        )
                    if self._runtime_turn_record is None and isinstance(
                        getattr(chunk, "metadata", None), dict
                    ):
                        raw_turn_record = chunk.metadata.get("runtime_turn_record")
                        if isinstance(raw_turn_record, dict):
                            self._runtime_turn_record = dict(raw_turn_record)
                        elif hasattr(raw_turn_record, "__dict__"):
                            self._runtime_turn_record = dict(
                                getattr(raw_turn_record, "__dict__", {}) or {}
                            )
                    if chunk.reasoning_delta:
                        self._reasoning_output += chunk.reasoning_delta
                        yield SSEChunkEncoder.encode(
                            {
                                "event": "thinking",
                                "delta": chunk.reasoning_delta,
                            }
                        )

                    if chunk.delta:
                        output += chunk.delta
                        yield SSEChunkEncoder.encode(
                            {
                                "event": "message",
                                "delta": chunk.delta,
                            }
                        )

                    if chunk.total_tokens is not None:
                        total_tokens = chunk.total_tokens

                    # 不可在 finish_reason 处 break：会提前 aclose 异步生成器，
                    # ConversationEngine._stream_llm_chunks 尾部的 Key 计数/commit 不会执行。
                next_runtime_context = None

            # ---- Parse and send Action Buttons ---- / 解析并发送 Action Buttons
            cleaned_output, action_buttons = self._extract_action_buttons(output)
            if action_buttons:
                output = cleaned_output
                yield SSEChunkEncoder.encode(
                    {
                        "event": "action_buttons",
                        "buttons": action_buttons,
                    }
                )
            if not tools:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=output,
                        reasoning_content=(self._reasoning_output or "").strip()
                        or None,
                        metadata=(
                            {"action_buttons": action_buttons}
                            if action_buttons
                            else None
                        ),
                    )
                )

            # ---- Send RAG reference source event ---- / 发送 RAG 引用来源事件
            if rag_sources:
                yield SSEChunkEncoder.encode(
                    {
                        "event": "rag_sources",
                        "sources": rag_sources,
                    }
                )

            # ---- Build result ---- / 构建结果
            duration_ms = int((time.perf_counter() - self.start_time) * 1000)
            self._state.register_completion_tokens(self._completion_tokens_used)
            budget_exit_reason = self._state.budget_exit_reason()
            if budget_exit_reason:
                self._register_budget_exit(budget_exit_reason)
            decision = RecoveryManager.decide(
                self._state.intent_plan,
                budget=self._state.budget,
                provider_failure_kind=self._state.provider_failure_kind,
            )
            if decision is not None and decision.action in {
                "pause_for_consent",
                "return_partial",
            }:
                self._state.recovery_history.append(decision)
            paused_for_consent = bool(
                decision is not None and decision.action == "pause_for_consent"
            )
            partial = bool(decision is not None and decision.action == "return_partial")
            partial_reply_stream_chunks: list[str] = []
            completion_reason = "completed"
            if partial:
                self._state.transition("partial_exit")
                completion_reason = decision.reason or "return_partial"
                visible_assistant_output = self._last_visible_assistant_content(messages)
                streamed_output = str(self._output or "").strip()
                if visible_assistant_output:
                    output = visible_assistant_output
                elif str(output or "").strip():
                    output = str(output).strip()
                elif self._state.provider_failure_kind == "budget_exit":
                    output = self._build_budget_exit_fallback_output(
                        tool_results=all_tool_results,
                    )
                else:
                    output = RecoveryManager.build_partial_output(
                        self._state.intent_plan,
                        reason=decision.reason or "return_partial",
                        provider_failure_kind=self._state.provider_failure_kind,
                    )
                self._output = output
                if output and not visible_assistant_output:
                    messages.append(ChatMessage(role="assistant", content=output))
                    if output != streamed_output:
                        partial_reply_stream_chunks = self._chunk_text_for_streaming(
                            output
                        )
            elif paused_for_consent:
                self._state.transition("awaiting_consent")
                completion_reason = decision.reason or "pause_for_consent"
                RecoveryManager.ensure_latest_assistant_pending_consent(
                    messages,
                    RecoveryManager.pending_consent_payload_from_decision(decision),
                )
                output = self._last_visible_assistant_content(messages) or str(
                    self._output or ""
                ).strip()
                self._output = output
            else:
                self._state.transition("completed")

            tool_planner = getattr(self.prep, "tool_planner", None)
            diagnostics_payload = self._state.build_diagnostics_payload()

            result = ExecutionResult(
                success=not partial,
                output=output,
                messages=self.engine._messages_to_dicts(messages),
                tool_results=all_tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=self.request.conversation_id,
                runtime_model_id=(self._runtime_model_info or {}).get("model_id"),
                runtime_model_name=(self._runtime_model_info or {}).get("model_name"),
                runtime_provider_id=(self._runtime_model_info or {}).get("provider_id"),
                runtime_provider_name=(self._runtime_model_info or {}).get(
                    "provider_name"
                ),
                rag_sources=rag_sources,
                rag_source_kinds=self.prep.rag_source_kinds,
                partial=partial,
                completion_reason=completion_reason,
                context_compacted=self.prep.context_compacted,
                memory_flush_triggered=self.prep.memory_flush_triggered,
                memory_recalled=self.prep.memory_recalled,
                prune_stats=self.prep.prune_stats,
                tool_planner=tool_planner,
                turn_record=self._runtime_turn_record,
                intent_plan=list(self._state.intent_plan),
                execution_path=getattr(self.prep, "execution_path", None),
                execution_budget=(
                    self._state.budget.snapshot()
                    if self._state.budget is not None
                    else None
                ),
                recovery_history=[
                    decision_item.to_dict()
                    for decision_item in self._state.recovery_history
                ],
                provider_failure_kind=self._state.provider_failure_kind,
                provider_events=list(self._state.provider_events),
                diagnostics=diagnostics_payload,
            )

            if paused_for_consent:
                result.success = False
                result.interrupted = True

            if isinstance(result.turn_record, dict):
                result.turn_record["execution_path"] = getattr(
                    self.prep,
                    "execution_path",
                    None,
                )
                result.turn_record["intent_plan"] = diagnostics_payload.get(
                    "intent_plan",
                )
                result.turn_record["budget"] = diagnostics_payload.get("budget")
                result.turn_record["budget_status"] = diagnostics_payload.get(
                    "budget_status",
                )
                result.turn_record["budget_exit_reason"] = diagnostics_payload.get(
                    "budget_exit_reason",
                )
                result.turn_record["candidate_tool_names"] = diagnostics_payload.get(
                    "candidate_tool_names",
                )
                result.turn_record["retry_events"] = diagnostics_payload.get(
                    "retry_events",
                )
                result.turn_record["partial_exit_reason"] = diagnostics_payload.get(
                    "partial_exit_reason",
                )
                result.turn_record["unfinished_intents"] = diagnostics_payload.get(
                    "unfinished_intents",
                )
                result.turn_record["provider_events"] = diagnostics_payload.get(
                    "provider_events",
                )
                result.turn_record["failure_kind"] = diagnostics_payload.get(
                    "failure_kind",
                )
                metadata = dict(result.turn_record.get("metadata") or {})
                metadata["orchestration"] = diagnostics_payload
                result.turn_record["metadata"] = metadata

            if partial_reply_stream_chunks:
                for chunk in partial_reply_stream_chunks:
                    yield SSEChunkEncoder.encode(
                        {
                            "event": "message",
                            "delta": chunk,
                        }
                    )

            # Start callback before yielding done so client-side disconnect
            # cannot prevent persistence from even starting.
            # 在发送 done 之前启动后台回调，确保客户端断开不会阻止持久化开始。
            self._schedule_on_complete(result)

            # ---- Send done first so UI unlocks immediately ---- / 先发送 done 以便前端立即解锁
            # on_complete may trigger slow operations (e.g. memory extraction LLM call);
            # emitting done before the callback prevents the UI from hanging.
            yield SSEChunkEncoder.encode(
                _trace_payload(
                    {
                        "event": "done",
                        "conversation_id": self.request.conversation_id,
                        "total_tokens": total_tokens,
                        "duration_ms": duration_ms,
                        "context_compacted": result.context_compacted,
                        "memory_flush_triggered": result.memory_flush_triggered,
                        "memory_recalled": result.memory_recalled,
                        "prune_stats": result.prune_stats,
                        "rag_source_kinds": result.rag_source_kinds,
                    }
                )
            )

            yield SSEChunkEncoder.done()

        except Exception as exc:
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
                        message=_("common.server_error"),
                        trace_id=trace_id_var.get() or None,
                        debug=build_exception_debug(exc),
                        extra={"conversation_id": self.request.conversation_id},
                    )
                )
                yield SSEChunkEncoder.done()
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
                # Append partial assistant when output exists but stream aborted / 有输出但未正常结束时追加部分 assistant
                if partial_output:
                    reasoning = (
                        getattr(self, "_reasoning_output", None) or ""
                    ).strip() or None
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=partial_output,
                            reasoning_content=reasoning,
                        )
                    )
                tool_planner = getattr(self.prep, "tool_planner", None)

                failed_result = ExecutionResult(
                    success=False,
                    output=partial_output,
                    messages=self.engine._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=partial_tokens,
                    duration_ms=duration_ms,
                    conversation_id=self.request.conversation_id,
                    runtime_model_id=(self._runtime_model_info or {}).get("model_id"),
                    runtime_model_name=(self._runtime_model_info or {}).get(
                        "model_name"
                    ),
                    runtime_provider_id=(self._runtime_model_info or {}).get(
                        "provider_id"
                    ),
                    runtime_provider_name=(self._runtime_model_info or {}).get(
                        "provider_name"
                    ),
                    error=build_public_error_text(
                        message=_("common.server_error"),
                        exc=exc,
                    ),
                    partial=True,
                    interrupted=False,
                    completion_reason="error",
                    rag_sources=rag_sources,
                    rag_source_kinds=self.prep.rag_source_kinds,
                    context_compacted=self.prep.context_compacted,
                    memory_flush_triggered=self.prep.memory_flush_triggered,
                    memory_recalled=self.prep.memory_recalled,
                    prune_stats=self.prep.prune_stats,
                    tool_planner=tool_planner,
                    turn_record=self._runtime_turn_record,
                )
                self._schedule_on_complete(failed_result)

        except BaseException as exc:
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
                if partial_output:
                    reasoning = (
                        getattr(self, "_reasoning_output", None) or ""
                    ).strip() or None
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=partial_output,
                            reasoning_content=reasoning,
                        )
                    )
                tool_planner = getattr(self.prep, "tool_planner", None)

                interrupted_result = ExecutionResult(
                    success=False,
                    output=partial_output,
                    messages=self.engine._messages_to_dicts(messages),
                    tool_results=all_tool_results,
                    total_tokens=partial_tokens,
                    duration_ms=duration_ms,
                    conversation_id=self.request.conversation_id,
                    runtime_model_id=(self._runtime_model_info or {}).get("model_id"),
                    runtime_model_name=(self._runtime_model_info or {}).get(
                        "model_name"
                    ),
                    runtime_provider_id=(self._runtime_model_info or {}).get(
                        "provider_id"
                    ),
                    runtime_provider_name=(self._runtime_model_info or {}).get(
                        "provider_name"
                    ),
                    error=build_public_error_text(
                        message="Execution interrupted",
                        detail=f"{type(exc).__name__}: {exc}",
                    ),
                    partial=True,
                    interrupted=True,
                    completion_reason="interrupted",
                    rag_sources=rag_sources,
                    rag_source_kinds=self.prep.rag_source_kinds,
                    context_compacted=self.prep.context_compacted,
                    memory_flush_triggered=self.prep.memory_flush_triggered,
                    memory_recalled=self.prep.memory_recalled,
                    prune_stats=self.prep.prune_stats,
                    tool_planner=tool_planner,
                    turn_record=self._runtime_turn_record,
                )
                self._schedule_on_complete(interrupted_result)
            raise  # Must re-raise BaseException / 必须重新抛出 BaseException

    def _chunk_text_for_streaming(self, text: str, chunk_size: int = 32) -> list[str]:
        """Split text into chunks for simulated streaming (typing effect)."""
        if not text:
            return []
        chunks: list[str] = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i : i + chunk_size])
        return chunks

    async def _generate_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        processor: ToolCallProcessor,
        all_tool_results: list[ToolResult],
        strip_fc_tokens: Callable[[str], str],
    ) -> AsyncIterator[str]:
        """
        Tool rounds use real streaming and incremental tool_call aggregation.
        工具轮次使用真实流式，并增量聚合 tool_call。
        """
        helper_methods = {
            "_restrict_tools_to_names": BaseEngine._restrict_tools_to_names,
            "_truncate_tool_calls_after_navigation": BaseEngine._truncate_tool_calls_after_navigation,
            "_tool_call_operation_name": BaseEngine._tool_call_operation_name,
            "_tool_call_name": BaseEngine._tool_call_name,
            "_mark_multi_family_progress": BaseEngine._mark_multi_family_progress,
            "_build_page_no_progress_recovery": BaseEngine._build_page_no_progress_recovery,
            "_messages_have_blocking_pending_interaction": BaseEngine._messages_have_blocking_pending_interaction,
            "_first_incomplete_requested_family": BaseEngine._first_incomplete_requested_family,
            "_allowed_tool_names_for_family": BaseEngine._allowed_tool_names_for_family,
        }
        for method_name, fallback in helper_methods.items():
            if not callable(getattr(self.engine, method_name, None)):
                setattr(self.engine, method_name, fallback)

        self._total_tokens = 0
        self._completion_tokens_used = 0
        self._output = ""
        self._reasoning_output = ""
        _unused_strip_fc_tokens = (
            strip_fc_tokens  # unused in real streaming path  # 补充说明 / note
        )
        del _unused_strip_fc_tokens
        append_final_assistant = True
        next_runtime_context = getattr(self.prep, "stream_runtime", None)
        continuation_context = getattr(self.prep, "continuation_context", None)
        round_tool_policy = getattr(self.prep, "tool_use_policy", ToolUsePolicy())
        tools_full = list(tools)
        self._fetch_gate_message_sent = False
        bundle_selected_skill_names = (
            list(getattr(self.prep.capability_bundle, "selected_skill_names", []) or [])
            if getattr(self.prep, "capability_bundle", None) is not None
            else []
        )
        bundle_context_sources = (
            getattr(self.prep.capability_bundle, "context_sources", None)
            if getattr(self.prep, "capability_bundle", None) is not None
            else None
        )
        forced_tool_names: list[str] | None = None
        ordered_requested_families: list[str] = []
        if not self._state.intent_plan:
            inferred_intents = IntentPlanner.plan_turn(
                messages=list(getattr(self.request, "messages", None) or messages or []),
                tools=getattr(self.prep, "all_tools", None) or tools_full,
                input_variables=getattr(self.request, "input_variables", None),
                continuation_context=continuation_context,
                capability_bundle=getattr(self.prep, "capability_bundle", None),
            )
            actionable_inferred_intents = any(
                intent.family != "none" and intent.requires_tools
                for intent in inferred_intents
            )
            fallback_family = round_tool_policy.family
            if fallback_family == "none" and round_tool_policy.retry_on_contract_breach:
                allowed_tool_names = set(round_tool_policy.allowed_tool_names or [])
                if {"web_search", "fetch_url"} & allowed_tool_names:
                    fallback_family = "web_research"
                elif any(
                    name == "get_page_context" or name.startswith("pageop_")
                    for name in allowed_tool_names
                ):
                    fallback_family = "page_ops"
                elif "get_current_weather" in allowed_tool_names:
                    fallback_family = "weather"
                elif "get_current_time" in allowed_tool_names:
                    fallback_family = "time_ops"
            if (
                not actionable_inferred_intents
                and fallback_family != "none"
            ):
                fallback_allowed_tools = list(round_tool_policy.allowed_tool_names)
                inferred_intents = [
                    IntentPlan(
                        intent_id=f"{fallback_family}-1",
                        kind=f"{fallback_family}_intent",
                        family=fallback_family,
                        order=1,
                        user_visible_label=fallback_family,
                        source_text=BaseEngine._extract_last_user_text(messages),
                        status="pending",
                        requires_tools=True,
                        allow_text_response=False,
                        allowed_tool_names=fallback_allowed_tools,
                        preferred_tool_names=fallback_allowed_tools,
                        completion_signals=BaseEngine._intent_completion_signals(
                            fallback_family,
                            allowed_tool_names=fallback_allowed_tools,
                            preferred_tool_names=fallback_allowed_tools,
                        ),
                    )
                ]
                actionable_inferred_intents = True
            if actionable_inferred_intents:
                self._state.intent_plan = [
                    IntentPlan(**intent.to_dict())
                    if isinstance(intent, IntentPlan)
                    else IntentPlan(**intent)
                    for intent in inferred_intents
                ]
                self.prep.intent_plan = list(self._state.intent_plan)
                if getattr(self.prep, "execution_path", None) in {None, ""}:
                    inferred_path = PathSelector.select(self._state.intent_plan)
                    self.prep.execution_path = inferred_path
                    self._state.execution_path = inferred_path
                if getattr(self.prep, "execution_budget", None) is None:
                    inferred_budget = BudgetGuard.build_default(
                        self._state.execution_path,
                        intent_count=len(self._state.intent_plan),
                    )
                    self.prep.execution_budget = inferred_budget
                    self._state.budget = inferred_budget
        for intent in list(getattr(self.prep, "intent_plan", []) or []):
            family = (
                str(intent.get("family") or "").strip()
                if isinstance(intent, dict)
                else str(getattr(intent, "family", "") or "").strip()
            )
            if family and family != "none" and family not in ordered_requested_families:
                ordered_requested_families.append(family)
        completed_families: set[str] = set()
        has_fetch_url_in_toolset = any(
            t.name == "fetch_url"
            for t in (getattr(self.prep, "all_tools", None) or tools_full)
        )

        # ---- Confirmation interception ---- / 确认拦截
        _last_user_text = ""
        if self.request.messages:
            _last = self.request.messages[-1]
            if _last.role == "user":
                _last_user_text = (_last.content or "").strip()

        _has_structured_confirm = any(
            str(u.get("kind") or "") == "pending_confirmation" and not u.get("rejected")
            for u in (self.request.interaction_updates or [])
        )

        _pending = None
        if _has_structured_confirm or processor.is_confirmation_text(_last_user_text):
            _pending = processor.find_pending_confirmation(messages)

        if _pending:
            _tc_id = _pending["tool_call_id"]
            _func_name = _pending["name"]
            _arguments = _pending["arguments"]
            _conf_skill = processor.get_skill_info(_func_name)
            yield SSEChunkEncoder.encode(
                processor.build_tool_start_event(
                    _func_name,
                    _arguments,
                    _conf_skill,
                    tool_call_id=_tc_id,
                )
            )
            _result, _tc_dur = await processor.execute_tool(
                _tc_id,
                _func_name,
                _arguments,
                conversation_id=self.request.conversation_id or 0,
            )
            all_tool_results.append(_result)
            yield SSEChunkEncoder.encode(
                processor.build_tool_call_event(
                    _result,
                    _tc_dur,
                    _conf_skill,
                    name_override=_func_name,
                )
            )
            messages.append(
                processor.build_assistant_tool_call_message(
                    content="",
                    tool_calls=[
                        {
                            "id": _tc_id,
                            "type": "function",
                            "function": {
                                "name": _func_name,
                                "arguments": json.dumps(_arguments, ensure_ascii=False),
                            },
                        }
                    ],
                )
            )
            messages.append(processor.build_tool_message(_result, _tc_id))
            _follow_up_message = processor.build_attachment_relay_message(_result)
            if _follow_up_message:
                messages.append(_follow_up_message)
            self._state.register_tool_results(
                messages=messages,
                tool_results=[_result],
            )
            self._register_tool_failures([_result])

        _consecutive_page_op_failures = 0
        _consecutive_data_op_failures = 0
        _page_op_aborted = False
        PAGE_OP_ABORT_THRESHOLD = 3

        round_limit = self._tool_loop_round_limit(tools_full)

        for _round in range(round_limit):
            pre_model_reason = BudgetGuard.pre_model_reason(self._state.budget)
            if pre_model_reason:
                self._register_budget_exit(pre_model_reason)
                break
            self._interrupted_stage = f"tool_loop_round_{_round + 1}:llm"
            round_output = ""
            round_reasoning_output = ""
            round_visible_thinking = ""
            round_tool_calls: list[dict[str, Any]] = []
            round_tool_results: list[ToolResult] = []
            round_total_tokens = 0
            round_output_tokens = 0
            round_message_events: list[str] = []
            self._output = ""
            self._reasoning_output = ""

            if (
                self.engine._needs_fetch_url_before_summary(messages)
                and not self._fetch_gate_message_sent
            ):
                messages.append(
                    ChatMessage(
                        role="system",
                        content=render_prompt_contract("fetch_url_gate"),
                    )
                )
                self._fetch_gate_message_sent = True

            round_tools = self.engine._apply_fetch_url_only_gate(
                messages,
                tools_full,
                getattr(self.prep, "all_tools", None) or tools_full,
            )
            restrict_tools = getattr(self.engine, "_restrict_tools_to_names", None)
            if callable(restrict_tools):
                round_tools = restrict_tools(
                    round_tools,
                    forced_tool_names,
                )
            processor.tools = round_tools

            _req_role = getattr(
                self.request,
                "user_role",
                UserRoleEnum.TENANT_ADMIN.value,
            )
            async for chunk in self.engine._stream_llm_chunks(
                agent=self.agent,
                messages=messages,
                tenant_id=self.request.tenant_id,
                conversation_id=self.request.conversation_id,
                route_result=self.prep.route_result,
                tools=round_tools,
                user_id=getattr(self.request, "user_id", None),
                billing_context=getattr(self.request, "billing_context", None),
                log_user_type=log_user_type_for_call_log(_req_role),
                runtime_context=next_runtime_context,
                all_tool_names=[tool.name for tool in self.prep.all_tools],
                selected_skill_names=bundle_selected_skill_names,
                context_sources=bundle_context_sources,
                tool_use_policy=round_tool_policy,
            ):
                if self._runtime_model_info is None and isinstance(
                    getattr(chunk, "metadata", None), dict
                ):
                    self._runtime_model_info = chunk.metadata.get(
                        "runtime_model_info",
                    )
                if self._runtime_turn_record is None and isinstance(
                    getattr(chunk, "metadata", None), dict
                ):
                    raw_turn_record = chunk.metadata.get("runtime_turn_record")
                    if isinstance(raw_turn_record, dict):
                        self._runtime_turn_record = dict(raw_turn_record)
                    elif hasattr(raw_turn_record, "__dict__"):
                        self._runtime_turn_record = dict(
                            getattr(raw_turn_record, "__dict__", {}) or {}
                        )
                if chunk.reasoning_delta:
                    round_reasoning_output += chunk.reasoning_delta
                    round_visible_thinking += chunk.reasoning_delta
                    self._reasoning_output = round_reasoning_output
                    yield SSEChunkEncoder.encode(
                        {
                            "event": "thinking",
                            "delta": chunk.reasoning_delta,
                        }
                    )

                if chunk.delta:
                    round_output += chunk.delta
                    round_visible_thinking += chunk.delta
                    self._output = round_output
                    round_message_events.append(
                        SSEChunkEncoder.encode(
                            {
                                "event": "message",
                                "delta": chunk.delta,
                            }
                        )
                    )

                if chunk.tool_calls:
                    round_tool_calls = self._merge_stream_tool_calls(
                        round_tool_calls,
                        chunk.tool_calls,
                    )

                if chunk.total_tokens is not None:
                    round_total_tokens = chunk.total_tokens
                if chunk.output_tokens is not None:
                    round_output_tokens = chunk.output_tokens

            next_runtime_context = None

            self._total_tokens += round_total_tokens
            self._completion_tokens_used += int(round_output_tokens or round_total_tokens)
            completion_reason = BudgetGuard.completion_reason(
                self._state.budget,
                completion_tokens=self._completion_tokens_used,
                total_tokens=self._total_tokens,
            )
            tc_list = self._finalize_stream_tool_calls(round_tool_calls)
            tc_list, truncated_after_navigation = (
                self.engine._truncate_tool_calls_after_navigation(tc_list)
            )
            if completion_reason:
                self._state.register_completion_tokens(self._completion_tokens_used)
                self._register_budget_exit(completion_reason)
                for event in round_message_events:
                    yield event
                self._output = round_output
                self._reasoning_output = round_reasoning_output
                break
            if truncated_after_navigation:
                logger.info(
                    "Truncated streamed assistant tool call batch after navigation op to avoid stale page follow-up calls: {}",
                    [
                        str((tc.get("function") or {}).get("name") or tc.get("name") or "")
                        for tc in tc_list
                    ],
                )

            if not tc_list:
                denial_response = self._build_text_round_response(
                    content=round_output,
                    reasoning_content=round_reasoning_output,
                    total_tokens=round_total_tokens,
                )
                self._state.register_completion_tokens(self._completion_tokens_used)
                decision = RecoveryManager.decide(
                    self._state.intent_plan,
                    budget=self._state.budget,
                    provider_failure_kind=self._state.provider_failure_kind,
                )
                if decision is not None and decision.action == "retry_intent":
                    analyzed_breach_type, analyzed_retry_policy, _analyzed_diagnostics = (
                        self.engine._analyze_post_tool_contract_breach(
                            messages=messages,
                            response=denial_response,
                            current_policy=round_tool_policy,
                            tools=getattr(self.prep, "all_tools", None) or tools_full,
                            input_variables=getattr(
                                self.request,
                                "input_variables",
                                None,
                            ),
                        )
                    )
                    del analyzed_breach_type, _analyzed_diagnostics
                    retry_reason = (
                        analyzed_retry_policy.reason
                        if analyzed_retry_policy is not None
                        else (
                            "web_research_summary_without_fetch"
                            if (
                                decision.retry_family == "web_research"
                                and self.engine._needs_fetch_url_before_summary(messages)
                            )
                            else decision.reason
                        )
                    )
                    retry_policy = ToolUsePolicy(
                        family=decision.retry_family
                        or getattr(self.prep, "tool_use_policy", ToolUsePolicy()).family,
                        mode="required",
                        allowed_tool_names=decision.allowed_tool_names
                        or [tool.name for tool in tools_full],
                        retry_on_contract_breach=False,
                        reason=retry_reason,
                    )
                    self.engine._log_tool_contract_diagnostics(
                        agent=self.agent,
                        messages=messages,
                        response=denial_response,
                        tools=tools_full,
                        policy=retry_policy,
                        conversation_id=self.request.conversation_id,
                        breach_type="stream_capability_denial_or_no_tool_use",
                        retry_result="retrying",
                        continuation=continuation_context,
                    )
                    self._state.register_retry(decision)
                    messages.append(
                        RecoveryManager.build_recovery_message(
                            decision=decision,
                            intents=self._state.intent_plan,
                        )
                    )
                    retry_tools = self.engine._restrict_tools_to_names(
                        getattr(self.prep, "all_tools", None) or tools_full,
                        decision.allowed_tool_names,
                    )
                    tools_full = list(retry_tools or tools_full)
                    round_tool_policy = retry_policy
                    forced_tool_names = (
                        list(decision.allowed_tool_names)
                        if decision.allowed_tool_names
                        else forced_tool_names
                    )
                    self._update_turn_progress(
                        tool_loop_progress={
                            "retry_intent": decision.target_intent_id,
                            "retry_allowed_tools": list(decision.allowed_tool_names),
                        }
                    )
                    next_runtime_context = None
                    continue
                if round_tool_policy.mode == "required" and self._state.recovery_history:
                    self.engine._log_tool_contract_diagnostics(
                        agent=self.agent,
                        messages=messages,
                        response=denial_response,
                        tools=tools_full,
                        policy=round_tool_policy,
                        conversation_id=self.request.conversation_id,
                        breach_type="stream_capability_denial_or_no_tool_use",
                        retry_result="failed",
                        continuation=continuation_context,
                    )

                for event in round_message_events:
                    yield event
                self._output = round_output
                self._reasoning_output = round_reasoning_output
                break

            for event in round_message_events:
                yield event
            tool_round_reason = BudgetGuard.tool_round_reason(
                self._state.budget,
                next_rounds_used=(
                    int(getattr(self._state.budget, "tool_rounds_used", 0) or 0) + 1
                    if self._state.budget is not None
                    else 1
                ),
            )
            if tool_round_reason:
                self._register_budget_exit(tool_round_reason)
                break
            self._state.register_tool_round()
            messages.append(
                processor.build_assistant_tool_call_message(
                    content=round_output,
                    tool_calls=tc_list,
                    reasoning_content=round_visible_thinking or None,
                )
            )
            if round_tool_policy.mode == "required" and (
                round_tool_policy.reason.startswith("capability_denial:")
                or round_tool_policy.reason.startswith("required_retry:")
            ):
                self.engine._log_tool_contract_diagnostics(
                    agent=self.agent,
                    messages=messages,
                    response=self._build_text_round_response(
                        content=round_output,
                        reasoning_content="",
                        total_tokens=round_total_tokens,
                    ),
                    tools=tools_full,
                    policy=round_tool_policy,
                    conversation_id=self.request.conversation_id,
                    breach_type="stream_capability_denial_or_no_tool_use",
                    retry_result="succeeded",
                    continuation=continuation_context,
                )
            follow_up_messages: list[ChatMessage] = []

            round_has_confirmation = False

            # Execute tools one by one and push SSE events immediately / 逐个执行工具并立即推送 SSE 事件
            for tc in tc_list:
                tc_id = tc.get("id", "")
                func = tc.get("function", {})
                func_name = func.get("name", "")
                operation_name = self.engine._tool_call_operation_name(tc)
                raw_args = func.get("arguments", "{}")
                arguments, parse_error = processor.parse_arguments(raw_args)
                self._interrupted_stage = (
                    f"tool_loop_round_{_round + 1}:tool:{func_name or 'unknown'}"
                )
                self._update_turn_progress(
                    last_tool_name=func_name or None,
                    last_page_op=operation_name or None,
                    tool_loop_progress={
                        "round": _round + 1,
                        "last_round_tool_names": [
                            self.engine._tool_call_name(item)
                            for item in tc_list
                            if isinstance(item, dict)
                            and self.engine._tool_call_name(item)
                        ],
                    },
                )

                # JSON parse failure: do not execute, push error result instead / JSON 解析失败：不执行，推送错误结果
                # Parse error 也纳入连续 pageop/invoke 失败计数，达阈值后熔断
                if parse_error:
                    raw_snippet = (
                        (raw_args[:500] + "…")
                        if isinstance(raw_args, str) and len(raw_args) > 500
                        else raw_args
                    )
                    logger.warning(
                        "Tool JSON parse failed: tool={} error={} raw_args_snippet={}",
                        func_name,
                        parse_error,
                        repr(raw_snippet)[:600],
                    )
                    from app.ai.tools.types import ToolResult

                    err_msg = _("page_operation.error.json_parse_failed")
                    if func_name and func_name.startswith("data_"):
                        _consecutive_data_op_failures += 1
                        err_msg += " " + _("data_intelligence.crud.json_parse_guidance")
                        if _consecutive_data_op_failures >= 2:
                            err_msg += " " + _(
                                "data_intelligence.crud.json_parse_guidance_tip"
                            )
                    err_result = ToolResult(
                        tool_call_id=tc_id,
                        name=func_name or "unknown",
                        success=False,
                        error=err_msg,
                        error_type=parse_error,
                    )
                    all_tool_results.append(err_result)
                    yield SSEChunkEncoder.encode(
                        processor.build_tool_call_event(
                            err_result,
                            0,
                            processor.get_skill_info(func_name),
                            name_override=func_name,
                        ),
                    )
                    messages.append(processor.build_tool_message(err_result, tc_id))
                    round_tool_results.append(err_result)
                    self._update_turn_progress(
                        interrupted_stage=(
                            f"tool_loop_round_{_round + 1}:parse_error:{func_name or 'unknown'}"
                        ),
                    )

                    # Count parse error as page op failure (circuit breaking) / parse error 计入页面操作失败以触发熔断
                    _is_page_op = func_name == "invoke_page_operation" or (
                        func_name.startswith("pageop_") if func_name else False
                    )
                    if _is_page_op:
                        _consecutive_page_op_failures += 1
                        if _consecutive_page_op_failures >= PAGE_OP_ABORT_THRESHOLD:
                            logger.warning(
                                "Aborting tool loop: {} consecutive page op failures (incl. parse errors) conversation={}",
                                _consecutive_page_op_failures,
                                self.request.conversation_id,
                            )
                            _page_op_aborted = True
                            self._output = (
                                round_output.strip()
                                + "\n\n"
                                + _("page_operation.error.multiple_failures_parse")
                            )

                    if _page_op_aborted:
                        break
                    continue

                _skill_info = processor.get_skill_info(func_name)
                processor.annotate_tool_call(tc, skill_info=_skill_info)

                # ---- consent_mode pre-check ---- / consent_mode 前置检查
                _consent = processor.check_consent(func_name)

                if _consent == "reject":
                    messages.append(processor.build_consent_reject_message(tc_id))
                    yield SSEChunkEncoder.encode(
                        processor.build_consent_reject_event(
                            func_name,
                            _skill_info,
                        )
                    )
                    continue

                if _consent == "ask":
                    processor.annotate_tool_call(
                        tc,
                        pending_consent=processor.build_pending_consent_payload(
                            func_name,
                            arguments,
                            _skill_info,
                        ),
                    )
                    messages.append(
                        processor.build_consent_ask_message(
                            tc_id,
                            func_name,
                            arguments,
                        )
                    )
                    yield SSEChunkEncoder.encode(
                        processor.build_consent_ask_event(
                            func_name,
                            arguments,
                            _skill_info,
                        )
                    )
                    round_has_confirmation = True
                    continue

                # ---- auto: normal execution ---- / auto: 正常执行
                yield SSEChunkEncoder.encode(
                    processor.build_tool_start_event(
                        func_name,
                        arguments,
                        _skill_info,
                        tool_call_id=tc_id,
                    )
                )

                result, tc_duration = await processor.execute_tool(
                    tc_id,
                    func_name,
                    arguments,
                    conversation_id=self.request.conversation_id or 0,
                )
                if result.success:
                    self.engine._mark_multi_family_progress(
                        func_name=func_name,
                        success=True,
                        ordered_requested_families=ordered_requested_families,
                        completed_families=completed_families,
                        has_fetch_url_in_toolset=has_fetch_url_in_toolset,
                        input_variables=getattr(self.request, "input_variables", None),
                    )
                all_tool_results.append(result)
                round_tool_results.append(result)
                processor.annotate_tool_call(
                    tc,
                    duration_ms=tc_duration,
                    result=result,
                    skill_info=_skill_info,
                )

                # Track consecutive page op failures; abort to avoid apology loops / 连续页面操作失败则中止，避免道歉循环
                _is_page_op = func_name == "invoke_page_operation" or (
                    func_name.startswith("pageop_") if func_name else False
                )
                if _is_page_op:
                    if result.success:
                        _consecutive_page_op_failures = 0
                    else:
                        _consecutive_page_op_failures += 1
                        if _consecutive_page_op_failures >= PAGE_OP_ABORT_THRESHOLD:
                            logger.warning(
                                "Aborting tool loop: {} consecutive page operation failures (conversation={})",
                                _consecutive_page_op_failures,
                                self.request.conversation_id,
                            )
                            _page_op_aborted = True
                            self._output = (
                                round_output.strip()
                                + "\n\n"
                                + _("page_operation.error.multiple_failures_sequence")
                            )
                elif func_name and func_name.startswith("data_") and result.success:
                    _consecutive_data_op_failures = 0

                # Push tool_result event / 推送 tool_result 事件（name_override 保持与 tool_start 一致，避免前端匹配失败）
                yield SSEChunkEncoder.encode(
                    processor.build_tool_call_event(
                        result,
                        tc_duration,
                        _skill_info,
                        name_override=func_name,
                    )
                )

                # Detect confirmation_request (CRUD preview confirmation) / 检测 confirmation_request（CRUD 预览确认）
                _conf_data = processor.check_confirmation_output(result)
                if _conf_data:
                    processor.annotate_tool_call(
                        tc,
                        pending_confirmation=processor.build_pending_confirmation_payload(
                            _conf_data,
                        ),
                    )
                    round_has_confirmation = True
                    yield SSEChunkEncoder.encode(
                        processor.build_confirmation_event(_conf_data)
                    )

                # Append tool message / 追加 tool 消息
                messages.append(processor.build_tool_message(result, tc_id))
                _follow_up_message = processor.build_attachment_relay_message(result)
                if _follow_up_message:
                    follow_up_messages.append(_follow_up_message)
                self._state.register_tool_results(
                    messages=messages,
                    tool_results=[result],
                )
                self._register_tool_failures([result])
                tool_result_budget_reason = self._state.budget_exit_reason()
                if tool_result_budget_reason:
                    self._register_budget_exit(tool_result_budget_reason)
                self._update_turn_progress(
                    last_tool_name=func_name or None,
                    last_page_op=operation_name or None,
                    tool_loop_progress={
                        "round": _round + 1,
                        "last_tool_success": bool(result.success),
                    },
                )

                if _page_op_aborted or self._state.provider_failure_kind == "budget_exit":
                    break

            if (
                follow_up_messages
                and not round_has_confirmation
                and not _page_op_aborted
            ):
                messages.extend(follow_up_messages)

            recovery_hint, recovery_tool_names, recovery_diagnostics = (
                self.engine._build_page_no_progress_recovery(
                    messages=messages,
                    tool_calls=tc_list,
                    tool_results=round_tool_results,
                    tools=getattr(self.prep, "all_tools", None) or tools_full,
                    input_variables=getattr(self.request, "input_variables", None),
                )
            )
            if recovery_hint and not round_has_confirmation and not _page_op_aborted:
                forced_tool_names = recovery_tool_names
                messages.append(ChatMessage(role="system", content=recovery_hint))
                self._update_turn_progress(
                    last_page_key=recovery_diagnostics.get("current_page_key"),
                    tool_loop_progress={
                        "page_recovery_reason": recovery_diagnostics.get("reason"),
                        "forced_tool_names": recovery_tool_names,
                    }
                )
                logger.info(
                    "Injected streamed page-flow recovery hint after no-progress page round: conversation_id={} diagnostics={}",
                    self.request.conversation_id,
                    recovery_diagnostics,
                )
            elif len(ordered_requested_families) > 1:
                if not self.engine._messages_have_blocking_pending_interaction(
                    messages
                ):
                    focus = self.engine._first_incomplete_requested_family(
                        ordered_requested_families,
                        completed_families,
                    )
                    forced_tool_names = (
                        None
                        if focus is None
                        else self.engine._allowed_tool_names_for_family(
                            focus,
                            getattr(self.prep, "all_tools", None) or tools_full,
                            getattr(self.request, "input_variables", None),
                        )
                    )
            elif forced_tool_names:
                forced_tool_names = None

            executed_web_research_round = (
                round_tool_policy.family == "web_research"
                and any(
                    ((tc.get("function") or {}).get("name") or "")
                    in {"web_search", "fetch_url"}
                    for tc in tc_list
                    if isinstance(tc, dict)
                )
            )
            if self._state.provider_failure_kind == "budget_exit":
                break

            if executed_web_research_round:
                round_tool_policy = ToolUsePolicy(
                    family="web_research",
                    mode="required",
                    allowed_tool_names=[tool.name for tool in tools_full],
                    retry_on_contract_breach=False,
                    reason="post_tool_web_research",
                )
            else:
                round_tool_policy = ToolUsePolicy(
                    family="none",
                    mode="auto",
                    allowed_tool_names=[tool.name for tool in tools_full],
                    retry_on_contract_breach=False,
                    reason="post_tool_auto",
                )

            if round_has_confirmation or _page_op_aborted:
                if round_has_confirmation:
                    self._output = round_output.strip()
                    self._reasoning_output = round_reasoning_output.strip()
                    # Round already has assistant(tool_calls); do not duplicate plain assistant / 本轮已有 tool_calls，勿再追加纯文本 assistant
                    append_final_assistant = False
                break
        else:
            logger.warning(
                "Tool call rounds exceeded max: conversation={} max_rounds={}",
                self.request.conversation_id,
                round_limit,
            )
            self._register_budget_exit("tool_round_budget_exceeded")

        if append_final_assistant and (self._output or "").strip():
            final_output, final_action_buttons = self._extract_action_buttons(
                self._output
            )
            self._output = final_output
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=final_output,
                    reasoning_content=(self._reasoning_output or "").strip() or None,
                    metadata=(
                        {"action_buttons": final_action_buttons}
                        if final_action_buttons
                        else None
                    ),
                )
            )

    # ========================================
    # Tool Call Incremental Aggregation / 工具调用增量聚合
    # ========================================

    @staticmethod
    def _normalize_stream_tool_call(tool_call: Any) -> dict[str, Any] | None:
        """
        Normalize streaming tool_call delta, compatible with both dict and SDK object formats. / 归一化流式 tool_call 增量，兼容 dict 与 SDK 对象。
        """
        if not tool_call:
            return None

        if isinstance(tool_call, dict):
            index = tool_call.get("index")
            tc_id = tool_call.get("id") or ""
            tc_type = tool_call.get("type") or "function"
            func = tool_call.get("function") or {}
            if not isinstance(func, dict):
                func = {}
            func_name = func.get("name") or ""
            func_arguments = func.get("arguments") or ""
        else:
            index = getattr(tool_call, "index", None)
            tc_id = getattr(tool_call, "id", None) or ""
            tc_type = getattr(tool_call, "type", None) or "function"
            func_obj = getattr(tool_call, "function", None)
            if isinstance(func_obj, dict):
                func_name = func_obj.get("name") or ""
                func_arguments = func_obj.get("arguments") or ""
            else:
                func_name = getattr(func_obj, "name", None) or ""
                func_arguments = getattr(func_obj, "arguments", None) or ""

        if isinstance(index, str) and index.isdigit():
            index = int(index)
        if not isinstance(index, int):
            index = None

        return {
            "_index": index,
            "id": tc_id,
            "type": tc_type,
            "function": {
                "name": func_name,
                "arguments": func_arguments,
            },
        }

    @classmethod
    def _merge_stream_tool_calls(
        cls,
        existing: list[dict[str, Any]],
        incoming: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Merge streaming tool_call deltas, supports OpenAI-style index incremental concatenation. / 合并流式 tool_call 增量，支持 OpenAI 风格 index 增量拼接。
        """
        merged = existing[:]

        for raw_tc in incoming:
            tc = cls._normalize_stream_tool_call(raw_tc)
            if not tc:
                continue

            target: dict[str, Any] | None = None
            tc_index = tc.get("_index")
            tc_id = tc.get("id")

            if tc_index is not None:
                for item in merged:
                    if item.get("_index") == tc_index:
                        target = item
                        break

            if target is None and tc_id:
                for item in merged:
                    if item.get("id") == tc_id:
                        target = item
                        break

            if target is None:
                merged.append(tc)
                target = merged[-1]
            else:
                if tc_id and not target.get("id"):
                    target["id"] = tc_id

            target_func = target.setdefault("function", {})
            tc_func = tc.get("function", {})

            tc_name = tc_func.get("name") or ""
            if tc_name:
                cur_name = target_func.get("name", "")
                if not cur_name or tc_name.startswith(cur_name):
                    target_func["name"] = tc_name
                elif not cur_name.startswith(tc_name):
                    target_func["name"] = cur_name + tc_name

            tc_args = tc_func.get("arguments") or ""
            if tc_args:
                cur_args = target_func.get("arguments", "")
                if not cur_args or tc_args.startswith(cur_args):
                    target_func["arguments"] = tc_args
                elif not cur_args.startswith(tc_args):
                    target_func["arguments"] = cur_args + tc_args

        return merged

    @staticmethod
    def _finalize_stream_tool_calls(
        calls: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        清理内部字段并补齐默认值，输出可执行的 tool_call 列表 / Clean internal fields and fill defaults, output executable tool_call list.
        """
        finalized: list[dict[str, Any]] = []

        for idx, tc in enumerate(calls):
            func = tc.get("function") or {}
            name = (func.get("name") or "").strip()
            if not name:
                logger.warning("Skip invalid streamed tool_call without name: {}", tc)
                continue

            arguments = func.get("arguments")
            if arguments in (None, ""):
                arguments = "{}"

            tc_id = tc.get("id") or f"stream_tool_{idx}"
            if isinstance(arguments, str) and len(arguments) > 200:
                logger.debug(
                    "Finalized tool_call: name={} args_len={} args_head={}",
                    name,
                    len(arguments),
                    repr(arguments[:300]),
                )
            finalized.append(
                {
                    "id": tc_id,
                    "type": tc.get("type") or "function",
                    "function": {
                        "name": name,
                        "arguments": arguments,
                    },
                }
            )

        return finalized

    # ========================================
    # Action Buttons Parsing / Action Buttons 解析
    # ========================================

    _ACTION_START = "[ACTIONS]"
    _ACTION_END = "[/ACTIONS]"

    @staticmethod
    def _extract_action_buttons(
        output: str,
    ) -> tuple[str, list[dict[str, str]] | None]:
        """
        Extract button definitions from [ACTIONS]...[/ACTIONS] markers in LLM output.
        从 LLM 输出中提取 [ACTIONS]...[/ACTIONS] 标记中的按钮定义。

        Supported format / 支持格式:
            [ACTIONS]
            [{"label": "方案A", "value": "选择方案A", "style": "primary"}]
            [/ACTIONS]

        Returns:
            (cleaned_output, buttons) — Cleaned output and button list (None if no buttons)
            清理后的输出和按钮列表（无按钮时为 None）
        """
        start_idx = output.find(StreamExecutionHandler._ACTION_START)
        if start_idx < 0:
            return output, None

        end_idx = output.find(
            StreamExecutionHandler._ACTION_END,
            start_idx + len(StreamExecutionHandler._ACTION_START),
        )
        if end_idx < 0:
            return output, None

        raw = output[
            start_idx + len(StreamExecutionHandler._ACTION_START) : end_idx
        ].strip()
        try:
            buttons = json.loads(raw)
            if not isinstance(buttons, list):
                return output, None
            # Validate each button has at least label and value / 校验每个按钮至少有 label 和 value
            valid_buttons: list[dict[str, str]] = []
            for btn in buttons:
                if isinstance(btn, dict) and "label" in btn and "value" in btn:
                    item: dict[str, str] = {
                        "label": str(btn["label"]),
                        "value": str(btn["value"]),
                    }
                    if "style" in btn and btn["style"] in (
                        "primary",
                        "default",
                        "danger",
                    ):
                        item["style"] = btn["style"]
                    valid_buttons.append(item)
            if not valid_buttons:
                return output, None
            # Remove markers from output / 从输出中移除标记
            cleaned = (
                output[:start_idx]
                + output[end_idx + len(StreamExecutionHandler._ACTION_END) :]
            ).strip()
            return cleaned, valid_buttons
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to parse action buttons from LLM output")
            return output, None


__all__ = ["StreamExecutionHandler"]
