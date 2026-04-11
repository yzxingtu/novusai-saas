"""
Context pipeline orchestrator helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

if False:  # pragma: no cover
    from app.ai.engine.types import ExecutionRequest


@dataclass(frozen=True)
class IntentPlanFlags:
    all_shortcircuit: bool
    has_page_intent: bool
    has_knowledge_intent: bool
    has_web_research_intent: bool
    has_memory_intent: bool
    has_memory_save_intent: bool
    has_memory_recall_intent: bool
    allow_memory_even_if_shortcircuit: bool
    should_run_memory_profile: bool
    should_run_memory_vector_recall: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "all_shortcircuit": self.all_shortcircuit,
            "has_page_intent": self.has_page_intent,
            "has_knowledge_intent": self.has_knowledge_intent,
            "has_web_research_intent": self.has_web_research_intent,
            "has_memory_intent": self.has_memory_intent,
            "has_memory_save_intent": self.has_memory_save_intent,
            "has_memory_recall_intent": self.has_memory_recall_intent,
            "allow_memory_even_if_shortcircuit": (
                self.allow_memory_even_if_shortcircuit
            ),
            "should_run_memory_profile": self.should_run_memory_profile,
            "should_run_memory_vector_recall": self.should_run_memory_vector_recall,
        }


class ContextPipelineOrchestrator:
    """
    Intent-aware context orchestration decisions.
    """

    @staticmethod
    def compute_intent_flags(
        intent_plan: list[Any],
        request: Any | None = None,
    ) -> IntentPlanFlags:
        _ = request
        normalized_plan = list(intent_plan or [])
        intent_kinds = {
            str(getattr(intent, "kind", "") or "").strip()
            for intent in normalized_plan
        }
        all_shortcircuit = bool(normalized_plan) and all(
            bool(getattr(intent, "shortcircuit", False))
            for intent in normalized_plan
        )
        has_page_intent = any(kind.startswith("page_") for kind in intent_kinds)
        has_knowledge_intent = "knowledge_query" in intent_kinds
        has_web_research_intent = (
            "web_research" in intent_kinds
            or any(
                str(getattr(intent, "family", "") or "").strip() == "web_research"
                for intent in normalized_plan
            )
        )
        has_memory_save_intent = "memory_save" in intent_kinds
        has_memory_recall_intent = "memory_recall" in intent_kinds
        allow_memory_even_if_shortcircuit = (
            has_memory_save_intent or has_memory_recall_intent
        )
        has_memory_intent = allow_memory_even_if_shortcircuit
        should_run_memory_profile = has_memory_recall_intent
        should_run_memory_vector_recall = has_memory_recall_intent
        return IntentPlanFlags(
            all_shortcircuit=all_shortcircuit,
            has_page_intent=has_page_intent,
            has_knowledge_intent=has_knowledge_intent,
            has_web_research_intent=has_web_research_intent,
            has_memory_intent=has_memory_intent,
            has_memory_save_intent=has_memory_save_intent,
            has_memory_recall_intent=has_memory_recall_intent,
            allow_memory_even_if_shortcircuit=allow_memory_even_if_shortcircuit,
            should_run_memory_profile=should_run_memory_profile,
            should_run_memory_vector_recall=should_run_memory_vector_recall,
        )


__all__ = ["ContextPipelineOrchestrator", "IntentPlanFlags"]
