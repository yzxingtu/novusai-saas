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
        actionable = [
            intent
            for intent in intents
            if intent.family not in {"none", "page_ops"}
        ]
        families = {intent.family for intent in actionable}
        if len(actionable) <= 1 and len(families) <= 1:
            first = actionable[0] if actionable else intents[0]
            if first.kind in {
                "direct_reply",
                "weather_query",
                "time_query",
            }:
                return "fast"
        if len(actionable) <= 2 and len(families) <= 2:
            return "normal"
        return "deep"


__all__ = ["PathSelector"]
