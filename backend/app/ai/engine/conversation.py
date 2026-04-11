"""
Conversation Execution Engine / 对话执行引擎

Supports multi-turn conversation, maintains session context, handles tool calling loop.
Supports SSE streaming output.
支持多轮对话，维护会话上下文，处理 tool calling 循环。
支持 SSE 流式输出。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.runtime import ConversationQueryEngine
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent

from .base import BaseEngine, log_user_type_for_call_log
from .conversation_result_projector import (
    build_execution_result,
    build_turn_projection,
)
from .conversation_runtime_accounting import (
    ConversationRuntimeAccounting,
)
from .conversation_runtime_bridge import (
    call_runtime_query_turn as _call_runtime_query_turn_impl,
)
from .conversation_runtime_bridge import (
    prepare_stream_runtime as _prepare_stream_runtime_impl,
)
from .conversation_runtime_bridge import (
    stream_llm_chunks as _stream_llm_chunks_impl,
)
from .conversation_runtime_preflight import (
    ConversationRuntimeContext,
    ConversationRuntimePreflight,
)
from .execution_state_machine import ExecutionStateMachine
from .failure_classifier import FailureClassifier
from .model_policy import build_model_request_overrides
from .recovery_manager import RecoveryManager
from .stream_handler import StreamExecutionHandler
from .stream_runtime_contract import (
    finalize_completed_turn_output,
    finalize_partial_turn_output,
)
from .tool_execution_helpers import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
from .tool_execution_helpers import (
    register_tool_failures as _register_tool_failures_impl,
)
from .tool_execution_helpers import (
    synthesize_tool_results_from_calls as _synthesize_tool_results_from_calls_impl,
)
from .turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from .turn_executor_helpers import (
    assistant_tool_round_count as _assistant_tool_round_count_impl,
)
from .turn_executor_helpers import (
    register_tool_round_delta as _register_tool_round_delta_impl,
)
from .types import (
    ExecutionRequest,
    ExecutionResult,
    ToolUsePolicy,
)

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")

# Compatibility seam: replay tests and legacy callers still import the old
# private runtime-context name while the implementation has moved to the
# focused preflight helper module.
_StreamRuntimeContext = ConversationRuntimeContext

@dataclass
class _SyncIOAdapter:
    engine: ConversationEngine
    agent: Agent
    request: ExecutionRequest
    prep: Any
    selected_skill_names: list[str]
    context_sources: list[Any]

    async def call_llm(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        tool_use_policy: ToolUsePolicy,
        **kwargs: Any,
    ) -> ModelRoundResult:
        runtime_call_overrides = build_model_request_overrides(
            execution_path=getattr(self.prep, "execution_path", None),
            tools=tools,
        )
        response = await self.engine._call_llm(
            agent=self.agent,
            messages=messages,
            tools=tools,
            all_tool_names=[tool.name for tool in self.prep.all_tools],
            tool_use_policy=tool_use_policy,
            tenant_id=self.request.tenant_id,
            user_id=self.request.user_id,
            conversation_id=self.request.conversation_id,
            billing_context=self.request.billing_context,
            route_result=self.prep.route_result,
            log_user_type=log_user_type_for_call_log(self.request.user_role),
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
            execution_path=getattr(self.prep, "execution_path", None),
            extra_kwargs=runtime_call_overrides or None,
            **kwargs,
        )
        total_tokens = int(response.total_tokens or 0)
        completion_tokens_used = int(
            response.output_tokens
            if response.output_tokens is not None
            else total_tokens
        )
        return ModelRoundResult(
            response=response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )

    async def handle_tool_calls(
        self,
        *,
        response: ChatResponse,
        tools: list[ToolDefinition],
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> ToolBatchResult:
        outcome = await self.engine._handle_tool_calls(
            agent=self.agent,
            messages=messages,
            response=response,
            tools=tools,
            all_tools=self.prep.all_tools,
            request=self.request,
            route_result=self.prep.route_result,
            tool_consent_modes=self.prep.tool_consent_modes,
            continuation_context=self.prep.continuation_context,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
            execution_budget=self.prep.execution_budget,
            **kwargs,
        )
        normalized_response, tool_results, total_tokens, completion_tokens_used = (
            self.engine._normalize_tool_call_outcome(outcome)
        )
        return ToolBatchResult(
            response=normalized_response,
            tool_results=list(tool_results),
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
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
        return await self.engine.finalize_partial_output(
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
        )

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
        return await self.engine.finalize_completed_output(
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=self.selected_skill_names,
            context_sources=self.context_sources,
        )

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.engine._should_retry_tool_contract_breach(
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
        return self.engine._should_retry_web_research_contract_breach(
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
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response is None:
            return None, None, {}
        return self.engine._analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def restrict_tools_to_names(
        self,
        tools: list[ToolDefinition],
        allowed_tool_names: list[str] | None,
    ) -> list[ToolDefinition]:
        return self.engine._restrict_tools_to_names(tools, allowed_tool_names)

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None:
        self.engine._log_tool_contract_diagnostics(
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
        _ = text


class ConversationEngine(BaseEngine):
    """
    Conversation Execution Engine / 对话执行引擎

    Handles multi-turn conversation scenarios:
    处理多轮对话场景：
    1. Build system message + history messages + new user message / 构建 system 消息 + 历史消息 + 新用户消息
    2. Call LLM / 调用 LLM
    3. If tool_calls returned, enter tool call loop / 如果返回 tool_calls，进入工具调用循环
    4. Return final assistant reply / 返回最终 assistant 回复

    Supports two output modes / 支持两种输出模式：
    - execute(): Non-streaming, returns complete result at once / 非流式，一次性返回完整结果
    - stream_execute(): SSE streaming, pushes token by token / SSE 流式，逐 token 推送
    """

    @staticmethod
    def _assistant_tool_round_count(messages: list[ChatMessage]) -> int:
        return _assistant_tool_round_count_impl(messages)

    @staticmethod
    def _register_tool_round_delta(
        state: ExecutionStateMachine,
        *,
        before_count: int,
        messages: list[ChatMessage],
    ) -> None:
        _register_tool_round_delta_impl(
            state,
            before_count=before_count,
            messages=messages,
        )

    @staticmethod
    def _register_tool_failures(
        state: ExecutionStateMachine,
        tool_results: list[Any],
    ) -> None:
        _register_tool_failures_impl(state, tool_results)

    @staticmethod
    def _normalize_tool_call_outcome(
        outcome: tuple[Any, ...],
    ) -> tuple[ChatResponse | None, list[Any], int, int]:
        return _normalize_tool_call_outcome_impl(outcome)

    @staticmethod
    def _synthesize_tool_results_from_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> list[ToolResult]:
        return _synthesize_tool_results_from_calls_impl(tool_calls)

    def _runtime_preflight(self) -> ConversationRuntimePreflight:
        return ConversationRuntimePreflight(
            db=self.db,
            gateway=self.gateway,
        )

    def _runtime_accounting(self) -> ConversationRuntimeAccounting:
        return ConversationRuntimeAccounting(
            gateway=self.gateway,
            db=self.db,
        )

    async def _finalize_partial_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await finalize_partial_turn_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def finalize_partial_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await finalize_partial_turn_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def _finalize_completed_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await finalize_completed_turn_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def finalize_completed_output(
        self,
        *,
        agent: Agent,
        request: ExecutionRequest,
        prep: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
        selected_skill_names: list[str],
        context_sources: list[Any],
    ) -> tuple[str, int, int]:
        return await finalize_completed_turn_output(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> ExecutionResult:
        """Execute conversation mode / 执行对话模式"""
        start = time.perf_counter()

        prep = None
        messages: list[ChatMessage] = []
        response: ChatResponse | None = None
        tool_results = []
        state: ExecutionStateMachine | None = None

        try:
            prep = await self._prepare_execution(agent, request, skill_result)
            messages = prep.messages
            rag_sources = prep.rag_sources
            runtime_selected_skill_names = (
                list(getattr(prep.capability_bundle, "selected_skill_names", []) or [])
                if prep.capability_bundle is not None
                else []
            )
            runtime_context_sources = (
                list(getattr(prep.capability_bundle, "context_sources", []) or [])
                if prep.capability_bundle is not None
                else []
            )
            state = ExecutionStateMachine.from_prepared_execution(prep)
            sync_io = _SyncIOAdapter(
                engine=self,
                agent=agent,
                request=request,
                prep=prep,
                selected_skill_names=runtime_selected_skill_names,
                context_sources=runtime_context_sources,
            )
            turn_execution = await TurnExecutor.run(
                state=state,
                io=sync_io,
                prep=prep,
                request=request,
                agent=agent,
            )
            response = turn_execution.response
            tool_results = list(turn_execution.tool_results)
            total_tokens = turn_execution.total_tokens
            output = turn_execution.output
            paused_for_consent = turn_execution.paused_for_consent
            partial = turn_execution.partial
            completion_reason = turn_execution.completion_reason
            final_output_source = turn_execution.final_output_source

            cleaned_output, action_buttons = (
                StreamExecutionHandler._extract_action_buttons(
                    output,
                )
            )
            if action_buttons:
                output = cleaned_output

            if output and not paused_for_consent:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=output,
                        metadata=(
                            {"action_buttons": action_buttons}
                            if action_buttons
                            else None
                        ),
                    )
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            response_metadata = dict(getattr(response, "metadata", {}) or {})
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
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
                runtime_model_info=response_metadata.get("runtime_model_info"),
                error="" if not partial else output,
                partial=partial,
                interrupted=paused_for_consent,
                completion_reason=completion_reason,
                rag_sources=rag_sources,
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

            if prep.context_engine is not None:
                await prep.context_engine.after_turn(
                    agent,
                    request,
                    result,
                )

            return result

        except (BusinessException, NotFoundException):
            raise

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "Conversation execution failed: agent={} error={}",
                agent.id,
                str(exc),
                exc_info=True,
            )
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
                        reason=decision.reason or "execution_exception",
                        provider_failure_kind=state.provider_failure_kind,
                    )
            completion_reason = (
                decision.reason
                if partial_output and decision is not None and decision.reason
                else "error"
            )
            return ExecutionResult(
                success=False,
                output=partial_output,
                messages=self._messages_to_dicts(messages) if messages else [],
                tool_results=tool_results,
                error=build_public_error_text(
                    message=_("common.server_error"),
                    exc=exc,
                ),
                partial=bool(partial_output),
                completion_reason=completion_reason,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
                rag_sources=(prep.rag_sources if prep is not None else None),
                rag_source_kinds=(prep.rag_source_kinds if prep is not None else []),
                context_compacted=bool(getattr(prep, "context_compacted", False)),
                memory_flush_triggered=bool(
                    getattr(prep, "memory_flush_triggered", False)
                ),
                memory_recalled=bool(getattr(prep, "memory_recalled", False)),
                prune_stats=getattr(prep, "prune_stats", None),
                tool_planner=getattr(prep, "tool_planner", None),
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
                provider_failure_kind=kind,
                provider_events=[event] if event else [],
                diagnostics=diagnostics_payload,
            )

    async def _call_runtime_query_turn(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        all_tool_names: list[str] | None,
        tool_use_policy: ToolUsePolicy | None,
        breach_retry_result: str | None,
        tenant_id: int | None,
        user_id: int | None,
        conversation_id: int | None,
        billing_context: dict[str, Any] | None,
        route_result: Any | None,
        log_user_type: str | None,
        selected_skill_names: list[str] | None,
        context_sources: list[Any] | None,
        execution_path: str | None,
        extra_kwargs: dict[str, Any] | None,
        skip_metering_preflight: bool,
    ) -> tuple[ChatResponse, ConversationQueryEngine]:
        _ = skip_metering_preflight
        return await _call_runtime_query_turn_impl(
            self,
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=all_tool_names,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            execution_path=execution_path,
            extra_kwargs=extra_kwargs,
            adapter_registry=AdapterRegistry,
            query_engine_cls=ConversationQueryEngine,
            model_request_override_builder=build_model_request_overrides,
            engine_logger=logger,
        )

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        route_result: Any | None = None,
        log_user_type: str | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        execution_path: str | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        runtime_call_overrides = dict(extra_kwargs or {})
        if not runtime_call_overrides:
            runtime_call_overrides = build_model_request_overrides(
                execution_path=execution_path,
                tools=tools,
            )
        runtime_response, _runtime_query_engine = await self._call_runtime_query_turn(
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=all_tool_names,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            execution_path=execution_path,
            extra_kwargs=runtime_call_overrides,
            skip_metering_preflight=False,
        )
        return runtime_response

    # ========================================
    # SSE Streaming Execution / SSE 流式执行
    # ========================================

    async def stream_execute(
        self,
        agent: Agent,
        request: ExecutionRequest,
        on_complete: Callable[
            [ExecutionResult],
            Awaitable[dict[str, Any] | None],
        ]
        | None = None,
        skill_result: SkillResolveResult | None = None,
    ) -> StreamingResponse:
        """
        SSE streaming conversation execution.
        SSE 流式执行对话。

        Event types / 事件类型：
        - message: Content delta / 内容增量
        - tool_call: Tool call result / 工具调用
        - done: Completion / 完成
        - [DONE]: SSE end marker / SSE 结束标记

        Execution strategy / 执行策略：
        - Without tools: Real streaming via adapter / 无工具时通过 adapter 真实流式推送 token
        - With tools: Each round uses real stream_chat, executes tools after detecting tool_calls
          有工具时每轮走真实 stream_chat，检测到 tool_calls 后执行工具并进入下一轮

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求
            on_complete: Callback after stream completion (for message persistence etc.) / 流式完成后的回调

        Returns:
            StreamingResponse (SSE)
        """
        start = time.perf_counter()

        # Shared pre-logic (Skill resolve + message building + RAG + tool optimization) / 共享前置逻辑
        prep = await self._prepare_execution(agent, request, skill_result)
        prep.stream_runtime = await self._prepare_stream_runtime(
            agent=agent,
            messages=prep.messages,
            tenant_id=request.tenant_id,
            route_result=prep.route_result,
        )

        handler = StreamExecutionHandler(
            engine=self,
            agent=agent,
            request=request,
            prep=prep,
            start_time=start,
            on_complete=on_complete,
        )

        return StreamingResponse(
            handler.generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ========================================
    # Internal: Streaming LLM Call / 内部方法：流式 LLM 调用
    # ========================================

    async def _stream_llm_chunks(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None = None,
        conversation_id: int | None = None,
        route_result: Any | None = None,
        tools: list[ToolDefinition] | None = None,
        execution_path: str | None = None,
        user_id: int | None = None,
        log_user_type: str | None = None,
        billing_context: dict[str, Any] | None = None,
        runtime_context: ConversationRuntimeContext | None = None,
        all_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in _stream_llm_chunks_impl(
            self,
            agent=agent,
            messages=messages,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            route_result=route_result,
            tools=tools,
            execution_path=execution_path,
            user_id=user_id,
            log_user_type=log_user_type,
            billing_context=billing_context,
            runtime_context=runtime_context,
            all_tool_names=all_tool_names,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            adapter_registry=AdapterRegistry,
            query_engine_cls=ConversationQueryEngine,
            model_request_override_builder=build_model_request_overrides,
            engine_logger=logger,
        ):
            yield chunk

    async def _prepare_stream_runtime(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None,
        route_result: Any | None = None,
        skip_metering_preflight: bool = False,
    ) -> ConversationRuntimeContext:
        return await _prepare_stream_runtime_impl(
            self,
            agent=agent,
            messages=messages,
            tenant_id=tenant_id,
            route_result=route_result,
            skip_metering_preflight=skip_metering_preflight,
        )


__all__ = ["ConversationEngine"]
