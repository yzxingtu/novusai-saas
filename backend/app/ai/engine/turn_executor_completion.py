"""Completion helpers for turn execution."""

from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .types import ToolUsePolicy

if TYPE_CHECKING:
    from .turn_executor import TurnIOAdapter


def response_has_visible_content(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    return bool(str(response.message.content or "").strip())


def latest_auto_fetch_gate_reason(state: ExecutionStateMachine) -> str | None:
    for intent in reversed(state.intent_plan):
        metadata = dict(getattr(intent, "metadata", {}) or {})
        reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
        if reason:
            return reason
    return None


def completed_tool_intent_families(state: ExecutionStateMachine) -> set[str]:
    families: set[str] = set()
    for intent in state.intent_plan:
        if intent.status != "completed" or not intent.requires_tools:
            continue
        family = str(intent.family or "").strip()
        if family:
            families.add(family)
    return families


def should_complete_from_budgeted_web_research_evidence(
    *,
    state: ExecutionStateMachine,
    response: ChatResponse | None,
    tool_results: list[ToolResult],
    reason: str,
) -> Literal["none", "keep_visible_output", "replace_with_tool_evidence"]:
    if not RecoveryManager.is_budget_exit_reason(reason):
        return "none"
    if "web_research" not in completed_tool_intent_families(state):
        return "none"
    if RecoveryManager.next_unfinished_intents(state.intent_plan):
        return "none"

    response_text = str(
        getattr(getattr(response, "message", None), "content", "") or ""
    ).strip()
    if not response_text:
        return "replace_with_tool_evidence"
    if RecoveryManager.should_replace_budgeted_web_research_response(
        response_text=response_text,
        tool_results=tool_results,
    ):
        return "replace_with_tool_evidence"
    return "keep_visible_output"


def post_tool_completion_state(
    *,
    state: ExecutionStateMachine,
    final_output_source: str,
    ran_post_tool_follow_up: bool,
) -> str:
    if final_output_source == "tool_evidence_completed":
        auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
        if auto_fetch_gate_reason == "search_no_results_completed":
            return "completed_no_result"
        return "tool_evidence_completed"
    if final_output_source == "partial_output":
        return "partial_output"
    if final_output_source == "budget_fallback":
        return "budget_fallback"
    if ran_post_tool_follow_up:
        return "llm_follow_up"
    return "assistant"


async def finalize_turn_execution(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    decision: Any | None,
    tool_results: list[ToolResult],
    total_tokens: int,
    completion_tokens_used: int,
    ran_post_tool_follow_up: bool,
    emit_round_started: Any,
) -> tuple[
    str,
    bool,
    bool,
    str,
    Literal[
        "assistant",
        "tool_evidence_completed",
        "partial_output",
        "budget_fallback",
    ],
    int,
    int,
    ChatResponse,
]:
    if response is None:
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
        )
    output = response.message.content
    paused_for_consent = bool(
        decision is not None and decision.action == "pause_for_consent"
    )
    partial = bool(decision is not None and decision.action == "return_partial")
    budgeted_web_research_completion_mode: Literal[
        "none",
        "keep_visible_output",
        "replace_with_tool_evidence",
    ] = (
        should_complete_from_budgeted_web_research_evidence(
            state=state,
            response=response,
            tool_results=tool_results,
            reason=decision.reason or "return_partial",
        )
        if partial and decision is not None
        else "none"
    )
    promote_budget_partial_to_completed = bool(
        partial
        and decision is not None
        and budgeted_web_research_completion_mode != "none"
    )
    replace_budgeted_web_research_output = (
        budgeted_web_research_completion_mode == "replace_with_tool_evidence"
    )
    if decision is not None and (
        decision.action == "pause_for_consent"
        or (
            decision.action == "return_partial"
            and not promote_budget_partial_to_completed
        )
    ):
        state.recovery_history.append(decision)
    completion_reason = "completed"
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "partial_output",
        "budget_fallback",
    ] = "assistant"
    if paused_for_consent:
        state.transition("awaiting_consent")
        completion_reason = decision.reason or "pause_for_consent"
        RecoveryManager.ensure_latest_assistant_pending_consent(
            messages,
            RecoveryManager.pending_consent_payload_from_decision(decision),
        )
    elif promote_budget_partial_to_completed:
        partial = False
        state.transition("completed")
        state.preparation_diagnostics["budgeted_web_research_completion_mode"] = (
            budgeted_web_research_completion_mode
        )
        if replace_budgeted_web_research_output and response is not None:
            response.message.content = ""
        if replace_budgeted_web_research_output and tool_results:
            synthesis_policy = ToolUsePolicy(
                family="none",
                mode="none",
                allowed_tool_names=[],
                retry_on_contract_breach=False,
                reason="budget_exceeded_synthesis",
            )
            emit_round_started(
                state,
                round_kind="budget_exceeded_synthesis",
                policy=synthesis_policy,
                tools=[],
                reason="budget_exceeded_synthesis",
            )
            synthesis_round = await io.call_llm(
                messages=messages,
                tools=None,
                tool_use_policy=synthesis_policy,
                breach_retry_result="budget_exceeded_synthesis",
            )
            synthesis_text = str(
                getattr(
                    getattr(synthesis_round.response, "message", None),
                    "content",
                    "",
                )
                or ""
            ).strip()
            if synthesis_text:
                output = synthesis_text
                total_tokens += int(synthesis_round.total_tokens or 0)
                completion_tokens_used += int(
                    synthesis_round.completion_tokens_used or 0
                )
                state.register_completion_tokens(completion_tokens_used)
                final_output_source = "assistant"
        if not str(output or "").strip():
            output, total_tokens, completion_tokens_used = (
                await io.finalize_completed_output(
                    messages=messages,
                    response=response,
                    state=state,
                    tool_results=tool_results,
                    reason=decision.reason or "completed",
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )
            if str(output or "").strip():
                final_output_source = "tool_evidence_completed"
    elif partial:
        state.transition("partial_exit")
        completion_reason = decision.reason or "return_partial"
        had_visible_output = bool(str(output or "").strip())
        output, total_tokens, completion_tokens_used = (
            await io.finalize_partial_output(
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=completion_reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
        )
        if (
            not had_visible_output
            and state.provider_failure_kind == "budget_exit"
            and str(output or "").strip()
        ):
            final_output_source = "budget_fallback"
        else:
            final_output_source = "partial_output"
    else:
        state.transition("completed")
        if not str(output or "").strip() and state.intent_plan:
            output, total_tokens, completion_tokens_used = (
                await io.finalize_completed_output(
                    messages=messages,
                    response=response,
                    state=state,
                    tool_results=tool_results,
                    reason=completion_reason,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )
            if str(output or "").strip():
                if (
                    str(
                        state.preparation_diagnostics.get("contract_breach_type")
                        or ""
                    ).strip()
                    and not RecoveryManager.has_completed_output_evidence(
                        state.intent_plan,
                        tool_results=tool_results,
                    )
                ):
                    final_output_source = "partial_output"
                else:
                    final_output_source = "tool_evidence_completed"

    state.preparation_diagnostics["final_output_source"] = final_output_source
    state.preparation_diagnostics["post_tool_completion_state"] = (
        post_tool_completion_state(
            state=state,
            final_output_source=final_output_source,
            ran_post_tool_follow_up=ran_post_tool_follow_up,
        )
    )
    auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
    if auto_fetch_gate_reason:
        state.preparation_diagnostics["auto_fetch_gate_reason"] = (
            auto_fetch_gate_reason
        )

    return (
        str(output or ""),
        partial,
        paused_for_consent,
        completion_reason,
        final_output_source,
        total_tokens,
        completion_tokens_used,
        response,
    )


__all__ = [
    "completed_tool_intent_families",
    "finalize_turn_execution",
    "latest_auto_fetch_gate_reason",
    "post_tool_completion_state",
    "response_has_visible_content",
    "should_complete_from_budgeted_web_research_evidence",
]
