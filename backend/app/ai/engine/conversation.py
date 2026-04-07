"""
Conversation Execution Engine / 对话执行引擎

Supports multi-turn conversation, maintains session context, handles tool calling loop.
Supports SSE streaming output.
支持多轮对话，维护会话上下文，处理 tool calling 循环。
支持 SSE 流式输出。
"""

from __future__ import annotations

import inspect
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.ai.adapters import AdapterRegistry
from app.ai.runtime import ConversationQueryEngine
from app.ai.text_semantics import strip_model_function_call_markup
from app.ai.tools.types import ToolDefinition, ToolResult, to_openai_tools
from app.ai.types import ChatChunk, ChatMessage, ChatResponse, messages_to_dicts
from app.ai.usage_mode import resolve_chat_usage
from app.ai.usage_recorder import UsageRecorder
from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.ai import CallStatusEnum, RequestTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.services.ai.usage_metrics import CostCalculator, TokenCounter

from .base import BaseEngine, log_user_type_for_call_log
from .budget_guard import BudgetGuard
from .execution_state_machine import ExecutionStateMachine
from .failure_classifier import FailureClassifier
from .model_policy import build_model_request_overrides
from .recovery_manager import RecoveryManager
from .stream_handler import StreamExecutionHandler
from .turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from .types import (
    ExecutionRequest,
    ExecutionResult,
    ToolUsePolicy,
)

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")


@dataclass
class _StreamRuntimeContext:
    provider: Any
    api_key: Any
    ai_model: Any
    model_code: str
    is_vision: bool
    is_audio: bool
    is_video: bool
    estimated_input: int
    metering_context: Any
    should_meter_usage: bool
    should_record_call_log: bool
    runtime_info: dict[str, Any]


def _strip_model_fc_tokens(text: str) -> str:
    """Filter leaked internal function call markers from model output (DeepSeek ｜DSML｜ etc.) / 过滤模型泄漏的内部 function call 标记"""
    return strip_model_function_call_markup(text)


async def _await_if_needed(value: Awaitable[Any] | Any) -> Any:
    """Await async collaborators while tolerating sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


def _serialize_context_sources(
    context_sources: list[Any] | None,
) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for source in context_sources or []:
        if isinstance(source, dict):
            serialized.append(
                {
                    "kind": str(source.get("kind") or "").strip() or None,
                    "name": str(source.get("name") or "").strip() or None,
                    "active": bool(source.get("active", True)),
                    "metadata": dict(source.get("metadata") or {}),
                }
            )
            continue
        if source is None:
            continue
        serialized.append(
            {
                "kind": str(getattr(source, "kind", "") or "").strip() or None,
                "name": str(getattr(source, "name", "") or "").strip() or None,
                "active": bool(getattr(source, "active", True)),
                "metadata": dict(getattr(source, "metadata", {}) or {}),
            }
        )
    return serialized


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
        return await self.engine._finalize_partial_output(
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
        return sum(
            1
            for message in messages
            if message.role == "assistant" and bool(message.tool_calls)
        )

    @staticmethod
    def _register_tool_round_delta(
        state: ExecutionStateMachine,
        *,
        before_count: int,
        messages: list[ChatMessage],
    ) -> None:
        delta = max(
            0,
            ConversationEngine._assistant_tool_round_count(messages) - before_count,
        )
        for _tool_round in range(delta):
            state.register_tool_round()

    @staticmethod
    def _register_tool_failures(
        state: ExecutionStateMachine,
        tool_results: list[Any],
    ) -> None:
        tool_failure_kind, tool_failure_events = (
            FailureClassifier.classify_tool_results(tool_results)
        )
        if tool_failure_kind != "none":
            for event in tool_failure_events:
                state.register_provider_failure(
                    kind=tool_failure_kind,
                    event=event,
                )

    @staticmethod
    def _normalize_tool_call_outcome(
        outcome: tuple[Any, ...],
    ) -> tuple[ChatResponse | None, list[Any], int, int]:
        if len(outcome) == 4:
            response, tool_results, total_tokens, completion_tokens_used = outcome
            return response, tool_results, total_tokens, completion_tokens_used
        if len(outcome) == 3:
            response, tool_results, total_tokens = outcome
            completion_tokens_used = int(
                getattr(response, "output_tokens", None)
                if getattr(response, "output_tokens", None) is not None
                else (total_tokens or 0)
            )
            return response, tool_results, total_tokens, completion_tokens_used
        raise ValueError(
            f"Unexpected tool call outcome shape: expected 3 or 4 items, got {len(outcome)}"
        )

    @staticmethod
    def _synthesize_tool_results_from_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> list[ToolResult]:
        synthesized: list[ToolResult] = []
        for index, tool_call in enumerate(tool_calls or []):
            function_block = tool_call.get("function") or {}
            tool_name = str(
                function_block.get("name") or tool_call.get("name") or ""
            ).strip()
            if not tool_name:
                continue
            tool_call_id = str(tool_call.get("id") or f"synthetic_tool_call_{index}")
            synthesized.append(
                ToolResult(
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    success=True,
                )
            )
        return synthesized

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
        _ = (
            agent,
            request,
            prep,
            messages,
            tool_results,
            selected_skill_names,
            context_sources,
        )
        visible_output = (
            str(response.message.content or "").strip()
            if response is not None
            else ""
        )
        if visible_output:
            return visible_output, total_tokens, completion_tokens_used
        return (
            RecoveryManager.build_partial_output(
                state.intent_plan,
                reason=reason,
                provider_failure_kind=state.provider_failure_kind,
            ),
            total_tokens,
            completion_tokens_used,
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
            completion_tokens_used = turn_execution.completion_tokens_used
            output = turn_execution.output
            paused_for_consent = turn_execution.paused_for_consent
            partial = turn_execution.partial
            completion_reason = turn_execution.completion_reason

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
            runtime_info = response_metadata.get("runtime_model_info", {})
            turn_record = response_metadata.get("runtime_turn_record")
            if isinstance(turn_record, dict):
                turn_record_payload = dict(turn_record)
            elif turn_record is not None and hasattr(
                turn_record, "__dataclass_fields__"
            ):
                turn_record_payload = asdict(turn_record)
            elif turn_record is not None and hasattr(turn_record, "__dict__"):
                turn_record_payload = dict(getattr(turn_record, "__dict__", {}) or {})
            else:
                turn_record_payload = {}
            diagnostics_payload = state.build_diagnostics_payload()
            if partial:
                diagnostics_payload["partial_exit_reason"] = (
                    completion_reason or diagnostics_payload.get("partial_exit_reason")
                )
            turn_record_payload.update(
                {
                    "execution_path": prep.execution_path,
                    "intent_plan": diagnostics_payload.get("intent_plan"),
                    "budget": diagnostics_payload.get("budget"),
                    "budget_status": diagnostics_payload.get("budget_status"),
                    "budget_exit_reason": diagnostics_payload.get("budget_exit_reason"),
                    "candidate_tool_names": diagnostics_payload.get(
                        "candidate_tool_names"
                    ),
                    "retry_events": diagnostics_payload.get("retry_events"),
                    "partial_exit_reason": diagnostics_payload.get(
                        "partial_exit_reason"
                    ),
                    "unfinished_intents": diagnostics_payload.get("unfinished_intents"),
                    "provider_events": diagnostics_payload.get("provider_events"),
                    "failure_kind": diagnostics_payload.get("failure_kind"),
                }
            )
            raw_turn_outcome = str(turn_record_payload.get("turn_outcome") or "").strip()
            raw_termination_reason = str(
                turn_record_payload.get("termination_reason") or ""
            ).strip()
            partial_exit_reason = str(
                diagnostics_payload.get("partial_exit_reason") or ""
            ).strip()
            if partial and completion_reason:
                turn_record_payload["turn_outcome"] = "partial"
                turn_record_payload["termination_reason"] = completion_reason
                turn_record_payload["partial_exit_reason"] = (
                    partial_exit_reason or completion_reason
                )
            else:
                if raw_turn_outcome:
                    turn_record_payload["turn_outcome"] = raw_turn_outcome
                if raw_termination_reason:
                    turn_record_payload["termination_reason"] = raw_termination_reason
                if partial_exit_reason:
                    turn_record_payload["partial_exit_reason"] = partial_exit_reason
            metadata = dict(turn_record_payload.get("metadata") or {})
            metadata["orchestration"] = diagnostics_payload
            turn_record_payload["metadata"] = metadata

            result = ExecutionResult(
                success=not partial,
                output=output,
                messages=self._messages_to_dicts(messages),
                tool_results=tool_results,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                conversation_id=request.conversation_id,
                runtime_model_id=runtime_info.get("model_id"),
                runtime_model_name=runtime_info.get("model_name"),
                runtime_provider_id=runtime_info.get("provider_id"),
                runtime_provider_name=runtime_info.get("provider_name"),
                error="" if not partial else output,
                partial=partial,
                completion_reason=completion_reason,
                rag_sources=rag_sources,
                rag_source_kinds=prep.rag_source_kinds,
                context_compacted=prep.context_compacted,
                memory_flush_triggered=prep.memory_flush_triggered,
                memory_recalled=prep.memory_recalled,
                prune_stats=prep.prune_stats,
                tool_planner=prep.tool_planner,
                turn_record=turn_record_payload,
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
                diagnostics=diagnostics_payload,
            )

            if paused_for_consent:
                result.success = False
                result.interrupted = True

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
        runtime_context = await self._prepare_stream_runtime(
            agent=agent,
            messages=messages,
            tenant_id=tenant_id,
            route_result=route_result,
            skip_metering_preflight=skip_metering_preflight,
        )
        provider = runtime_context.provider
        api_key = runtime_context.api_key
        ai_model = runtime_context.ai_model
        model_code = runtime_context.model_code
        is_vision = runtime_context.is_vision
        is_audio = runtime_context.is_audio
        is_video = runtime_context.is_video
        estimated_input = runtime_context.estimated_input
        metering_context = runtime_context.metering_context

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
            provider_config=provider.config,
            internal_db=self.db,
            internal_tenant_id=tenant_id,
            model_config=getattr(ai_model, "config", None),
        )
        openai_tools = to_openai_tools(tools) if tools else None
        effective_policy = tool_use_policy or ToolUsePolicy(
            family="none",
            mode="auto" if tools else "none",
            allowed_tool_names=[tool.name for tool in (tools or [])],
            retry_on_contract_breach=False,
            reason="implicit_auto",
        )
        effective_tool_choice = (
            effective_policy.mode
            if openai_tools and effective_policy.mode in {"auto", "required"}
            else None
        )
        runtime_context_sources = _serialize_context_sources(context_sources)
        query_engine = ConversationQueryEngine(
            adapter=adapter,
            strict_contract=(effective_tool_choice == "required"),
        )
        request_log_data = {
            "_runtime_v2_non_stream": True,
            "messages": messages_to_dicts(messages),
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "top_p": agent.top_p or 1.0,
            "tools": openai_tools,
            "tool_choice": effective_tool_choice,
            "selected_tool_names": [tool.name for tool in (tools or [])],
            "all_tool_names": all_tool_names or [tool.name for tool in (tools or [])],
            "tool_use_policy": {
                "family": effective_policy.family,
                "mode": effective_policy.mode,
                "allowed_tool_names": effective_policy.allowed_tool_names,
            },
            "breach_retry_result": breach_retry_result,
        }
        routed_model_id = (
            int(getattr(route_result, "model_id", 0) or 0)
            if route_result is not None
            and getattr(route_result, "is_overridden", False)
            else None
        )
        route_reason = (
            route_result.reason
            if route_result is not None
            and getattr(route_result, "is_overridden", False)
            else None
        )
        call_start = time.perf_counter()

        try:
            response = await query_engine.run_chat_turn(
                messages=messages,
                model=model_code,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                top_p=agent.top_p or 1.0,
                tools=openai_tools,
                tool_choice=effective_tool_choice,
                supports_vision=bool(is_vision),
                supports_audio=bool(is_audio),
                supports_video=bool(is_video),
                selected_skill_names=list(selected_skill_names or []),
                context_sources=runtime_context_sources,
                extra_kwargs=dict(extra_kwargs or {}),
            )
        except Exception as exc:
            logger.error(
                "Runtime-v2 non-stream call failed: provider={} model={} conversation={} error={}",
                provider.code,
                model_code,
                conversation_id,
                str(exc),
                exc_info=True,
            )
            if tenant_id is not None and ai_model:
                try:
                    await _await_if_needed(
                        self.gateway.usage_recorder.log_call_failure(
                            error=exc,
                            start_time=call_start,
                            provider=provider,
                            model=model_code,
                            model_id=ai_model.id,
                            messages=messages,
                            temperature=agent.temperature,
                            max_tokens=agent.max_tokens,
                            top_p=agent.top_p or 1.0,
                            tools=openai_tools,
                            tool_choice=effective_tool_choice,
                            selected_tool_names=[tool.name for tool in (tools or [])],
                            all_tool_names=all_tool_names
                            or [tool.name for tool in (tools or [])],
                            tool_use_policy_family=effective_policy.family,
                            tool_use_policy_mode=effective_policy.mode,
                            allowed_tool_names=effective_policy.allowed_tool_names,
                            breach_retry_result=breach_retry_result,
                            request_type=RequestTypeEnum.CHAT.value,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            user_type=log_user_type,
                            agent_id=getattr(agent, "id", None),
                            conversation_id=conversation_id,
                            billing_context=self.gateway._merge_model_provider_snapshots(
                                billing_context,
                                provider=provider,
                                ai_model=ai_model,
                            ),
                            call_type="main_chat",
                            turn_record=asdict(query_engine.turn_record),
                            protocol_path=getattr(
                                query_engine.turn_record,
                                "protocol_path",
                                None,
                            ),
                            context_sources=runtime_context_sources,
                            routed_model_id=routed_model_id,
                            route_reason=route_reason,
                        )
                    )
                except Exception as log_exc:
                    logger.error(
                        "Runtime-v2 non-stream failure audit log failed: provider={} model={} conversation={} error={}",
                        provider.code,
                        model_code,
                        conversation_id,
                        str(log_exc),
                    )
            raise

        metadata = dict(getattr(response, "metadata", {}) or {})
        metadata.setdefault("runtime_model_info", runtime_context.runtime_info)
        metadata["runtime_turn_record"] = query_engine.turn_record
        response.metadata = metadata

        resolved_usage = resolve_chat_usage(
            messages=messages,
            output_text=response.message.content or "",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_input=estimated_input,
        )
        input_tokens = resolved_usage.input_tokens
        output_tokens = resolved_usage.output_tokens
        total_tokens = resolved_usage.total_tokens
        response.input_tokens = input_tokens
        response.output_tokens = output_tokens
        response.total_tokens = total_tokens
        response.metadata["usage_mode"] = resolved_usage.usage_mode
        latency_ms = int((time.perf_counter() - call_start) * 1000)

        cost = (
            CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
            if ai_model
            else 0.0
        )
        should_meter_usage = runtime_context.should_meter_usage
        should_record_call_log = runtime_context.should_record_call_log

        if should_meter_usage and ai_model and tenant_id is not None:
            await _await_if_needed(
                self.gateway.usage_recorder.record_usage_and_adjust(
                    tenant_id=tenant_id,
                    model_id=ai_model.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    estimated_input=estimated_input,
                    latency_ms=latency_ms,
                    user_id=user_id,
                    metering_context=metering_context,
                )
            )

        api_key.increment_usage()

        if should_record_call_log and ai_model and tenant_id is not None:
            try:
                resolved_log_type = UsageRecorder._resolve_call_user_type(
                    tenant_id,
                    log_user_type,
                )
                await _await_if_needed(
                    self.gateway.usage_recorder.call_log_service.log_call_async(
                        tenant_id=tenant_id,
                        model_id=ai_model.id,
                        provider_id=provider.id,
                        request_type=RequestTypeEnum.CHAT.value,
                        request_data=request_log_data,
                        response_data={
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
                            "model": model_code,
                            "usage_mode": resolved_usage.usage_mode,
                        },
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost=cost,
                        latency_ms=latency_ms,
                        status=CallStatusEnum.SUCCESS.value,
                        user_id=user_id,
                        user_type=resolved_log_type,
                        agent_id=getattr(agent, "id", None),
                        conversation_id=conversation_id,
                        billing_context=self.gateway._merge_model_provider_snapshots(
                            billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        call_type="main_chat",
                        turn_record=asdict(query_engine.turn_record),
                        protocol_path=getattr(
                            query_engine.turn_record, "protocol_path", None
                        ),
                        context_sources=runtime_context_sources,
                        routed_model_id=routed_model_id,
                        route_reason=route_reason,
                    )
                )
            except Exception as log_exc:
                logger.error("Runtime-v2 non-stream call log failed: {}", str(log_exc))

        await _await_if_needed(self.db.commit())
        return response, query_engine

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
        on_complete: Callable[[ExecutionResult], Awaitable[None]] | None = None,
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
        runtime_context: _StreamRuntimeContext | None = None,
        all_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """
        Get streaming ChatChunk via adapter (with rate limiting/quota/metering protection).
        通过 adapter 获取流式 ChatChunk（含限流/配额/计量保护）。

        Uses adapter for real streaming, but executes gateway-level rate limiting,
        quota checking, and usage metering before/after stream, ensuring same
        security guarantees as non-streaming path.
        使用 adapter 实现真实流式推送，但在流前后执行 gateway 级别的限流/配额/计量检查。

        Args:
            agent: Agent / 智能体
            messages: Message list / 消息列表
            tenant_id: Tenant ID (for API Key retrieval) / 企业 ID
            route_result: ModelRouter route result (affects provider/model selection) / ModelRouter 路由结果
            tools: Tool definition list (for Function Calling) / 工具定义列表
            user_id: Caller user id for ai_call_logs / 调用人 ID
            log_user_type: Explicit call_log user_type / 调用日志用户类型

        Yields:
            ChatChunk
        """
        stream_start = time.perf_counter()

        if runtime_context is None:
            runtime_context = await self._prepare_stream_runtime(
                agent=agent,
                messages=messages,
                tenant_id=tenant_id,
                route_result=route_result,
            )

        provider = runtime_context.provider
        api_key = runtime_context.api_key
        ai_model = runtime_context.ai_model
        model_code = runtime_context.model_code
        is_vision = runtime_context.is_vision
        is_audio = runtime_context.is_audio
        is_video = runtime_context.is_video
        estimated_input = runtime_context.estimated_input
        metering_context = runtime_context.metering_context
        should_meter_usage = runtime_context.should_meter_usage
        should_record_call_log = runtime_context.should_record_call_log

        adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
            provider_config=provider.config,
            internal_db=self.db,
            internal_tenant_id=tenant_id,
            model_config=getattr(ai_model, "config", None),
        )
        openai_tools = to_openai_tools(tools) if tools else None
        effective_policy = tool_use_policy or ToolUsePolicy()
        effective_tool_choice = (
            effective_policy.mode
            if openai_tools and effective_policy.mode in {"auto", "required"}
            else None
        )
        runtime_call_overrides = build_model_request_overrides(
            execution_path=execution_path,
            tools=tools,
        )
        request_log_data = {
            "_stream": True,
            "messages": messages_to_dicts(messages),
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "top_p": agent.top_p or 1.0,
            "tools": openai_tools,
            "tool_choice": effective_tool_choice,
            "selected_tool_names": [tool.name for tool in (tools or [])],
            "all_tool_names": all_tool_names or [tool.name for tool in (tools or [])],
            "tool_use_policy": {
                "family": effective_policy.family,
                "mode": effective_policy.mode,
                "allowed_tool_names": effective_policy.allowed_tool_names,
            },
        }
        if breach_retry_result:
            request_log_data["breach_retry_result"] = breach_retry_result
        if effective_policy.reason.startswith(
            ("capability_denial:", "required_retry:")
        ):
            request_log_data["breach_retry_result"] = "contract_retry"
        if (
            openai_tools
            and any(
                isinstance(tool, dict)
                and (tool.get("function", {}) or {}).get("name")
                in {"web_search", "fetch_url"}
                for tool in openai_tools
            )
            and not effective_tool_choice
        ):
            logger.warning(
                "Tool policy not loaded: status=policy_not_loaded runtime={} conversation_id={} agent_id={} tool_names={}",
                get_runtime_identity_tag(),
                conversation_id,
                getattr(agent, "id", None),
                [
                    (tool.get("function", {}) or {}).get("name")
                    for tool in openai_tools
                    if isinstance(tool, dict)
                ],
            )

        supports_streaming = (
            getattr(ai_model, "supports_streaming", True) if ai_model else True
        )
        routed_model_id = (
            int(getattr(route_result, "model_id", 0) or 0)
            if route_result is not None
            and getattr(route_result, "is_overridden", False)
            else None
        )
        route_reason = (
            route_result.reason
            if route_result is not None
            and getattr(route_result, "is_overridden", False)
            else None
        )

        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        usage_mode = "actual"
        streamed_output = ""
        runtime_info = runtime_context.runtime_info
        runtime_selected_skill_names = list(selected_skill_names or [])
        runtime_context_sources = _serialize_context_sources(context_sources)
        query_engine: ConversationQueryEngine | None = None

        def _chunk_has_meaningful_payload(chunk: ChatChunk) -> bool:
            return bool(
                (chunk.delta or "").strip()
                or (chunk.reasoning_delta or "").strip()
                or chunk.tool_calls,
            )

        try:
            query_engine = ConversationQueryEngine(
                adapter=adapter,
                strict_contract=(effective_tool_choice == "required"),
            )
            if not supports_streaming:
                logger.info(
                    "Model {} does not support streaming, using runtime-v2 sync turn",
                    model_code,
                )
                response = await query_engine.run_chat_turn(
                    messages=messages,
                    model=model_code,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    top_p=agent.top_p or 1.0,
                    tools=openai_tools,
                    tool_choice=effective_tool_choice,
                    supports_vision=bool(is_vision),
                    supports_audio=bool(is_audio),
                    supports_video=bool(is_video),
                    selected_skill_names=runtime_selected_skill_names,
                    context_sources=runtime_context_sources,
                    extra_kwargs=dict(runtime_call_overrides),
                )
                total_tokens = response.total_tokens or 0
                input_tokens = response.input_tokens or 0
                output_tokens = response.output_tokens or 0
                streamed_output = response.message.content or ""
                yield ChatChunk(
                    delta=response.message.content or "",
                    role=response.message.role,
                    finish_reason="stop",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    tool_calls=response.tool_calls or response.message.tool_calls,
                    metadata={
                        "runtime_model_info": runtime_info,
                        "runtime_turn_record": query_engine.turn_record,
                    },
                )
            else:
                try:
                    runtime_chunks = await query_engine.run_stream_turn(
                        messages=messages,
                        model=model_code,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        top_p=agent.top_p or 1.0,
                        tools=openai_tools,
                        tool_choice=effective_tool_choice,
                        supports_vision=bool(is_vision),
                        supports_audio=bool(is_audio),
                        supports_video=bool(is_video),
                        selected_skill_names=runtime_selected_skill_names,
                        context_sources=runtime_context_sources,
                        extra_kwargs=dict(runtime_call_overrides),
                    )
                except Exception as runtime_stream_exc:
                    turn_record_metadata = dict(
                        getattr(
                            getattr(query_engine, "turn_record", None),
                            "metadata",
                            {},
                        )
                        or {},
                    )
                    had_meaningful_chunk_before_error = bool(
                        turn_record_metadata.get("stream_failure_has_meaningful_chunk"),
                    )
                    if had_meaningful_chunk_before_error and query_engine is not None:
                        request_log_data["runtime_v2_stream_failure_after_chunk"] = True
                        query_engine.turn_record.metadata[
                            "runtime_v2_stream_failure_after_chunk"
                        ] = True
                    logger.warning(
                        "Runtime-v2 stream failed: runtime={} agent_id={} conversation_id={} had_meaningful_chunk={} error_type={} error={}",
                        get_runtime_identity_tag(),
                        getattr(agent, "id", None),
                        conversation_id,
                        had_meaningful_chunk_before_error,
                        type(runtime_stream_exc).__name__,
                        str(runtime_stream_exc),
                    )
                    raise
                else:
                    for chunk in runtime_chunks:
                        if chunk.total_tokens is not None:
                            total_tokens = chunk.total_tokens
                        if chunk.input_tokens is not None:
                            input_tokens = chunk.input_tokens
                        if chunk.output_tokens is not None:
                            output_tokens = chunk.output_tokens
                        if chunk.delta:
                            streamed_output += chunk.delta
                        chunk.metadata = dict(chunk.metadata or {})
                        if chunk.metadata.get("usage_mode"):
                            usage_mode = str(chunk.metadata["usage_mode"])
                        chunk.metadata.setdefault("runtime_model_info", runtime_info)
                        chunk.metadata.setdefault(
                            "runtime_turn_record",
                            query_engine.turn_record,
                        )
                        yield chunk
        except Exception as exc:
            logger.error(
                "Engine stream upstream failed: provider={} model={} conversation={} error={}",
                provider.code,
                model_code,
                conversation_id,
                str(exc),
                exc_info=True,
            )
            if should_record_call_log and ai_model:
                try:
                    await _await_if_needed(
                        self.gateway.usage_recorder.log_call_failure(
                            error=exc,
                            start_time=stream_start,
                            provider=provider,
                            model=model_code,
                            model_id=ai_model.id,
                            messages=messages,
                            temperature=agent.temperature,
                            max_tokens=agent.max_tokens,
                            top_p=agent.top_p or 1.0,
                            tools=openai_tools,
                            tool_choice=effective_tool_choice,
                            selected_tool_names=[
                                ((tool.get("function", {}) or {}).get("name"))
                                for tool in (openai_tools or [])
                                if isinstance(tool, dict)
                            ],
                            all_tool_names=all_tool_names
                            or [tool.name for tool in (tools or [])],
                            tool_use_policy_family=effective_policy.family,
                            tool_use_policy_mode=effective_policy.mode,
                            allowed_tool_names=effective_policy.allowed_tool_names,
                            breach_retry_result=request_log_data.get(
                                "breach_retry_result"
                            ),
                            request_type=RequestTypeEnum.CHAT.value,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            user_type=log_user_type,
                            agent_id=getattr(agent, "id", None),
                            conversation_id=conversation_id,
                            billing_context=self.gateway._merge_model_provider_snapshots(
                                billing_context,
                                provider=provider,
                                ai_model=ai_model,
                            ),
                            call_type="main_chat",
                            turn_record=(
                                vars(query_engine.turn_record)
                                if query_engine is not None
                                else None
                            ),
                            protocol_path=(
                                getattr(query_engine.turn_record, "protocol_path", None)
                                if query_engine is not None
                                else None
                            ),
                            context_sources=(
                                runtime_context_sources
                                if query_engine is not None
                                else None
                            ),
                            routed_model_id=routed_model_id,
                            route_reason=route_reason,
                        )
                    )
                except Exception as log_exc:
                    logger.error(
                        "Engine stream failure audit log failed: provider={} model={} conversation={} error={}",
                        provider.code,
                        model_code,
                        conversation_id,
                        str(log_exc),
                    )
            raise

        # 流结束后：与 gateway.chat 一致 — 先租户计量再 Key；日志 best-effort
        # 整个尾部用 try/except 保护，避免计量/flush 异常阻塞生成器导致前端永远收不到 done
        latency_ms = int((time.perf_counter() - stream_start) * 1000)
        try:
            resolved_log_type = UsageRecorder._resolve_call_user_type(
                tenant_id, log_user_type
            )
            resolved_usage = resolve_chat_usage(
                messages=messages,
                output_text=streamed_output,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_input=estimated_input,
            )
            input_tokens = resolved_usage.input_tokens
            output_tokens = resolved_usage.output_tokens
            total_tokens = resolved_usage.total_tokens
            usage_mode = resolved_usage.usage_mode

            cost = (
                CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
                if ai_model
                else 0.0
            )

            if should_meter_usage and ai_model and estimated_input > 0:
                assert tenant_id is not None
                await _await_if_needed(
                    self.gateway.usage_recorder.record_usage_and_adjust(
                        tenant_id=tenant_id,
                        model_id=ai_model.id,
                        request_type=RequestTypeEnum.CHAT.value,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost=cost,
                        estimated_input=estimated_input,
                        latency_ms=latency_ms,
                        user_id=user_id,
                        metering_context=metering_context,
                    )
                )

            api_key.increment_usage()
            await _await_if_needed(self.db.flush())

            if should_record_call_log and ai_model:
                try:
                    assert tenant_id is not None
                    await _await_if_needed(
                        self.gateway.usage_recorder.call_log_service.log_call_async(
                            tenant_id=tenant_id,
                            model_id=ai_model.id,
                            provider_id=provider.id,
                            request_type=RequestTypeEnum.CHAT.value,
                            request_data={
                                **request_log_data,
                            },
                            response_data={
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "total_tokens": total_tokens,
                                "model": model_code,
                                "usage_mode": usage_mode,
                            },
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            cost=cost,
                            latency_ms=latency_ms,
                            status=CallStatusEnum.SUCCESS.value,
                            user_id=user_id,
                            user_type=resolved_log_type,
                            agent_id=getattr(agent, "id", None),
                            conversation_id=conversation_id,
                            billing_context=self.gateway._merge_model_provider_snapshots(
                                billing_context,
                                provider=provider,
                                ai_model=ai_model,
                            ),
                            call_type="main_chat",
                            turn_record=(
                                vars(query_engine.turn_record)
                                if query_engine is not None
                                else None
                            ),
                            protocol_path=(
                                getattr(query_engine.turn_record, "protocol_path", None)
                                if query_engine is not None
                                else None
                            ),
                            context_sources=(
                                runtime_context_sources
                                if query_engine is not None
                                else None
                            ),
                            routed_model_id=routed_model_id,
                            route_reason=route_reason,
                        )
                    )
                except Exception as log_exc:
                    logger.error("Engine stream call log failed: {}", str(log_exc))
        except Exception as tail_exc:
            logger.error(
                "Stream tail metering/flush failed (stream still completes): model={} error={}",
                model_code,
                str(tail_exc),
            )

    async def _prepare_stream_runtime(
        self,
        *,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int | None,
        route_result: Any | None = None,
        skip_metering_preflight: bool = False,
    ) -> _StreamRuntimeContext:
        """Prepare first-round stream runtime and perform quota/rate preflight.

        为首轮流式请求准备运行时上下文，并在返回 StreamingResponse 之前完成限速/配额预检。
        """
        if route_result is not None and getattr(route_result, "is_overridden", False):
            provider_code: str = route_result.provider_code or ""
            model_code: str = route_result.model_code or ""
            routed_mid = int(getattr(route_result, "model_id", 0) or 0)
            route_model_obj = None
            if routed_mid:
                from app.repositories.ai.model_repository import AIModelRepository

                route_model_obj = await AIModelRepository(
                    self.db
                ).get_active_with_provider(
                    routed_mid,
                )
            if route_model_obj is not None:
                ai_model = route_model_obj
                is_vision = bool(route_model_obj.supports_vision)
                is_audio = bool(getattr(route_model_obj, "supports_audio", False))
                is_video = bool(getattr(route_model_obj, "supports_video", False))
            else:
                ai_model = agent.model
                reason_str: str = route_result.reason or ""
                is_vision = "vision" in reason_str
                is_audio = "audio" in reason_str
                is_video = "video" in reason_str
        else:
            mobj = agent.model
            ai_model = mobj
            provider_code = mobj.provider.code if mobj and mobj.provider else ""
            model_code = mobj.code if mobj else ""
            is_vision = mobj.supports_vision if mobj else False
            is_audio = getattr(mobj, "supports_audio", False) if mobj else False
            is_video = getattr(mobj, "supports_video", False) if mobj else False

        for msg in messages:
            if msg.attachments:
                kept = [
                    a
                    for a in msg.attachments
                    if not (
                        (a.get("type") == "image" and not is_vision)
                        or (a.get("type") == "audio" and not is_audio)
                        or (a.get("type") == "video" and not is_video)
                    )
                ]
                msg.attachments = kept if kept else None

        provider, api_key = await _await_if_needed(
            self.gateway.get_provider_and_key(
                provider_code,
                tenant_id,
            )
        )

        estimated_input = 0
        metering_context = None
        should_meter_usage = tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
        should_record_call_log = tenant_id is not None
        if should_record_call_log and ai_model:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
        if should_meter_usage and ai_model and not skip_metering_preflight:
            metering_context = await _await_if_needed(
                self.gateway.usage_recorder.check_rate_and_quota(
                    tenant_id,
                    ai_model.id,
                    ai_model,
                    estimated_input,
                )
            )

        return _StreamRuntimeContext(
            provider=provider,
            api_key=api_key,
            ai_model=ai_model,
            model_code=model_code,
            is_vision=is_vision,
            is_audio=is_audio,
            is_video=is_video,
            estimated_input=estimated_input,
            metering_context=metering_context,
            should_meter_usage=should_meter_usage,
            should_record_call_log=should_record_call_log,
            runtime_info={
                "provider_id": provider.id,
                "provider_name": (
                    getattr(provider, "name", None)
                    or getattr(provider, "code", None)
                    or f"Provider #{provider.id}"
                ),
                "model_id": ai_model.id if ai_model else None,
                "model_name": (
                    (getattr(ai_model, "name", None) or model_code)
                    if ai_model
                    else None
                ),
                "model_code": model_code,
            },
        )


__all__ = ["ConversationEngine"]
