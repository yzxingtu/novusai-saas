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
from contextlib import suppress
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.ai.page_locale import resolve_page_locale
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage, ChatResponse
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
from .turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
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


class StreamIOAdapter:
    """Transport adapter for streaming TurnExecutor execution."""

    def __init__(self, handler: StreamExecutionHandler) -> None:
        self.handler = handler

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
        raw_turn_record = metadata.get("runtime_turn_record")
        if isinstance(raw_turn_record, dict):
            self.handler._runtime_turn_record = dict(raw_turn_record)
        elif raw_turn_record is not None and hasattr(raw_turn_record, "__dict__"):
            self.handler._runtime_turn_record = dict(
                getattr(raw_turn_record, "__dict__", {}) or {}
            )

    def _ensure_engine_tool_helpers(self) -> None:
        from .conversation import ConversationEngine

        helper_methods = {
            "_analyze_post_tool_contract_breach": BaseEngine._analyze_post_tool_contract_breach,
            "_apply_fetch_url_only_gate": BaseEngine._apply_fetch_url_only_gate,
            "_allowed_tool_names_for_family": BaseEngine._allowed_tool_names_for_family,
            "_build_contract_recovery_system_message": BaseEngine._build_contract_recovery_system_message,
            "_build_ordered_capability_hint": BaseEngine._build_ordered_capability_hint,
            "_build_page_no_progress_recovery": BaseEngine._build_page_no_progress_recovery,
            "_budget_exit_response": BaseEngine._budget_exit_response,
            "_can_finalize_partial_with_llm": ConversationEngine._can_finalize_partial_with_llm,
            "_first_incomplete_requested_family": BaseEngine._first_incomplete_requested_family,
            "_mark_multi_family_progress": BaseEngine._mark_multi_family_progress,
            "_messages_have_blocking_pending_interaction": BaseEngine._messages_have_blocking_pending_interaction,
            "_needs_fetch_url_before_summary": BaseEngine._needs_fetch_url_before_summary,
            "_ordered_requested_families_from_intents": BaseEngine._ordered_requested_families_from_intents,
            "_restrict_tools_to_names": BaseEngine._restrict_tools_to_names,
            "_tool_call_name": BaseEngine._tool_call_name,
            "_tool_call_operation_name": BaseEngine._tool_call_operation_name,
            "_truncate_tool_calls_after_navigation": BaseEngine._truncate_tool_calls_after_navigation,
        }
        for method_name, fallback in helper_methods.items():
            if not callable(getattr(self.handler.engine, method_name, None)):
                setattr(self.handler.engine, method_name, fallback)

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

        if kwargs.get("breach_retry_result"):
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
        breach_retry_result = str(kwargs.get("breach_retry_result") or "").strip()
        if (
            breach_retry_result == "intent_retry"
            and tool_use_policy.mode == "required"
            and (self.handler.prep.all_tools or tools)
        ):
            diag_tools = list(self.handler.prep.all_tools or tools or [])
            continuation_context = getattr(
                self.handler.prep,
                "continuation_context",
                None,
            )
            breach_type = tool_use_policy.reason or "contract_breach"
            self.log_tool_contract_diagnostics(
                agent=self.handler.agent,
                messages=messages,
                response=response,
                tools=diag_tools,
                policy=tool_use_policy,
                conversation_id=self.handler.request.conversation_id,
                breach_type=breach_type,
                retry_result="retrying",
                continuation=continuation_context,
            )
            if not finalized_tool_calls and aggregated_output.strip():
                self.log_tool_contract_diagnostics(
                    agent=self.handler.agent,
                    messages=messages,
                    response=response,
                    tools=diag_tools,
                    policy=tool_use_policy,
                    conversation_id=self.handler.request.conversation_id,
                    breach_type=breach_type,
                    retry_result="failed",
                    continuation=continuation_context,
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
        from app.ai.tools.types import ToolResult
        from .tool_processor import ToolCallProcessor

        self._ensure_engine_tool_helpers()
        request_proxy = self._request_with_defaults()
        current_policy = (
            kwargs.get("tool_use_policy")
            or request_proxy.tool_use_policy
            or ToolUsePolicy()
        )
        processor = ToolCallProcessor(
            sandbox=self.handler.engine.sandbox,
            tools=tools,
            all_tools=self.handler.prep.all_tools,
            consent_modes=self.handler.prep.tool_consent_modes,
            approved_pending_consent_tools=ToolCallProcessor.approved_pending_consent_tool_names(
                self.handler.request.interaction_updates,
            ),
            interaction_mode=request_proxy.interaction_mode,
        )
        tool_calls = list(response.tool_calls or response.message.tool_calls or [])
        tool_calls, _truncated_after_navigation = (
            self.handler.engine._truncate_tool_calls_after_navigation(tool_calls)
        )
        starting_total_tokens = int(kwargs.get("starting_total_tokens") or 0)
        starting_completion_tokens = int(
            kwargs.get("starting_completion_tokens") or 0
        )
        reasoning_content = str(
            response.message.reasoning_content or response.message.content or ""
        ).strip() or None
        messages.append(
            processor.build_assistant_tool_call_message(
                content=response.message.content or "",
                tool_calls=tool_calls,
                reasoning_content=reasoning_content,
            )
        )

        round_tool_results: list[ToolResult] = []
        follow_up_messages: list[ChatMessage] = []
        round_has_confirmation = False
        page_op_failures = 0
        page_op_aborted = False
        page_op_abort_threshold = 3

        for tc in tool_calls:
            tc_id = tc.get("id", "")
            func = tc.get("function", {}) if isinstance(tc, dict) else {}
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
                round_tool_results.append(err_result)
                await self.handler._emit_runtime_event(
                    processor.build_tool_call_event(
                        err_result,
                        0,
                        processor.get_skill_info(func_name),
                        name_override=func_name or err_result.name,
                    )
                )
                messages.append(processor.build_tool_message(err_result, tc_id))
                is_page_op = func_name == "invoke_page_operation" or (
                    func_name.startswith("pageop_") if func_name else False
                )
                if is_page_op:
                    page_op_failures += 1
                    if page_op_failures >= page_op_abort_threshold:
                        page_op_aborted = True
                        self.handler._output = (
                            str(response.message.content or "").strip() + "\n\n"
                            if str(response.message.content or "").strip()
                            else ""
                        ) + _("page_operation.error.multiple_failures_parse")
                        break
                continue

            skill_info = processor.get_skill_info(func_name)
            processor.annotate_tool_call(tc, skill_info=skill_info)
            consent = processor.check_consent(func_name, arguments)
            if consent == "reject":
                messages.append(processor.build_consent_reject_message(tc_id))
                await self.handler._emit_runtime_event(
                    processor.build_consent_reject_event(
                        func_name,
                        skill_info,
                    )
                )
                continue
            if consent == "ask":
                processor.annotate_tool_call(
                    tc,
                    pending_consent=processor.build_pending_consent_payload(
                        func_name,
                        arguments,
                        skill_info,
                    ),
                )
                messages.append(
                    processor.build_consent_ask_message(
                        tc_id,
                        func_name,
                        arguments,
                    )
                )
                await self.handler._emit_runtime_event(
                    processor.build_consent_ask_event(
                        func_name,
                        arguments,
                        skill_info,
                    )
                )
                round_has_confirmation = True
                continue

            await self.handler._emit_runtime_event(
                processor.build_tool_start_event(
                    func_name,
                    arguments,
                    skill_info,
                    tool_call_id=tc_id,
                )
            )
            started = time.perf_counter()
            result, tc_duration = await processor.execute_tool(
                tc_id,
                func_name,
                arguments,
                conversation_id=self.handler.request.conversation_id or 0,
            )
            if tc_duration <= 0:
                tc_duration = int((time.perf_counter() - started) * 1000)
            processor.annotate_tool_call(
                tc,
                duration_ms=tc_duration,
                result=result,
                skill_info=skill_info,
            )
            round_tool_results.append(result)
            await self.handler._emit_runtime_event(
                processor.build_tool_call_event(
                    result,
                    tc_duration,
                    skill_info,
                    name_override=func_name,
                )
            )
            messages.append(processor.build_tool_message(result, tc_id))
            follow_up_message = processor.build_attachment_relay_message(result)
            if follow_up_message:
                follow_up_messages.append(follow_up_message)
            confirmation_payload = processor.check_confirmation_output(result)
            if confirmation_payload:
                processor.annotate_tool_call(
                    tc,
                    pending_confirmation=processor.build_pending_confirmation_payload(
                        confirmation_payload,
                    ),
                )
                round_has_confirmation = True
                await self.handler._emit_runtime_event(
                    processor.build_confirmation_event(confirmation_payload)
                )

            is_page_op = func_name == "invoke_page_operation" or (
                func_name.startswith("pageop_") if func_name else False
            )
            if is_page_op:
                if result.success:
                    page_op_failures = 0
                else:
                    page_op_failures += 1
                    if page_op_failures >= page_op_abort_threshold:
                        page_op_aborted = True
                        self.handler._output = (
                            str(response.message.content or "").strip() + "\n\n"
                            if str(response.message.content or "").strip()
                            else ""
                        ) + _("page_operation.error.multiple_failures_sequence")
                        break

            tool_result_budget_reason = self.handler._state.budget_exit_reason()
            if tool_result_budget_reason:
                self.handler._register_budget_exit(tool_result_budget_reason)
                break

        if follow_up_messages and not round_has_confirmation and not page_op_aborted:
            messages.extend(follow_up_messages)

        if page_op_aborted:
            text_response = self.handler._build_text_round_response(
                content=self.handler._output,
                reasoning_content=reasoning_content or "",
                total_tokens=starting_total_tokens,
            )
            return ToolBatchResult(
                response=text_response,
                tool_results=round_tool_results,
                total_tokens=starting_total_tokens,
                completion_tokens_used=starting_completion_tokens,
            )

        if round_has_confirmation:
            consent_response = ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=response.message.content or "",
                    tool_calls=tool_calls,
                    reasoning_content=reasoning_content,
                ),
                total_tokens=starting_total_tokens,
                output_tokens=starting_completion_tokens,
                tool_calls=tool_calls,
                metadata={"skip_final_assistant": True},
            )
            return ToolBatchResult(
                response=consent_response,
                tool_results=round_tool_results,
                total_tokens=starting_total_tokens,
                completion_tokens_used=starting_completion_tokens,
            )

        if self.handler._state.provider_failure_kind == "budget_exit":
            budget_output = str(self.handler._output or "").strip()
            if not budget_output:
                budget_output = self.handler._build_budget_exit_fallback_output(
                    tool_results=round_tool_results,
                )
                self.handler._output = budget_output
            budget_response = self.handler._build_text_round_response(
                content=budget_output,
                reasoning_content=reasoning_content or "",
                total_tokens=starting_total_tokens,
            )
            return ToolBatchResult(
                response=budget_response,
                tool_results=round_tool_results,
                total_tokens=starting_total_tokens,
                completion_tokens_used=starting_completion_tokens,
            )

        follow_up_tools = self.handler.engine._apply_fetch_url_only_gate(
            messages,
            list(tools),
            self.handler.prep.all_tools or list(tools),
        )
        follow_up_policy = current_policy
        if [tool.name for tool in follow_up_tools] != list(
            current_policy.allowed_tool_names or []
        ):
            follow_up_policy = ToolUsePolicy(
                family=current_policy.family,
                mode=current_policy.mode,
                allowed_tool_names=[tool.name for tool in follow_up_tools],
                retry_on_contract_breach=current_policy.retry_on_contract_breach,
                reason=(
                    f"{current_policy.reason}|round_tool_subset"
                    if current_policy.reason
                    else "round_tool_subset"
                ),
            )

        follow_up_round = await self.call_llm(
            messages=messages,
            tools=follow_up_tools or None,
            tool_use_policy=follow_up_policy,
        )
        normalized_response = follow_up_round.response
        total_tokens = starting_total_tokens + int(follow_up_round.total_tokens or 0)
        completion_tokens_used = starting_completion_tokens + int(
            follow_up_round.completion_tokens_used or 0
        )
        self._sync_runtime_metadata(
            getattr(normalized_response, "metadata", None)
            if normalized_response is not None
            else None
        )
        continuation_context = getattr(self.handler.prep, "continuation_context", None)
        all_tools = list(self.handler.prep.all_tools or tools or [])
        analyze_breach_fn = getattr(
            self.handler.engine,
            "_analyze_post_tool_contract_breach",
            None,
        )
        breach_type: str | None = None
        retry_policy: ToolUsePolicy | None = None
        if normalized_response is not None and callable(analyze_breach_fn):
            breach_type, retry_policy, _diagnostics = analyze_breach_fn(
                messages=messages,
                response=normalized_response,
                current_policy=follow_up_policy,
                tools=all_tools,
                input_variables=getattr(request_proxy, "input_variables", None),
            )
            del _diagnostics
        if retry_policy is None and follow_up_policy.retry_on_contract_breach:
            should_retry, retry_policy, _breach_response_text = (
                self.should_retry_tool_contract_breach(
                    response=normalized_response,
                    current_policy=follow_up_policy,
                    tools=all_tools,
                    input_variables=getattr(request_proxy, "input_variables", None),
                )
            )
            if not should_retry:
                should_retry, retry_policy, _breach_response_text = (
                    self.should_retry_web_research_contract_breach(
                        messages=messages,
                        response=normalized_response,
                        current_policy=follow_up_policy,
                        tools=all_tools,
                        input_variables=getattr(
                            request_proxy,
                            "input_variables",
                            None,
                        ),
                        continuation=continuation_context,
                    )
                )
            if should_retry and retry_policy is not None and not breach_type:
                breach_type = retry_policy.reason or "contract_breach"
            del _breach_response_text
        if retry_policy is not None:
            retry_breach_type = breach_type or retry_policy.reason or "contract_breach"
            self.log_tool_contract_diagnostics(
                agent=self.handler.agent,
                messages=messages,
                response=normalized_response,
                tools=all_tools,
                policy=retry_policy,
                conversation_id=self.handler.request.conversation_id,
                breach_type=retry_breach_type,
                retry_result="retrying",
                continuation=continuation_context,
            )
            retry_tools = self.restrict_tools_to_names(
                all_tools,
                retry_policy.allowed_tool_names,
            )
            effective_retry_policy = ToolUsePolicy(
                family=retry_policy.family,
                mode=retry_policy.mode,
                allowed_tool_names=list(retry_policy.allowed_tool_names or []),
                retry_on_contract_breach=False,
                reason=retry_policy.reason,
            )
            retry_round = await self.call_llm(
                messages=messages,
                tools=retry_tools or None,
                tool_use_policy=effective_retry_policy,
                breach_retry_result="retry_follow_up",
            )
            normalized_response = retry_round.response
            total_tokens += int(retry_round.total_tokens or 0)
            completion_tokens_used += int(retry_round.completion_tokens_used or 0)
            self._sync_runtime_metadata(
                getattr(normalized_response, "metadata", None)
                if normalized_response is not None
                else None
            )
            if getattr(normalized_response, "tool_calls", None) and retry_tools:
                retry_batch = await self.handle_tool_calls(
                    response=normalized_response,
                    tools=retry_tools,
                    messages=messages,
                    tool_use_policy=effective_retry_policy,
                    starting_total_tokens=total_tokens,
                    starting_completion_tokens=completion_tokens_used,
                )
                return ToolBatchResult(
                    response=retry_batch.response,
                    tool_results=round_tool_results + list(retry_batch.tool_results),
                    total_tokens=retry_batch.total_tokens,
                    completion_tokens_used=retry_batch.completion_tokens_used,
                )
            if normalized_response is not None and not getattr(
                normalized_response,
                "tool_calls",
                None,
            ):
                retry_failed = True
                if callable(analyze_breach_fn):
                    next_breach_type, _next_retry_policy, _next_diagnostics = (
                        analyze_breach_fn(
                            messages=messages,
                            response=normalized_response,
                            current_policy=effective_retry_policy,
                            tools=all_tools,
                            input_variables=getattr(
                                request_proxy,
                                "input_variables",
                                None,
                            ),
                        )
                    )
                    retry_failed = bool(next_breach_type or _next_retry_policy)
                    del _next_retry_policy, _next_diagnostics
                    if next_breach_type:
                        retry_breach_type = next_breach_type
                if retry_failed:
                    self.log_tool_contract_diagnostics(
                        agent=self.handler.agent,
                        messages=messages,
                        response=normalized_response,
                        tools=all_tools,
                        policy=effective_retry_policy,
                        conversation_id=self.handler.request.conversation_id,
                        breach_type=retry_breach_type,
                        retry_result="failed",
                        continuation=continuation_context,
                    )
        self.handler._total_tokens = int(total_tokens or 0)
        self.handler._completion_tokens_used = int(completion_tokens_used or 0)
        return ToolBatchResult(
            response=normalized_response,
            tool_results=round_tool_results,
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
        from .conversation import ConversationEngine

        self._ensure_engine_tool_helpers()
        output, final_total_tokens, final_completion_tokens = (
            await ConversationEngine._finalize_partial_output(
                self.handler.engine,
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
        if stream_local_output:
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
        retry_fn = getattr(
            self.handler.engine,
            "_should_retry_tool_contract_breach",
            None,
        )
        if callable(retry_fn):
            return retry_fn(
                response=response,
                current_policy=current_policy,
                tools=tools,
                input_variables=input_variables,
            )
        return False, None, ""

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
        retry_fn = getattr(
            self.handler.engine,
            "_should_retry_web_research_contract_breach",
            None,
        )
        if callable(retry_fn):
            return retry_fn(
                messages=messages,
                response=response,
                current_policy=current_policy,
                tools=tools,
                input_variables=input_variables,
                continuation=continuation,
            )
        return False, None, ""

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]:
        if callable(getattr(self.handler.engine, "_restrict_tools_to_names", None)):
            return self.handler.engine._restrict_tools_to_names(
                tools,
                allowed_tool_names,
            )
        return list(tools)

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
        log_fn = getattr(self.handler.engine, "_log_tool_contract_diagnostics", None)
        if callable(log_fn):
            log_fn(
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

        total_tokens = 0
        all_tool_results: list[ToolResult] = []
        output = ""
        turn_execution = None
        executor_task: asyncio.Task[Any] | None = None
        self._output = ""  # Used for partial persist on interrupt  # 补充说明 / note
        self._reasoning_output = ""  # For chain-of-thought models, used in partial persist  # 补充说明 / note
        self._total_tokens = 0
        self._completion_tokens_used = 0
        self._runtime_model_info: dict[str, Any] | None = None
        self._runtime_turn_record: dict[str, Any] | None = None
        self._on_complete_called = False
        self._visible_stream_content = ""
        self._clear_before_next_message = False
        self._next_runtime_context = getattr(self.prep, "stream_runtime", None)

        try:
            self._interrupted_stage = "stream_generating"
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
                    last_page_key=str(
                        current_page_context.get("page_key") or ""
                    ).strip()
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

            # Push tool optimization event / 推送工具优化事件
            if _optimize_event is not None:
                yield SSEChunkEncoder.encode(
                    {"event": "optimizing_tools", **_optimize_event}
                    if isinstance(_optimize_event, dict)
                    else _optimize_event
                )

            executor_task = asyncio.create_task(self._run_with_turn_executor())
            while True:
                if executor_task.done() and self._event_queue.empty():
                    break
                try:
                    queued_event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=0.05,
                    )
                except asyncio.TimeoutError:
                    continue
                yield queued_event

            turn_execution = await executor_task
            output = turn_execution.output
            total_tokens = turn_execution.total_tokens
            all_tool_results = list(turn_execution.tool_results)
            self._completion_tokens_used = turn_execution.completion_tokens_used
            response = turn_execution.response
            response_metadata = (
                dict(getattr(response, "metadata", {}) or {})
                if response is not None
                else {}
            )
            runtime_model_info = response_metadata.get("runtime_model_info")
            if isinstance(runtime_model_info, dict):
                self._runtime_model_info = dict(runtime_model_info)
            raw_turn_record = response_metadata.get("runtime_turn_record")
            if isinstance(raw_turn_record, dict):
                self._runtime_turn_record = dict(raw_turn_record)
            elif raw_turn_record is not None and hasattr(raw_turn_record, "__dict__"):
                self._runtime_turn_record = dict(
                    getattr(raw_turn_record, "__dict__", {}) or {}
                )

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
            paused_for_consent = bool(turn_execution.paused_for_consent)
            partial = bool(turn_execution.partial)
            partial_reply_stream_chunks: list[str] = []
            completion_reason = turn_execution.completion_reason or "completed"
            skip_final_assistant = bool(response_metadata.get("skip_final_assistant"))
            if partial:
                visible_assistant_output = self._last_visible_assistant_content(
                    messages
                )
                streamed_output = str(self._visible_stream_content or "").strip()
                stream_local_output = str(self._output or "").strip()
                if visible_assistant_output:
                    output = visible_assistant_output
                elif stream_local_output:
                    output = stream_local_output
                elif str(output or "").strip():
                    output = str(output).strip()
                elif self._state.provider_failure_kind == "budget_exit":
                    output = self._build_budget_exit_fallback_output(
                        tool_results=all_tool_results,
                    )
                else:
                    output = RecoveryManager.build_partial_output(
                        self._state.intent_plan,
                        reason=completion_reason or "return_partial",
                        provider_failure_kind=self._state.provider_failure_kind,
                    )
                self._output = output
                if output and not visible_assistant_output:
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
                    if output != streamed_output:
                        partial_reply_stream_chunks = self._chunk_text_for_streaming(
                            output
                        )
            elif paused_for_consent:
                output = (
                    self._last_visible_assistant_content(messages)
                    or str(self._output or "").strip()
                )
                self._output = output
            elif output and not skip_final_assistant:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=output,
                        reasoning_content=(
                            str(
                                getattr(
                                    getattr(response, "message", None),
                                    "reasoning_content",
                                    None,
                                )
                                or self._reasoning_output
                                or ""
                            ).strip()
                            or None
                        ),
                        metadata=(
                            {"action_buttons": action_buttons}
                            if action_buttons
                            else None
                        ),
                    )
                )

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
            if executor_task is not None and not executor_task.done():
                executor_task.cancel()
                with suppress(BaseException):
                    await executor_task
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

        def _has_successful_tool_results() -> bool:
            return any(result.success for result in all_tool_results)

        def _finalization_only_policy() -> ToolUsePolicy:
            return ToolUsePolicy(
                family="none",
                mode="none",
                allowed_tool_names=[],
                retry_on_contract_breach=False,
                reason="partial_exit_final_response",
            )

        forced_tool_names: list[str] | None = None
        ordered_requested_families: list[str] = []
        if not self._state.intent_plan:
            inferred_intents = IntentPlanner.plan_turn(
                messages=list(
                    getattr(self.request, "messages", None) or messages or []
                ),
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
            if not actionable_inferred_intents and fallback_family != "none":
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
            pre_model_reason = BudgetGuard.pre_model_reason(
                self._state.budget,
                allow_finalization_grace=_has_successful_tool_results(),
            )
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
            self._output = ""
            self._reasoning_output = ""

            force_finalization_only = bool(
                self._state.budget is not None
                and self._state.budget.finalization_grace_applied
                and _has_successful_tool_results()
            )

            if force_finalization_only:
                round_tools = []
                round_tool_policy = _finalization_only_policy()
            else:
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
                if round_tools:
                    round_tool_policy = ToolUsePolicy(
                        family=round_tool_policy.family,
                        mode=round_tool_policy.mode,
                        allowed_tool_names=[tool.name for tool in round_tools],
                        retry_on_contract_breach=round_tool_policy.retry_on_contract_breach,
                        reason=(
                            f"{round_tool_policy.reason}|round_tool_subset"
                            if round_tool_policy.reason
                            else "round_tool_subset"
                        ),
                    )
                else:
                    round_tool_policy = _finalization_only_policy()

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
                    yield SSEChunkEncoder.encode(
                        {
                            "event": "message",
                            "delta": chunk.delta,
                        }
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
            self._completion_tokens_used += int(
                round_output_tokens or round_total_tokens
            )
            completion_reason = BudgetGuard.completion_reason(
                self._state.budget,
                completion_tokens=self._completion_tokens_used,
                total_tokens=self._total_tokens,
            )
            tc_list = self._finalize_stream_tool_calls(round_tool_calls)
            tc_list, truncated_after_navigation = (
                self.engine._truncate_tool_calls_after_navigation(tc_list)
            )
            if force_finalization_only and tc_list:
                logger.warning(
                    "Finalization-only stream round returned unexpected tool calls; suppressing execution: conversation_id={} tool_names={}",
                    self.request.conversation_id,
                    [
                        str(
                            (tool_call.get("function") or {}).get("name")
                            or tool_call.get("name")
                            or ""
                        )
                        for tool_call in tc_list
                        if isinstance(tool_call, dict)
                    ],
                )
                tc_list = []
            if completion_reason:
                self._state.register_completion_tokens(self._completion_tokens_used)
                self._register_budget_exit(completion_reason)
                self._output = round_output
                self._reasoning_output = round_reasoning_output
                break
            if truncated_after_navigation:
                logger.info(
                    "Truncated streamed assistant tool call batch after navigation op to avoid stale page follow-up calls: {}",
                    [
                        str(
                            (tc.get("function") or {}).get("name")
                            or tc.get("name")
                            or ""
                        )
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
                    (
                        analyzed_breach_type,
                        analyzed_retry_policy,
                        _analyzed_diagnostics,
                    ) = self.engine._analyze_post_tool_contract_breach(
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
                    del analyzed_breach_type, _analyzed_diagnostics
                    retry_reason = (
                        analyzed_retry_policy.reason
                        if analyzed_retry_policy is not None
                        else (
                            "web_research_summary_without_fetch"
                            if (
                                decision.retry_family == "web_research"
                                and self.engine._needs_fetch_url_before_summary(
                                    messages
                                )
                            )
                            else decision.reason
                        )
                    )
                    retry_policy = ToolUsePolicy(
                        family=decision.retry_family
                        or getattr(
                            self.prep, "tool_use_policy", ToolUsePolicy()
                        ).family,
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
                    # 告知前端丢弃本轮已流出的 message 内容 / Tell frontend to discard the current round message content
                    if round_output:
                        yield SSEChunkEncoder.encode({"event": "clear_content"})
                        self._output = ""
                    next_runtime_context = None
                    continue
                if (
                    round_tool_policy.mode == "required"
                    and self._state.recovery_history
                ):
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

                self._output = round_output
                self._reasoning_output = round_reasoning_output
                break

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
            graceful_finalization_pending = False

            sandbox = getattr(self.engine, "sandbox", None)
            if sandbox is not None and hasattr(sandbox, "set_runtime_model_info"):
                sandbox.set_runtime_model_info(self._runtime_model_info)

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
                _consent = processor.check_consent(func_name, arguments)

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
                    if (
                        tool_result_budget_reason == "elapsed_budget_exceeded"
                        and _has_successful_tool_results()
                        and BudgetGuard.pre_model_reason(
                            self._state.budget,
                            allow_finalization_grace=True,
                        )
                        is None
                    ):
                        graceful_finalization_pending = True
                        break
                    self._register_budget_exit(tool_result_budget_reason)
                self._update_turn_progress(
                    last_tool_name=func_name or None,
                    last_page_op=operation_name or None,
                    tool_loop_progress={
                        "round": _round + 1,
                        "last_tool_success": bool(result.success),
                    },
                )

                if (
                    _page_op_aborted
                    or self._state.provider_failure_kind == "budget_exit"
                ):
                    break

            if (
                follow_up_messages
                and not round_has_confirmation
                and not _page_op_aborted
            ):
                messages.extend(follow_up_messages)

            if graceful_finalization_pending:
                continue

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
                    },
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
