"""
Context pipeline orchestrator helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.memory_policy import resolve_memory_runtime_policy


@dataclass(frozen=True)
class IntentPlanFlags:
    all_shortcircuit: bool
    has_knowledge_intent: bool
    has_bound_kb: bool
    should_skip_bound_kb_rag: bool
    has_memory_intent: bool
    memory_context_enabled: bool
    has_memory_save_intent: bool
    has_memory_recall_intent: bool
    session_memory_runtime_enabled: bool
    long_term_memory_runtime_enabled: bool
    allow_memory_even_if_shortcircuit: bool
    should_run_memory_profile: bool
    should_run_memory_vector_recall: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "all_shortcircuit": self.all_shortcircuit,
            "has_knowledge_intent": self.has_knowledge_intent,
            "has_bound_kb": self.has_bound_kb,
            "should_skip_bound_kb_rag": self.should_skip_bound_kb_rag,
            "has_memory_intent": self.has_memory_intent,
            "memory_context_enabled": self.memory_context_enabled,
            "has_memory_save_intent": self.has_memory_save_intent,
            "has_memory_recall_intent": self.has_memory_recall_intent,
            "session_memory_runtime_enabled": self.session_memory_runtime_enabled,
            "long_term_memory_runtime_enabled": self.long_term_memory_runtime_enabled,
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
        normalized_plan = list(intent_plan or [])
        intent_kinds = {
            str(getattr(intent, "kind", "") or "").strip() for intent in normalized_plan
        }
        all_shortcircuit = bool(normalized_plan) and all(
            bool(getattr(intent, "shortcircuit", False)) for intent in normalized_plan
        )
        has_knowledge_intent = "knowledge_query" in intent_kinds
        has_bound_kb = bool(
            request is not None
            and bool(getattr(request, "_has_bound_knowledge_base", False))
        )
        deterministic_shortcircuit_kinds = {
            "confirmation_replay",
            "memory_recall",
            "memory_save",
            "time_query",
        }
        should_skip_bound_kb_rag = bool(normalized_plan) and all(
            bool(getattr(intent, "shortcircuit", False))
            and (
                str(getattr(intent, "kind", "") or "").strip()
                in deterministic_shortcircuit_kinds
                or str(
                    (getattr(intent, "metadata", None) or {}).get("routing_mode")
                    or ""
                ).strip()
                == "deterministic_shortcircuit"
            )
            for intent in normalized_plan
        )
        has_memory_save_intent = "memory_save" in intent_kinds
        has_memory_recall_intent = "memory_recall" in intent_kinds
        memory_policy = resolve_memory_runtime_policy(request)
        session_memory_runtime_enabled = bool(
            memory_policy.session_memory_state != "disabled"
        )
        long_term_memory_runtime_enabled = bool(
            memory_policy.long_term_memory_runtime_enabled
        )
        allow_memory_even_if_shortcircuit = (
            has_memory_save_intent or has_memory_recall_intent
        )
        has_memory_intent = bool(has_memory_save_intent or has_memory_recall_intent)
        memory_context_enabled = bool(
            has_memory_intent
            or (memory_policy.memory_context_enabled and not all_shortcircuit)
        )
        should_run_memory_profile = has_memory_recall_intent
        should_run_memory_vector_recall = bool(
            has_memory_recall_intent
            or (
                memory_policy.long_term_memory_recall_state == "enabled"
                and not all_shortcircuit
            )
        )
        return IntentPlanFlags(
            all_shortcircuit=all_shortcircuit,
            has_knowledge_intent=has_knowledge_intent,
            has_bound_kb=has_bound_kb,
            should_skip_bound_kb_rag=should_skip_bound_kb_rag,
            has_memory_intent=has_memory_intent,
            memory_context_enabled=memory_context_enabled,
            has_memory_save_intent=has_memory_save_intent,
            has_memory_recall_intent=has_memory_recall_intent,
            session_memory_runtime_enabled=session_memory_runtime_enabled,
            long_term_memory_runtime_enabled=long_term_memory_runtime_enabled,
            allow_memory_even_if_shortcircuit=allow_memory_even_if_shortcircuit,
            should_run_memory_profile=should_run_memory_profile,
            should_run_memory_vector_recall=should_run_memory_vector_recall,
        )

    @staticmethod
    def _last_user_text(request: Any | None) -> str:
        messages = list(getattr(request, "messages", None) or [])
        for message in reversed(messages):
            if str(getattr(message, "role", "") or "").strip() != "user":
                continue
            text = str(getattr(message, "content", "") or "").strip()
            if text:
                return text
        return ""


__all__ = ["ContextPipelineOrchestrator", "IntentPlanFlags"]
