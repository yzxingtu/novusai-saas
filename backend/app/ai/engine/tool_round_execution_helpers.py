"""
Helpers for BaseEngine._handle_tool_calls() round execution and result accounting.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .budget_guard import BudgetGuard
from .tool_processor import SingleToolResult, ToolCallProcessor
from .types import ExecutionBudget


@dataclass
class ToolRoundExecutionState:
    messages: list[ChatMessage]
    all_tool_results: list[ToolResult]
    round_tool_results: list[ToolResult]
    follow_up_messages: list[ChatMessage]
    total_tokens: int
    completion_tokens_used: int
    tracked_tool_result_bytes: int


@dataclass
class ToolRoundExecutionOutcome:
    tracked_tool_result_bytes: int
    early_return: tuple[ChatResponse | None, list[ToolResult], int, int] | None = None


def _trim_last_assistant_tool_calls(
    messages: list[ChatMessage],
    kept_tool_calls: list[dict[str, Any]],
) -> None:
    """将最近一条带 tool_calls 的 assistant 消息收敛为 kept_tool_calls。

    consent 门控暂停时，已追加的 assistant 消息可能包含当前待确认工具之后
    尚未执行的 tool_calls，这些 tool_calls 没有匹配的 tool 响应，会在历史
    重投时触发 provider 报错。此处将其裁剪为已处理 + 当前待确认的部分。
    """
    for message in reversed(messages):
        if message.role == "assistant" and message.tool_calls:
            message.tool_calls = list(kept_tool_calls)
            return


def prepare_parallel_readonly_batch(
    *,
    processor: ToolCallProcessor,
    tool_calls: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str, dict[str, str | None]]] | None:
    if len(tool_calls) <= 1:
        return None

    prepared: list[tuple[dict[str, Any], str, dict[str, str | None]]] = []
    for tc in tool_calls:
        func = tc.get("function", {})
        func_name = str(func.get("name") or "").strip()
        raw_args = func.get("arguments", "{}")
        arguments, parse_error = processor.parse_arguments(raw_args)
        if parse_error or arguments is None:
            return None
        if not processor.is_parallel_safe_tool_call(func_name, arguments):
            return None
        if processor.check_consent(func_name, arguments) in {"reject", "ask"}:
            return None
        prepared.append((tc, func_name, processor.get_skill_info(func_name)))
    return prepared


def apply_single_tool_result(
    *,
    processor: ToolCallProcessor,
    tc: dict[str, Any],
    func_name: str,
    skill_info: dict[str, str | None],
    single: SingleToolResult,
    state: ToolRoundExecutionState,
    execution_budget: ExecutionBudget | None,
    mark_multi_family_progress: Any,
    build_budget_exit_response: Any,
    ordered_requested_families: list[str],
    completed_families: set[str],
    input_variables: dict[str, Any] | None,
) -> ToolRoundExecutionOutcome:
    tracked_tool_result_bytes = state.tracked_tool_result_bytes

    if single.tool_result and single.tool_result.success:
        mark_multi_family_progress(
            func_name=func_name,
            success=True,
            ordered_requested_families=ordered_requested_families,
            completed_families=completed_families,
            input_variables=input_variables,
        )

    if single.tool_result:
        state.all_tool_results.append(single.tool_result)
        state.round_tool_results.append(single.tool_result)

    return _finalize_single_tool_result(
        processor=processor,
        tc=tc,
        func_name=func_name,
        skill_info=skill_info,
        single=single,
        state=state,
        execution_budget=execution_budget,
        build_budget_exit_response=build_budget_exit_response,
        tracked_tool_result_bytes=tracked_tool_result_bytes,
    )


def _finalize_single_tool_result(
    *,
    processor: ToolCallProcessor,
    tc: dict[str, Any],
    func_name: str,
    skill_info: dict[str, str | None],
    single: SingleToolResult,
    state: ToolRoundExecutionState,
    execution_budget: ExecutionBudget | None,
    build_budget_exit_response: Any,
    tracked_tool_result_bytes: int,
) -> ToolRoundExecutionOutcome:
    if single.tool_result:
        processor.annotate_tool_call(
            tc,
            duration_ms=single.duration_ms,
            result=single.tool_result,
            skill_info=skill_info,
        )
        confirmation_data = processor.check_confirmation_output(single.tool_result)
        if confirmation_data:
            processor.annotate_tool_call(
                tc,
                pending_confirmation=processor.build_pending_confirmation_payload(
                    confirmation_data,
                    func_name,
                ),
            )
        tool_result_budget_reason = BudgetGuard.tool_result_reason(
            execution_budget,
            current_bytes_used=tracked_tool_result_bytes,
            additional_results=[single.tool_result],
        )
        tracked_tool_result_bytes += len(
            (single.tool_result.output or single.tool_result.error or "").encode(
                "utf-8"
            )
        )
        if tool_result_budget_reason:
            return ToolRoundExecutionOutcome(
                tracked_tool_result_bytes=tracked_tool_result_bytes,
                early_return=(
                    build_budget_exit_response(state.total_tokens),
                    state.all_tool_results,
                    state.total_tokens,
                    state.completion_tokens_used,
                ),
            )

    if single.tool_message:
        state.messages.append(single.tool_message)
    if single.follow_up_message:
        state.follow_up_messages.append(single.follow_up_message)
    return ToolRoundExecutionOutcome(
        tracked_tool_result_bytes=tracked_tool_result_bytes,
    )


async def execute_tool_round(
    *,
    processor: ToolCallProcessor,
    tool_calls: list[dict[str, Any]],
    request: Any,
    current_response: ChatResponse,
    state: ToolRoundExecutionState,
    execution_budget: ExecutionBudget | None,
    mark_multi_family_progress: Any,
    build_budget_exit_response: Any,
    ordered_requested_families: list[str],
    completed_families: set[str],
    input_variables: dict[str, Any] | None,
) -> ToolRoundExecutionOutcome:
    parallel_batch = prepare_parallel_readonly_batch(
        processor=processor,
        tool_calls=tool_calls,
    )
    if parallel_batch is not None:
        for tc, _func_name, skill_info in parallel_batch:
            processor.annotate_tool_call(tc, skill_info=skill_info)
        singles = await asyncio.gather(
            *[
                processor.process_single(
                    tc,
                    conversation_id=request.conversation_id or 0,
                )
                for tc, _func_name, _skill_info in parallel_batch
            ]
        )
        for (tc, func_name, skill_info), single in zip(
            parallel_batch,
            singles,
            strict=False,
        ):
            outcome = apply_single_tool_result(
                processor=processor,
                tc=tc,
                func_name=func_name,
                skill_info=skill_info,
                single=single,
                state=state,
                execution_budget=execution_budget,
                mark_multi_family_progress=mark_multi_family_progress,
                build_budget_exit_response=build_budget_exit_response,
                ordered_requested_families=ordered_requested_families,
                completed_families=completed_families,
                input_variables=input_variables,
            )
            state.tracked_tool_result_bytes = outcome.tracked_tool_result_bytes
            if outcome.early_return is not None:
                return outcome
        return ToolRoundExecutionOutcome(
            tracked_tool_result_bytes=state.tracked_tool_result_bytes
        )

    for tc_index, tc in enumerate(tool_calls):
        tc_id = tc.get("id", "")
        func = tc.get("function", {})
        func_name = func.get("name", "")
        raw_args = func.get("arguments", "{}")
        arguments, parse_error = processor.parse_arguments(raw_args)

        if not parse_error:
            skill_info = processor.get_skill_info(func_name)
            processor.annotate_tool_call(tc, skill_info=skill_info)
            consent = processor.check_consent(func_name, arguments)
            if consent == "reject":
                state.messages.append(processor.build_consent_reject_message(tc_id))
                continue
            if consent == "ask":
                pending_consent = processor.build_pending_consent_payload(
                    func_name,
                    arguments,
                    skill_info,
                )
                processor.annotate_tool_call(
                    tc,
                    pending_consent=pending_consent,
                )
                state.messages.append(
                    processor.build_consent_ask_message(
                        tc_id,
                        func_name,
                        arguments,
                    )
                )
                # Consent 门控暂停时，丢弃当前待确认工具之后尚未执行的 tool_calls，
                # 仅保留「已处理 + 当前待确认」这一段。被保留项均有匹配的 tool 消息
                # （执行结果 / 拒绝消息 / consent_ask 消息），避免历史重投时出现无
                # 匹配 tool 响应的孤儿 tool_calls。
                kept_tool_calls = list(tool_calls[: tc_index + 1])
                _trim_last_assistant_tool_calls(state.messages, kept_tool_calls)
                return ToolRoundExecutionOutcome(
                    tracked_tool_result_bytes=state.tracked_tool_result_bytes,
                    early_return=(
                        ChatResponse(
                            message=ChatMessage(
                                role="assistant",
                                content=current_response.message.content or "",
                                tool_calls=kept_tool_calls,
                                metadata={"pending_consent": pending_consent},
                            ),
                            metadata={
                                **dict(getattr(current_response, "metadata", {}) or {}),
                                "skip_final_assistant": True,
                            },
                        ),
                        state.all_tool_results,
                        state.total_tokens,
                        state.completion_tokens_used,
                    ),
                )

        single = await processor.process_single(
            tc,
            conversation_id=request.conversation_id or 0,
        )
        outcome = apply_single_tool_result(
            processor=processor,
            tc=tc,
            func_name=str(func_name or ""),
            skill_info=processor.get_skill_info(func_name),
            single=single,
            state=state,
            execution_budget=execution_budget,
            mark_multi_family_progress=mark_multi_family_progress,
            build_budget_exit_response=build_budget_exit_response,
            ordered_requested_families=ordered_requested_families,
            completed_families=completed_families,
            input_variables=input_variables,
        )
        state.tracked_tool_result_bytes = outcome.tracked_tool_result_bytes
        if outcome.early_return is not None:
            return outcome

    return ToolRoundExecutionOutcome(
        tracked_tool_result_bytes=state.tracked_tool_result_bytes
    )
