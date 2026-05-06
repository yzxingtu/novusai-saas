"""
Result assembly support for context engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.contracts import ContextCapabilityFinalization
from app.ai.runtime.types import CapabilityBundle


@dataclass
class ContextDiagnosticsInputs:
    prune_stats: Any
    compaction_source_tokens: int
    estimated_tokens_before_prune: int
    estimated_tokens_after_prune: int
    context_compacted: bool
    memory_recalled: bool
    intent_plan: list[Any] = field(default_factory=list)
    intent_flags: dict[str, bool] = field(default_factory=dict)
    dynamic_capability_awareness_enabled: bool = False
    dynamic_capability_awareness_injected: bool = False
    capability_awareness_categories: list[str] = field(default_factory=list)
    capability_awareness_error: str | None = None
    requested_knowledge_base_ids: list[int] = field(default_factory=list)
    effective_knowledge_base_ids: list[int] = field(default_factory=list)
    dropped_knowledge_base_ids: list[int] = field(default_factory=list)
    context_budget: dict[str, Any] = field(default_factory=dict)
    budget_usage: dict[str, Any] = field(default_factory=dict)
    capability_injection_decision: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityFinalizationMergeResult:
    diagnostics: dict[str, Any] = field(default_factory=dict)
    capability_bundle: CapabilityBundle | None = None
    capability_injection_decision: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextAssemblyPayload:
    messages: list[Any] = field(default_factory=list)
    estimated_tokens: int = 0
    system_prompt_additions: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    rag_sources: list[dict[str, Any]] | None = None
    rag_source_kinds: list[str] = field(default_factory=list)
    compact_summary: str | None = None
    prune_stats: dict[str, Any] | None = None
    memory_recall_slice: dict[str, Any] | None = None
    context_compacted: bool = False
    memory_recalled: bool = False
    capability_bundle: CapabilityBundle | None = None


def build_context_budget_diagnostics(
    *,
    context_budget: dict[str, Any],
    budget_usage: dict[str, Any],
    estimated_tokens_after_prune: int,
) -> dict[str, Any]:
    return {
        **dict(context_budget or {}),
        "system_additions_used_tokens": int(
            (budget_usage or {}).get("used_tokens", 0) or 0
        ),
        "trimmed_sections": list((budget_usage or {}).get("trimmed_sections", [])),
        "skipped_sections": list((budget_usage or {}).get("skipped_sections", [])),
        "prompt_budget_exceeded": (
            estimated_tokens_after_prune
            > int((context_budget or {}).get("prompt_target_tokens", 0) or 0)
        ),
    }


def build_context_diagnostics(
    inputs: ContextDiagnosticsInputs,
) -> dict[str, Any]:
    diagnostics = {
        "pruning_applied": bool(getattr(inputs.prune_stats, "pruned_message_count", 0)),
        "compaction_source_tokens": inputs.compaction_source_tokens,
        "estimated_tokens_before_prune": inputs.estimated_tokens_before_prune,
        "estimated_tokens_after_prune": inputs.estimated_tokens_after_prune,
        "context_compacted": inputs.context_compacted,
        "memory_recalled": inputs.memory_recalled,
        "intent_plan": [
            intent.to_dict() if hasattr(intent, "to_dict") else intent
            for intent in (inputs.intent_plan or [])
        ],
        "allow_memory_even_if_shortcircuit": bool(
            (inputs.intent_flags or {}).get("allow_memory_even_if_shortcircuit", False)
        ),
        "dynamic_capability_awareness_enabled": (
            inputs.dynamic_capability_awareness_enabled
        ),
        "dynamic_capability_awareness_injected": (
            inputs.dynamic_capability_awareness_injected
        ),
        "dynamic_capability_awareness_categories": list(
            inputs.capability_awareness_categories or []
        ),
        "requested_knowledge_base_ids": list(inputs.requested_knowledge_base_ids or []),
        "effective_knowledge_base_ids": list(inputs.effective_knowledge_base_ids or []),
        "dropped_knowledge_base_ids": list(inputs.dropped_knowledge_base_ids or []),
        "context_budget": build_context_budget_diagnostics(
            context_budget=inputs.context_budget,
            budget_usage=inputs.budget_usage,
            estimated_tokens_after_prune=inputs.estimated_tokens_after_prune,
        ),
        "capability_injection_decision": dict(
            inputs.capability_injection_decision or {}
        ),
    }
    if inputs.capability_awareness_error:
        diagnostics["dynamic_capability_awareness_error"] = (
            inputs.capability_awareness_error
        )
    return diagnostics


def merge_capability_finalization(
    *,
    diagnostics: dict[str, Any],
    capability_finalization: ContextCapabilityFinalization,
) -> CapabilityFinalizationMergeResult:
    merged_diagnostics = dict(diagnostics or {})
    merged_diagnostics.update(capability_finalization.diagnostics or {})
    merged_capability_injection_decision = dict(
        capability_finalization.capability_injection_decision or {}
    )
    merged_diagnostics["runtime_capability_manifest"] = dict(
        capability_finalization.runtime_manifest or {}
    )
    merged_diagnostics["runtime_capability_summary"] = (
        capability_finalization.runtime_capability_summary
    )
    merged_diagnostics["capability_injection_decision"] = (
        merged_capability_injection_decision
    )
    return CapabilityFinalizationMergeResult(
        diagnostics=merged_diagnostics,
        capability_bundle=capability_finalization.capability_bundle,
        capability_injection_decision=merged_capability_injection_decision,
    )


def build_context_assembly_payload(
    *,
    messages: list[Any],
    estimated_tokens: int,
    system_prompt_additions: list[str],
    diagnostics: dict[str, Any],
    rag_sources: list[dict[str, Any]] | None,
    rag_source_kinds: list[str],
    compact_summary: str | None,
    prune_stats: Any,
    memory_recall_slice: dict[str, Any] | None,
    context_compacted: bool,
    memory_recalled: bool,
    capability_bundle: CapabilityBundle | None,
) -> ContextAssemblyPayload:
    return ContextAssemblyPayload(
        messages=list(messages or []),
        estimated_tokens=estimated_tokens,
        system_prompt_additions=list(system_prompt_additions or []),
        diagnostics=dict(diagnostics or {}),
        rag_sources=rag_sources,
        rag_source_kinds=list(rag_source_kinds or []),
        compact_summary=compact_summary,
        prune_stats=(
            prune_stats.to_dict() if hasattr(prune_stats, "to_dict") else prune_stats
        ),
        memory_recall_slice=(
            dict(memory_recall_slice or {}) if memory_recall_slice else None
        ),
        context_compacted=context_compacted,
        memory_recalled=memory_recalled,
        capability_bundle=capability_bundle,
    )


__all__ = [
    "CapabilityFinalizationMergeResult",
    "ContextAssemblyPayload",
    "ContextDiagnosticsInputs",
    "build_context_assembly_payload",
    "build_context_budget_diagnostics",
    "build_context_diagnostics",
    "merge_capability_finalization",
]
