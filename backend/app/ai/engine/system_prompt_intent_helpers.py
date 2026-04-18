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
_PAGE_INTENT_COMPLETION_SIGNAL_NAMES: dict[str, tuple[str, ...]] = {
    "page_summary": (
        "ui_get_snapshot",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
    ),
    "page_screenshot": ("ui_get_snapshot",),
    "page_navigation": ("ui_open_surface", "ui_click"),
    "page_pagination": ("ui_click",),
    "page_row_detail": (
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
    ),
    "page_form_read": ("ui_get_form_state", "ui_read_region"),
    "page_form_write": ("ui_fill_form", "ui_set_field", "ui_submit_form"),
    "page_search": ("ui_click", "ui_read_region"),
    "page_editor_read": ("ui_read_region",),
    "page_editor_write": ("ui_fill_form", "ui_submit_form"),
}


def _ordered_unique_tool_names(*groups: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            normalized = str(name or "").strip()
            if not normalized or normalized in seen:
                continue
            ordered.append(normalized)
            seen.add(normalized)
    return ordered


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
    intent_kind: str | None = None,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
) -> list[str]:
    ordered_tool_names = _ordered_unique_tool_names(
        list(preferred_tool_names or []),
        list(allowed_tool_names or []),
    )
    if family == "web_research":
        if "fetch_url" in allowed_tool_names:
            return ["fetch_url"]
        if "web_search" in allowed_tool_names:
            return ["web_search"]
    if family == "page_ops":
        page_intent_kind = str(intent_kind or "").strip()
        if page_intent_kind in _PAGE_INTENT_COMPLETION_SIGNAL_NAMES:
            allowed_signals = set(
                _PAGE_INTENT_COMPLETION_SIGNAL_NAMES[page_intent_kind]
            )
            return [
                name for name in ordered_tool_names if name in allowed_signals
            ]
        non_snapshot_names = [
            name for name in ordered_tool_names if name != "ui_get_snapshot"
        ]
        return non_snapshot_names or list(ordered_tool_names)
    return list(allowed_tool_names or preferred_tool_names)
