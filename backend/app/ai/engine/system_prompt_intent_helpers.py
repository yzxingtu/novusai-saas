"""Intent plan parsing and capability query helpers extracted from BaseEngine."""

from __future__ import annotations

from typing import Any

from app.ai.context.orchestrator import ContextPipelineOrchestrator

from .types import IntentPlan

_CAPABILITY_REPORTING_QUERY_TERMS = (
    "这轮有哪些能力",
    "当前能力",
    "本轮能力",
    "你有哪些能力",
    "你能做什么",
    "可以做什么",
    "能力有哪些",
    "available capabilities",
    "current capabilities",
    "capabilities this turn",
    "what can you do this turn",
    "what can you do",
)


def deserialize_intent_plan(raw_intent_plan: Any) -> list[IntentPlan]:
    if not isinstance(raw_intent_plan, list):
        return []
    intent_plan: list[IntentPlan] = []
    for raw_intent in raw_intent_plan:
        if isinstance(raw_intent, IntentPlan):
            intent_plan.append(raw_intent)
            continue
        if not isinstance(raw_intent, dict):
            continue
        try:
            intent_plan.append(IntentPlan(**raw_intent))
        except TypeError:
            continue
    return intent_plan


def intent_plan_gating_flags(intent_plan: list[IntentPlan]) -> dict[str, bool]:
    flags = ContextPipelineOrchestrator.compute_intent_flags(intent_plan)
    return {
        "all_shortcircuit": bool(flags.all_shortcircuit),
        "has_page_intent": bool(flags.has_page_intent),
        "has_knowledge_intent": bool(flags.has_knowledge_intent),
        "has_memory_intent": bool(flags.has_memory_intent),
    }


def is_capability_reporting_query(user_text: str | None) -> bool:
    normalized = " ".join(str(user_text or "").strip().lower().split())
    if not normalized:
        return False
    return any(term in normalized for term in _CAPABILITY_REPORTING_QUERY_TERMS)


def intent_completion_signals(
    family: str,
    *,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
) -> list[str]:
    if family == "web_research":
        if "fetch_url" in allowed_tool_names:
            return ["fetch_url"]
        if "web_search" in allowed_tool_names:
            return ["web_search"]
    return list(allowed_tool_names or preferred_tool_names)
