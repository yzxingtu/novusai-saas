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


def _ordered_matching_tool_names(
    tool_names: list[str],
    completed_tool_names: set[str],
) -> list[str]:
    return [name for name in tool_names if name in completed_tool_names]


def intent_completion_contract(
    family: str,
    *,
    intent_kind: str | None = None,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
    intent_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = list(allowed_tool_names or preferred_tool_names)

    # Internal-ops meta-tools form a list -> describe -> invoke chain: only the
    # terminal invoke completes the intent; discovery calls are action steps.
    # 内部操作元工具是 list -> describe -> invoke 链：仅终态 invoke 视为完成，
    # 发现类调用属于过程动作。
    normalized_family = str(family or "").strip().lower()
    if normalized_family == "internal_ops":
        from app.ai.internal_ops.tools import TOOL_INVOKE_OPERATION

        if TOOL_INVOKE_OPERATION in allowed:
            return {
                "mode": "any_of",
                "completion_signals": [TOOL_INVOKE_OPERATION],
                "action_signals": [
                    name for name in allowed if name != TOOL_INVOKE_OPERATION
                ],
                "verify_signals": [],
            }

    return {
        "mode": "any_of",
        "completion_signals": allowed,
        "action_signals": [],
        "verify_signals": [],
    }


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
            item = IntentPlan(**raw_intent)
        except TypeError:
            continue
        intent_plan.append(item)
    return intent_plan


def intent_plan_gating_flags(
    intent_plan: list[IntentPlan],
    request: Any | None = None,
) -> dict[str, bool]:
    flags = ContextPipelineOrchestrator.compute_intent_flags(
        intent_plan,
        request=request,
    )
    return {
        "all_shortcircuit": bool(flags.all_shortcircuit),
        "has_knowledge_intent": bool(flags.has_knowledge_intent),
        "has_bound_kb": bool(flags.has_bound_kb),
        "should_skip_bound_kb_rag": bool(flags.should_skip_bound_kb_rag),
        "has_memory_intent": bool(flags.has_memory_intent),
        "memory_context_enabled": bool(flags.memory_context_enabled),
        "session_memory_runtime_enabled": bool(flags.session_memory_runtime_enabled),
        "long_term_memory_runtime_enabled": bool(
            flags.long_term_memory_runtime_enabled
        ),
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
    intent_metadata: dict[str, Any] | None = None,
) -> list[str]:
    contract = intent_completion_contract(
        family,
        intent_kind=intent_kind,
        allowed_tool_names=allowed_tool_names,
        preferred_tool_names=preferred_tool_names,
        intent_metadata=intent_metadata,
    )
    return list(contract.get("completion_signals") or [])


def intent_completion_matches(
    family: str,
    *,
    completed_tool_names: set[str],
    intent_kind: str | None = None,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
    intent_metadata: dict[str, Any] | None = None,
) -> list[str]:
    contract = intent_completion_contract(
        family,
        intent_kind=intent_kind,
        allowed_tool_names=allowed_tool_names,
        preferred_tool_names=preferred_tool_names,
        intent_metadata=intent_metadata,
    )
    completion_signals = list(contract.get("completion_signals") or [])
    return _ordered_matching_tool_names(
        completion_signals,
        completed_tool_names,
    )


def intent_completion_progress(
    family: str,
    *,
    completed_tool_names: set[str],
    intent_kind: str | None = None,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
    intent_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = intent_completion_contract(
        family,
        intent_kind=intent_kind,
        allowed_tool_names=allowed_tool_names,
        preferred_tool_names=preferred_tool_names,
        intent_metadata=intent_metadata,
    )
    completion_signals = list(contract.get("completion_signals") or [])
    action_signals = list(contract.get("action_signals") or [])
    verify_signals = list(contract.get("verify_signals") or completion_signals)
    completion_matches = intent_completion_matches(
        family,
        completed_tool_names=completed_tool_names,
        intent_kind=intent_kind,
        allowed_tool_names=allowed_tool_names,
        preferred_tool_names=preferred_tool_names,
        intent_metadata=intent_metadata,
    )
    action_matches = _ordered_matching_tool_names(
        action_signals,
        completed_tool_names,
    )
    verify_matches = _ordered_matching_tool_names(
        verify_signals,
        completed_tool_names,
    )
    mode = str(contract.get("mode") or "any_of").strip()
    continuation_required = not bool(completion_matches)
    status = "completed" if completion_matches else "pending"
    return {
        "mode": mode,
        "completion_signals": completion_signals,
        "action_signals": action_signals,
        "verify_signals": verify_signals,
        "matched_completion_signals": completion_matches,
        "matched_action_signals": action_matches,
        "matched_verify_signals": verify_matches,
        "continuation_required": continuation_required,
        "status": status,
    }
