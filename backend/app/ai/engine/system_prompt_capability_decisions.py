"""Capability summary gating and decision helpers."""

from __future__ import annotations

from typing import Any


def resolve_capability_injection_decision(
    *,
    diagnostics: dict[str, Any],
    intent_flags: dict[str, bool],
    context_sources: list[Any] | None,
    capability_summary_injected: bool,
) -> dict[str, Any]:
    decision = dict(diagnostics.get("capability_injection_decision") or {})
    all_shortcircuit = bool(intent_flags.get("all_shortcircuit"))
    decision["all_shortcircuit"] = all_shortcircuit
    decision.setdefault("skills_injected", False)
    decision.setdefault("kb_injected", False)
    decision.setdefault("memory_injected", False)
    if all_shortcircuit:
        decision.setdefault("bypass_reason", "all_shortcircuit")
    elif decision.get("bypass_reason") == "all_shortcircuit":
        decision["bypass_reason"] = None
    else:
        decision.setdefault("bypass_reason", None)

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
            and bool(
                intent_flags.get(
                    "has_bound_kb",
                    intent_flags.get("has_knowledge_intent"),
                )
            )
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
