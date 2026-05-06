"""Capability summary gating and decision helpers."""

from __future__ import annotations

from typing import Any


def should_skip_capability_summary(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    force_capability_summary: bool,
) -> bool:
    awareness_categories = {
        str(category or "").strip()
        for category in diagnostics.get("dynamic_capability_awareness_categories") or []
    }
    raw_context_budget = diagnostics.get("context_budget") or {}
    context_budget = raw_context_budget if isinstance(raw_context_budget, dict) else {}
    trimmed_sections = {
        str(section or "").strip()
        for section in context_budget.get("trimmed_sections") or []
    }
    dynamic_skill_awareness_injected = bool(
        diagnostics.get("dynamic_capability_awareness_injected")
    ) and (
        "skills" in awareness_categories
        and "dynamic_capability_awareness" not in trimmed_sections
    )
    return dynamic_skill_awareness_injected or (
        bool(intent_flags.get("all_shortcircuit")) and not force_capability_summary
    )


def resolve_capability_injection_decision(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    context_sources: list[Any] | None,
    capability_summary_injected: bool,
) -> dict[str, Any]:
    decision = dict(diagnostics.get("capability_injection_decision") or {})
    decision.setdefault("all_shortcircuit", bool(intent_flags.get("all_shortcircuit")))
    decision.setdefault("skills_injected", False)
    decision.setdefault("kb_injected", False)
    decision.setdefault("memory_injected", False)
    decision.setdefault(
        "bypass_reason",
        "all_shortcircuit" if bool(intent_flags.get("all_shortcircuit")) else None,
    )

    active_context_source_kinds = {
        str(source.kind or "").strip()
        for source in (context_sources or [])
        if bool(getattr(source, "active", True))
    }
    decision["skills_injected"] = bool(
        capability_summary_injected and "skill" in active_context_source_kinds
    )
    decision["kb_injected"] = bool(
        decision["kb_injected"]
        or (
            capability_summary_injected
            and "knowledge_base" in active_context_source_kinds
            and bool(intent_flags.get("has_knowledge_intent"))
        )
    )
    decision["memory_injected"] = bool(
        decision["memory_injected"]
        or (
            capability_summary_injected
            and (
                "session_memory" in active_context_source_kinds
                or "long_term_memory" in active_context_source_kinds
            )
            and bool(
                intent_flags.get(
                    "memory_context_enabled",
                    intent_flags.get("has_memory_intent"),
                )
            )
        )
    )
    return decision
