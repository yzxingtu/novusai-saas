"""Page-flow no-progress recovery helpers extracted from BaseEngine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name as _tool_call_name_impl
from .tool_policy_helpers import first_page_intent_kind as _first_page_intent_kind_impl
from .tool_router import ToolRouter
from .turn_research_helpers import (
    extract_last_user_text as _extract_last_user_text_impl,
)


def _is_missing_active_form_result(result: ToolResult) -> bool:
    if result.success or result.name != "ui_get_form_state":
        return False
    if str(result.error_type or "").strip() == "form_session_not_found":
        return True
    lowered_error = str(result.error or "").strip().lower()
    return any(
        token in lowered_error
        for token in (
            "active form",
            "form session",
            "no form session",
            "未找到活动中的表单会话",
        )
    )


def _trim_recovery_tool_names(
    *,
    preferred_tool_names: list[str],
    repeated_snapshot: bool,
    only_snapshot_round: bool,
    navigation_action_no_progress: bool,
    missing_form_session_no_progress: bool,
) -> list[str]:
    trimmed = list(preferred_tool_names)
    if repeated_snapshot or only_snapshot_round or navigation_action_no_progress:
        without_snapshot = [name for name in trimmed if name != "ui_get_snapshot"]
        if without_snapshot:
            trimmed = without_snapshot
    if missing_form_session_no_progress:
        without_form_mutation = [
            name
            for name in trimmed
            if name not in {"ui_fill_form", "ui_set_field", "ui_submit_form"}
        ]
        if without_form_mutation:
            trimmed = without_form_mutation
    return trimmed


def _recovery_progress_status(
    *,
    workflow_plan: Any,
) -> str:
    workflow_phase = str(workflow_plan.workflow_phase or "").strip()
    if workflow_phase == "discover":
        return "discover_pending"
    if workflow_phase == "navigate_or_open":
        return "action_pending"
    if workflow_phase == "write":
        return "write_pending"
    if workflow_phase == "submit":
        return "submit_pending"
    if workflow_phase == "verify":
        return "verify_pending"
    if workflow_phase == "read":
        return "read_pending"
    return "step_pending"


def _build_recovery_progress(
    *,
    recovery_reason: str,
    preferred_tool_names: list[str],
    round_tool_names: list[str],
    workflow_plan: Any,
) -> dict[str, Any]:
    completion = workflow_plan.completion_contract
    return {
        "mode": str(completion.mode or "").strip() or "verify_only",
        "workflow_stage": workflow_plan.workflow_stage,
        "workflow_phase": workflow_plan.workflow_phase,
        "workflow_goal": workflow_plan.workflow_goal,
        "completion_signals": list(completion.completion_signals or []),
        "action_signals": list(completion.action_signals or []),
        "verify_signals": list(completion.verify_signals or []),
        "matched_completion_signals": [],
        "matched_action_signals": [],
        "matched_verify_signals": [],
        "continuation_required": True,
        "status": _recovery_progress_status(workflow_plan=workflow_plan),
        "recovery_reason": recovery_reason,
        "preferred_tool_names": list(preferred_tool_names),
        "round_tool_names": list(round_tool_names),
    }


def build_page_no_progress_recovery(
    *,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    extract_last_user_text: Callable[[list[ChatMessage]], str],
    first_page_intent_kind: Callable[..., str | None],
    tool_call_name: Callable[[dict[str, Any]], str],
    render_contract: Callable[..., str] | None = None,
) -> tuple[str | None, list[str], dict[str, Any]]:
    _ = render_contract
    if not tool_calls or not tools or not isinstance(input_variables, dict):
        return None, [], {}

    from app.ai.tools.semantic_defaults import (
        page_context_available_ui_tools,
        page_context_payload,
    )

    page_context = page_context_payload(input_variables)
    if not isinstance(page_context, dict):
        return None, [], {}

    user_text = extract_last_user_text(messages)
    page_intent_kind = first_page_intent_kind(
        user_text=user_text,
        tools=tools,
        input_variables=input_variables,
    )
    if page_intent_kind in {None, "page_summary"}:
        return None, [], {}

    round_tool_names = [
        tool_call_name(tool_call)
        for tool_call in tool_calls
        if tool_call_name(tool_call)
    ]
    if not round_tool_names:
        return None, [], {}

    snapshot_calls = [
        result for result in tool_results if result.name == "ui_get_snapshot"
    ]
    repeated_snapshot = len(snapshot_calls) > 1
    only_snapshot_round = set(round_tool_names) == {"ui_get_snapshot"}
    failed_page_navigation_action = any(
        not result.success and result.name in {"ui_click", "ui_open_surface"}
        for result in tool_results
    )
    navigation_action_no_progress = (
        page_intent_kind == "page_navigation" and failed_page_navigation_action
    )
    missing_form_session_no_progress = page_intent_kind == "page_form_write" and any(
        _is_missing_active_form_result(result) for result in tool_results
    )
    if (
        not repeated_snapshot
        and not only_snapshot_round
        and not navigation_action_no_progress
        and not missing_form_session_no_progress
    ):
        return None, [], {}

    available_tool_names = {tool.name for tool in tools}
    available_ui_tools = page_context_available_ui_tools(
        page_context, available_tool_names=available_tool_names
    )
    workflow_plan = ToolRouter.page_intent_tool_plan(
        page_intent_kind,
        input_variables=input_variables,
    )
    recovery_tool_names = list(workflow_plan.preferred_names)
    if repeated_snapshot or only_snapshot_round or navigation_action_no_progress:
        recovery_tool_names = list(workflow_plan.allowed_names)
    if (
        page_intent_kind == "page_form_write"
        and workflow_plan.workflow_state.has_active_form
    ):
        recovery_tool_names = [
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ]
    if (
        page_intent_kind == "page_row_detail"
        and workflow_plan.workflow_goal == "row_detail"
        and workflow_plan.workflow_phase == "read"
    ):
        recovery_tool_names = [
            "ui_read_region",
            "ui_read_table",
            "ui_get_snapshot",
        ]
    preferred_tool_names = [
        name for name in recovery_tool_names if name in available_ui_tools
    ]
    preferred_tool_names = _trim_recovery_tool_names(
        preferred_tool_names=preferred_tool_names,
        repeated_snapshot=repeated_snapshot,
        only_snapshot_round=only_snapshot_round,
        navigation_action_no_progress=navigation_action_no_progress,
        missing_form_session_no_progress=missing_form_session_no_progress,
    )
    if not preferred_tool_names:
        return None, [], {}

    if navigation_action_no_progress:
        recovery_reason = "page_navigation_failed_no_progress"
    elif missing_form_session_no_progress:
        recovery_reason = "page_form_session_missing"
    else:
        recovery_reason = (
            "repeated_ui_get_snapshot"
            if repeated_snapshot
            else "page_snapshot_only_round"
        )
    progress = _build_recovery_progress(
        recovery_reason=recovery_reason,
        preferred_tool_names=preferred_tool_names,
        round_tool_names=round_tool_names,
        workflow_plan=workflow_plan,
    )
    workflow_snapshot = {
        "intent_kind": page_intent_kind,
        "stage": workflow_plan.workflow_stage,
        "phase": workflow_plan.workflow_phase,
        "goal": workflow_plan.workflow_goal,
        "state": workflow_plan.workflow_state.to_dict(),
        "completion": workflow_plan.completion_contract.to_dict(),
        "progress": dict(progress),
        "allowed_tool_names": list(preferred_tool_names),
        "preferred_tool_names": list(preferred_tool_names),
    }
    return (
        None,
        preferred_tool_names,
        {
            "reason": recovery_reason,
            "intent_kind": page_intent_kind,
            "preferred_tool_names": preferred_tool_names,
            "round_tool_names": round_tool_names,
            "workflow_stage": workflow_plan.workflow_stage,
            "workflow_phase": workflow_plan.workflow_phase,
            "workflow_goal": workflow_plan.workflow_goal,
            "workflow_state": workflow_plan.workflow_state.to_dict(),
            "workflow_completion": workflow_plan.completion_contract.to_dict(),
            "page_workflow_progress": progress,
            "page_workflow": workflow_snapshot,
        },
    )


def build_page_no_progress_recovery_default(
    *,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> tuple[str | None, list[str], dict[str, Any]]:
    return build_page_no_progress_recovery(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        tools=tools,
        input_variables=input_variables,
        extract_last_user_text=_extract_last_user_text_impl,
        first_page_intent_kind=_first_page_intent_kind_impl,
        tool_call_name=_tool_call_name_impl,
    )
