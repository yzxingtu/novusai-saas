"""Completion helpers for turn execution."""

from __future__ import annotations

from typing import Literal

from app.ai.tools.types import ToolResult
from app.ai.types import ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager


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


__all__ = [
    "completed_tool_intent_families",
    "latest_auto_fetch_gate_reason",
    "post_tool_completion_state",
    "response_has_visible_content",
    "should_complete_from_budgeted_web_research_evidence",
]
