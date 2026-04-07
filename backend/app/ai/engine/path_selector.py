"""Execution path selection for fast/normal/deep orchestration."""

from __future__ import annotations

from .types import ExecutionPath, IntentPlan


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
                "page_summary",
            }:
                return "fast"
        deep_page_kinds = {
            "page_navigation",
            "page_form_write",
            "page_editor_write",
        }
        if (
            len(actionable) <= 2
            and len(families) <= 2
            and not any(
                intent.kind in deep_page_kinds
                for intent in actionable
            )
        ):
            return "normal"
        return "deep"


__all__ = ["PathSelector"]
