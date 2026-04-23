"""Execution path selection for fast/normal/deep orchestration."""

from __future__ import annotations

from .page_workflow_state_machine import resolve_page_workflow_goal
from .types import ExecutionPath, IntentPlan


def _page_workflow_phase(intent: IntentPlan) -> str:
    return str((intent.metadata or {}).get("page_workflow_phase") or "").strip()


def _page_workflow_goal(intent: IntentPlan) -> str:
    return resolve_page_workflow_goal(
        intent_kind=intent.kind,
        intent_metadata=intent.metadata,
        user_text=intent.source_text,
    )


def _is_fast_page_intent(intent: IntentPlan) -> bool:
    if intent.family != "page_ops":
        return False
    phase = _page_workflow_phase(intent)
    goal = _page_workflow_goal(intent)
    if phase in {"navigate_or_open", "submit", "write"}:
        return False
    return goal not in {"editor_write", "form_write", "navigation"}


def _is_deep_page_intent(intent: IntentPlan) -> bool:
    if intent.family != "page_ops":
        return False
    phase = _page_workflow_phase(intent)
    goal = _page_workflow_goal(intent)
    return phase in {"navigate_or_open", "submit", "write"} or goal in {
        "editor_write",
        "form_write",
        "navigation",
    }


class PathSelector:
    @staticmethod
    def select(intents: list[IntentPlan]) -> ExecutionPath:
        if not intents:
            return "fast"
        if all(intent.shortcircuit for intent in intents):
            return "fast"
        actionable = [intent for intent in intents if intent.family != "none"]
        families = {intent.family for intent in actionable}
        if len(actionable) <= 1 and len(families) <= 1:
            first = actionable[0] if actionable else intents[0]
            if first.kind in {
                "direct_reply",
                "weather_query",
                "time_query",
            } or _is_fast_page_intent(first):
                return "fast"
        if (
            len(actionable) <= 2
            and len(families) <= 2
            and not any(_is_deep_page_intent(intent) for intent in actionable)
        ):
            return "normal"
        return "deep"


__all__ = ["PathSelector"]
