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
_LEGACY_PAGE_WORKFLOW_GOALS: dict[str, str] = {
    "page_summary": "page_summary",
    "page_screenshot": "page_screenshot",
    "page_navigation": "navigation",
    "page_search": "search",
    "page_pagination": "pagination",
    "page_row_detail": "row_detail",
    "page_form_read": "form_read",
    "page_form_write": "form_write",
    "page_editor_read": "editor_read",
    "page_editor_write": "editor_write",
}
_PAGE_WORKFLOW_COMPLETION_SIGNAL_NAMES: dict[str, tuple[str, ...]] = {
    "page_summary": (
        "ui_get_snapshot",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
    ),
    "page_screenshot": ("ui_get_snapshot",),
    "table_summary": ("ui_read_table", "ui_read_region"),
    "navigation": ("ui_get_snapshot",),
    "pagination": ("ui_read_table",),
    "row_detail": (
        "ui_read_region",
        "ui_read_table",
        "ui_get_snapshot",
    ),
    "form_read": ("ui_get_form_state", "ui_read_region"),
    "form_write": ("ui_fill_form", "ui_set_field", "ui_submit_form"),
    "search": ("ui_read_region",),
    "editor_read": ("ui_read_region",),
    "editor_write": ("ui_fill_form", "ui_submit_form"),
}
_PAGE_WORKFLOW_ACTION_SIGNAL_NAMES: dict[str, tuple[str, ...]] = {
    "navigation": ("ui_click", "ui_open_surface"),
    "pagination": ("ui_click",),
    "row_detail": ("ui_click", "ui_open_surface"),
}
_PAGE_WORKFLOW_STAGE_COMPLETION_MODES: dict[str, dict[str, str]] = {
    "navigation": {
        "discover_navigation_target": "action_then_verify",
        "verify_navigation_result": "verify_only",
    },
    "row_detail": {
        "open_detail_surface": "action_then_verify",
        "read_detail_surface": "verify_only",
    },
    "form_read": {
        "discover_form_surface": "verify_only",
        "read_active_form": "verify_only",
    },
    "form_write": {
        "discover_form_before_write": "verify_only",
        "fill_active_form": "verify_only",
        "submit_active_form": "verify_only",
    },
    "editor_write": {
        "discover_editor_surface": "verify_only",
        "edit_active_editor": "verify_only",
        "submit_active_editor": "verify_only",
    },
}
_PAGE_WORKFLOW_STAGE_COMPLETION_SIGNAL_NAMES: dict[str, dict[str, tuple[str, ...]]] = {
    "navigation": {
        "verify_navigation_result": ("ui_get_snapshot",),
    },
    "row_detail": {
        "open_detail_surface": (
            "ui_read_region",
            "ui_read_table",
            "ui_get_snapshot",
        ),
        "read_detail_surface": (
            "ui_read_region",
            "ui_read_table",
            "ui_get_snapshot",
        ),
    },
    "form_read": {
        "discover_form_surface": (
            "ui_get_form_state",
            "ui_read_region",
            "ui_get_snapshot",
        ),
        "read_active_form": (
            "ui_get_form_state",
            "ui_read_region",
            "ui_get_snapshot",
        ),
    },
    "form_write": {
        "discover_form_before_write": (
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ),
        "fill_active_form": (
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ),
        "submit_active_form": ("ui_submit_form",),
    },
    "editor_write": {
        "discover_editor_surface": ("ui_fill_form", "ui_submit_form"),
        "edit_active_editor": ("ui_fill_form", "ui_submit_form"),
        "submit_active_editor": ("ui_submit_form",),
    },
}
_VALID_PAGE_COMPLETION_MODES = {"any_of", "action_then_verify", "verify_only"}


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


def _ordered_subset(
    ordered_tool_names: list[str],
    raw_tool_names: Any,
) -> list[str]:
    if not isinstance(raw_tool_names, (list, tuple, set)):
        return []
    requested = {
        str(name or "").strip() for name in raw_tool_names if str(name or "").strip()
    }
    if not requested:
        return []
    return [name for name in ordered_tool_names if name in requested]


def _page_completion_contract_from_metadata(
    *,
    intent_metadata: dict[str, Any] | None,
    ordered_tool_names: list[str],
) -> dict[str, Any] | None:
    if not isinstance(intent_metadata, dict):
        return None
    raw_contract = intent_metadata.get("page_workflow_completion")
    if not isinstance(raw_contract, dict):
        return None

    mode = str(raw_contract.get("mode") or "verify_only").strip()
    if mode not in _VALID_PAGE_COMPLETION_MODES:
        mode = "verify_only"

    completion_signals = _ordered_subset(
        ordered_tool_names,
        raw_contract.get("completion_signals"),
    )
    action_signals = _ordered_subset(
        ordered_tool_names,
        raw_contract.get("action_signals"),
    )
    verify_signals = _ordered_subset(
        ordered_tool_names,
        raw_contract.get("verify_signals"),
    )
    if not completion_signals and verify_signals:
        completion_signals = list(verify_signals)
    if not verify_signals and completion_signals:
        verify_signals = list(completion_signals)
    if not (completion_signals or action_signals or verify_signals):
        return None
    return {
        "mode": mode,
        "completion_signals": completion_signals,
        "action_signals": action_signals,
        "verify_signals": verify_signals,
    }


def _page_workflow_goal(
    *,
    intent_kind: str | None,
    intent_metadata: dict[str, Any] | None,
) -> str:
    metadata = dict(intent_metadata or {})
    metadata_goal = str(metadata.get("page_workflow_goal") or "").strip()
    if metadata_goal:
        return metadata_goal
    return _LEGACY_PAGE_WORKFLOW_GOALS.get(str(intent_kind or "").strip(), "")


def _page_workflow_completion_mode(
    workflow_goal: str,
    *,
    workflow_stage: str,
) -> str:
    stage_modes = _PAGE_WORKFLOW_STAGE_COMPLETION_MODES.get(workflow_goal, {})
    if workflow_stage and workflow_stage in stage_modes:
        return stage_modes[workflow_stage]
    if workflow_goal in _PAGE_WORKFLOW_ACTION_SIGNAL_NAMES:
        return "action_then_verify"
    return "verify_only"


def intent_completion_contract(
    family: str,
    *,
    intent_kind: str | None = None,
    allowed_tool_names: list[str],
    preferred_tool_names: list[str],
    intent_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered_tool_names = _ordered_unique_tool_names(
        list(preferred_tool_names or []),
        list(allowed_tool_names or []),
    )
    if family == "web_research":
        if "fetch_url" in allowed_tool_names:
            return {
                "mode": "any_of",
                "completion_signals": ["fetch_url"],
                "action_signals": [],
                "verify_signals": [],
            }
        if "web_search" in allowed_tool_names:
            return {
                "mode": "any_of",
                "completion_signals": ["web_search"],
                "action_signals": [],
                "verify_signals": [],
            }
    if family == "page_ops":
        page_intent_kind = str(intent_kind or "").strip()
        workflow_goal = _page_workflow_goal(
            intent_kind=page_intent_kind,
            intent_metadata=intent_metadata,
        )
        metadata_contract = _page_completion_contract_from_metadata(
            intent_metadata=intent_metadata,
            ordered_tool_names=ordered_tool_names,
        )
        if metadata_contract is not None:
            return metadata_contract
        workflow_stage = str(
            (intent_metadata or {}).get("page_workflow_stage") or ""
        ).strip()
        has_known_page_contract = (
            workflow_goal in _PAGE_WORKFLOW_COMPLETION_SIGNAL_NAMES
            or workflow_goal in _PAGE_WORKFLOW_STAGE_COMPLETION_SIGNAL_NAMES
        )
        verify_priority = _PAGE_WORKFLOW_STAGE_COMPLETION_SIGNAL_NAMES.get(
            workflow_goal,
            {},
        ).get(
            workflow_stage,
            _PAGE_WORKFLOW_COMPLETION_SIGNAL_NAMES.get(workflow_goal, ()),
        )
        verify_signals = [
            name for name in ordered_tool_names if name in set(verify_priority)
        ]
        action_priority = _PAGE_WORKFLOW_ACTION_SIGNAL_NAMES.get(
            workflow_goal,
            (),
        )
        action_signals = [
            name for name in ordered_tool_names if name in set(action_priority)
        ]
        completion_signals = (
            list(verify_signals)
            if has_known_page_contract
            else (verify_signals or list(ordered_tool_names))
        )
        return {
            "mode": _page_workflow_completion_mode(
                workflow_goal,
                workflow_stage=workflow_stage,
            ),
            "completion_signals": completion_signals,
            "action_signals": action_signals,
            "verify_signals": verify_signals,
        }
    return {
        "mode": "any_of",
        "completion_signals": list(allowed_tool_names or preferred_tool_names),
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
            intent_plan.append(IntentPlan(**raw_intent))
        except TypeError:
            continue
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
        "has_page_intent": bool(flags.has_page_intent),
        "has_knowledge_intent": bool(flags.has_knowledge_intent),
        "has_web_research_intent": bool(flags.has_web_research_intent),
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
    mode = str(contract.get("mode") or "any_of").strip()
    if family != "page_ops" or mode == "any_of":
        return _ordered_matching_tool_names(
            completion_signals,
            completed_tool_names,
        )

    if mode == "action_then_verify":
        action_matches = _ordered_matching_tool_names(
            list(contract.get("action_signals") or []),
            completed_tool_names,
        )
        verify_matches = _ordered_matching_tool_names(
            list(contract.get("verify_signals") or completion_signals),
            completed_tool_names,
        )
        if action_matches and verify_matches:
            return _ordered_unique_tool_names(action_matches, verify_matches)
        return []

    return _ordered_matching_tool_names(
        completion_signals,
        completed_tool_names,
    )


def _page_workflow_progress_status(
    *,
    workflow_phase: str,
    mode: str,
    action_matches: list[str],
    verify_matches: list[str],
    completion_matches: list[str],
) -> str:
    if completion_matches:
        return "completed"

    if workflow_phase == "discover":
        return "discover_pending"
    if workflow_phase == "navigate_or_open":
        return "verify_pending" if action_matches else "action_pending"
    if workflow_phase == "write":
        return "write_pending"
    if workflow_phase == "submit":
        return "submit_pending"
    if workflow_phase == "verify":
        return "verify_pending"
    if workflow_phase == "read":
        return "read_pending"
    if mode == "action_then_verify":
        return "verify_pending" if action_matches else "action_pending"
    if verify_matches:
        return "verify_pending"
    return "step_pending"


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
    workflow_stage = str((intent_metadata or {}).get("page_workflow_stage") or "").strip()
    workflow_phase = str((intent_metadata or {}).get("page_workflow_phase") or "").strip()
    workflow_goal = str((intent_metadata or {}).get("page_workflow_goal") or "").strip()
    mode = str(contract.get("mode") or "any_of").strip()
    continuation_required = not bool(completion_matches)
    status = (
        _page_workflow_progress_status(
            workflow_phase=workflow_phase,
            mode=mode,
            action_matches=action_matches,
            verify_matches=verify_matches,
            completion_matches=completion_matches,
        )
        if family == "page_ops"
        else ("completed" if completion_matches else "pending")
    )
    return {
        "mode": mode,
        "workflow_stage": workflow_stage,
        "workflow_phase": workflow_phase,
        "workflow_goal": workflow_goal,
        "completion_signals": completion_signals,
        "action_signals": action_signals,
        "verify_signals": verify_signals,
        "matched_completion_signals": completion_matches,
        "matched_action_signals": action_matches,
        "matched_verify_signals": verify_matches,
        "continuation_required": continuation_required,
        "status": status,
    }
