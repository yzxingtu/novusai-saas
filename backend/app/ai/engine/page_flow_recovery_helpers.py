"""Page-flow no-progress recovery helpers extracted from BaseEngine."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.ai.navigation_semantics import has_navigation_intent
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name as _tool_call_name_impl
from .page_workflow_state_machine import (
    PageWorkflowStateMachine,
)
from .tool_policy_page_helpers import (
    first_page_workflow_goal as _first_page_workflow_goal_impl,
)
from .tool_router import ToolRouter
from .turn_research_helpers import (
    extract_last_user_text as _extract_last_user_text_impl,
)

_RECOVERY_PAGINATION_TERMS = (
    "下一页",
    "上一页",
    "上一屏",
    "下一屏",
    "翻页",
    "翻到",
    "分页",
    "page ",
    "next page",
    "previous page",
    "prev page",
)
_RECOVERY_SEARCH_TERMS = (
    "搜索",
    "查找",
    "筛选",
    "过滤",
    "keyword",
    "keywords",
    "filter",
    "search",
)
_RECOVERY_FORM_READ_TERMS = (
    "表单状态",
    "读取表单",
    "查看表单",
    "读一下表单",
    "表单有哪些字段",
    "form state",
    "read form",
)
_RECOVERY_FORM_WRITE_TERMS = (
    "填写",
    "提交",
    "保存",
    "创建",
    "新增",
    "添加",
    "绑定",
    "编辑",
    "修改",
    "更新",
    "fill",
    "submit",
    "save",
    "create",
    "add",
    "bind",
    "edit",
    "update",
)
_RECOVERY_ROW_DETAIL_TERMS = (
    "详情",
    "明细",
    "详细",
    "记录详情",
    "详情页",
    "detail",
)
_RECOVERY_RECORD_POINTER_TERMS = (
    "这条记录",
    "当前记录",
    "这一行",
    "这行",
    "record",
    "row",
)
_RECOVERY_NAVIGATION_TERMS = (
    "打开",
    "进入",
    "跳转",
    "切到",
    "前往",
    "打开到",
    "click",
    "open",
    "go to",
    "navigate",
    "switch to",
)
_RECOVERY_NAVIGATION_TARGET_TERMS = (
    "页面",
    "列表",
    "界面",
    "面板",
    "页",
    "page",
    "list",
    "panel",
    "drawer",
    "弹窗",
)
_RECOVERY_SCREENSHOT_TERMS = (
    "截图",
    "截屏",
    "screenshot",
)
_RECOVERY_TABLE_SUMMARY_STRONG_TERMS = (
    "表格",
    "table",
    "前5条",
    "前五条",
    "标题",
    "时间",
    "columns",
    "rows",
)


def _normalized_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases if phrase)


def _looks_like_table_summary_request(user_text: str) -> bool:
    return _contains_any(user_text, _RECOVERY_TABLE_SUMMARY_STRONG_TERMS)


def _matches_pagination_request(user_text: str) -> bool:
    return _contains_any(user_text, _RECOVERY_PAGINATION_TERMS)


def _matches_search_request(user_text: str) -> bool:
    return _contains_any(user_text, _RECOVERY_SEARCH_TERMS)


def _matches_form_read_request(user_text: str) -> bool:
    if _contains_any(user_text, _RECOVERY_FORM_READ_TERMS):
        return True
    return "表单" in user_text and any(
        token in user_text for token in ("状态", "字段", "读取", "read")
    )


def _matches_form_write_request(user_text: str) -> bool:
    return _contains_any(user_text, _RECOVERY_FORM_WRITE_TERMS)


def _matches_row_detail_request(user_text: str) -> bool:
    if _contains_any(user_text, _RECOVERY_ROW_DETAIL_TERMS):
        return True
    return _contains_any(user_text, _RECOVERY_RECORD_POINTER_TERMS) and any(
        token in user_text for token in ("查看", "看", "read")
    )


def _matches_navigation_request(
    *,
    user_text: str,
    page_context: dict[str, Any],
) -> bool:
    if has_navigation_intent(user_text, page_context):
        return True
    return _contains_any(user_text, _RECOVERY_NAVIGATION_TERMS) and _contains_any(
        user_text,
        _RECOVERY_NAVIGATION_TARGET_TERMS,
    )


def _recovery_workflow_goal(
    *,
    user_text: str,
    page_context: dict[str, Any],
    workflow_state: Any,
    round_tool_names: list[str],
    tool_results: list[ToolResult],
) -> str:
    normalized = _normalized_text(user_text)
    if not normalized:
        return ""

    if _looks_like_table_summary_request(normalized):
        return "table_summary"
    if _contains_any(normalized, _RECOVERY_SCREENSHOT_TERMS):
        return "page_screenshot"
    if _matches_pagination_request(normalized):
        return "pagination"
    if _matches_search_request(normalized):
        return "search"

    missing_form_session = any(
        _is_missing_active_form_result(result) for result in tool_results
    )
    if workflow_state.has_active_form:
        if _matches_form_read_request(normalized):
            return "form_read"
        if _matches_form_write_request(normalized):
            return "form_write"

    if missing_form_session and (
        _matches_form_write_request(normalized)
        or any(name == "ui_get_form_state" for name in round_tool_names)
    ):
        return "form_write"

    if _matches_row_detail_request(normalized):
        return "row_detail"
    if _matches_navigation_request(user_text=normalized, page_context=page_context):
        return "navigation"
    if _matches_form_read_request(normalized):
        return "form_read"
    if _matches_form_write_request(normalized):
        return "form_write"
    return ""


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


def _snapshot_payload(result: ToolResult) -> dict[str, Any]:
    if not result.success or result.name != "ui_get_snapshot":
        return {}
    try:
        payload = json.loads(str(result.output or "").strip() or "{}")
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _snapshot_result_indicates_navigation_progress(
    *,
    result: ToolResult,
    page_context: dict[str, Any],
) -> bool:
    payload = _snapshot_payload(result)
    if not payload:
        return False
    if str(payload.get("active_form_session_id") or "").strip():
        return True
    if isinstance(payload.get("active_form_summary"), dict):
        return True

    current_active_surface_id = str(page_context.get("active_surface_id") or "").strip()
    snapshot_active_surface_id = str(payload.get("active_surface_id") or "").strip()
    if (
        current_active_surface_id
        and snapshot_active_surface_id
        and snapshot_active_surface_id != current_active_surface_id
    ):
        return True

    current_surface_stack = (
        list(page_context.get("surface_stack") or [])
        if isinstance(page_context.get("surface_stack"), list)
        else []
    )
    snapshot_surface_stack = (
        list(payload.get("surface_stack") or [])
        if isinstance(payload.get("surface_stack"), list)
        else []
    )
    if len(snapshot_surface_stack) > len(current_surface_stack):
        return True
    return any(
        str((surface or {}).get("kind") or "").strip() not in {"", "page"}
        for surface in snapshot_surface_stack
        if isinstance(surface, dict)
    )


def _trim_recovery_tool_names(
    *,
    preferred_tool_names: list[str],
    repeated_snapshot: bool,
    only_snapshot_round: bool,
    only_discovery_round: bool,
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
            if name
            not in {
                "ui_fill_form",
                "ui_set_field",
                "ui_submit_form",
                "ui_get_form_state",
            }
        ]
        if without_form_mutation:
            trimmed = without_form_mutation
    if only_discovery_round:
        without_discovery = [
            name for name in trimmed if name != "ui_list_interactables"
        ]
        if without_discovery:
            trimmed = without_discovery
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
    first_page_workflow_goal: Callable[..., str | None],
    tool_call_name: Callable[[dict[str, Any]], str],
) -> tuple[list[str], dict[str, Any]]:
    if not tool_calls or not tools or not isinstance(input_variables, dict):
        return [], {}

    from app.ai.tools.semantic_defaults import (
        page_context_available_ui_tools,
        page_context_payload,
    )

    page_context = page_context_payload(input_variables)
    if not isinstance(page_context, dict):
        return [], {}

    user_text = extract_last_user_text(messages)
    workflow_state = PageWorkflowStateMachine.resolve_state(
        input_variables=input_variables
    )
    round_tool_names = [
        tool_call_name(tool_call)
        for tool_call in tool_calls
        if tool_call_name(tool_call)
    ]
    workflow_goal = str(
        first_page_workflow_goal(
            user_text=user_text,
            tools=tools,
            input_variables=input_variables,
        )
        or ""
    ).strip()
    recovery_goal = _recovery_workflow_goal(
        user_text=user_text,
        page_context=page_context,
        workflow_state=workflow_state,
        round_tool_names=round_tool_names,
        tool_results=tool_results,
    )
    if recovery_goal and (
        not workflow_goal
        or workflow_goal == "page_summary"
        or (workflow_goal == "form_read" and recovery_goal == "form_write")
    ):
        workflow_goal = recovery_goal
    if not workflow_goal or workflow_goal == "page_summary":
        return [], {}

    plan_metadata = {
        "page_workflow_kind": "page_workflow",
        "page_workflow_goal": workflow_goal,
    }

    workflow_plan = ToolRouter.page_intent_tool_plan(
        "page_workflow",
        user_text=user_text,
        input_variables=input_variables,
        intent_metadata=plan_metadata,
    )
    workflow_goal = str(workflow_plan.workflow_goal or workflow_goal or "").strip()
    if not workflow_goal:
        return [], {}

    if not round_tool_names:
        return [], {}

    snapshot_calls = [
        result for result in tool_results if result.name == "ui_get_snapshot"
    ]
    repeated_snapshot = len(snapshot_calls) > 1
    only_snapshot_round = set(round_tool_names) == {"ui_get_snapshot"}
    only_discovery_round = set(round_tool_names) == {"ui_list_interactables"}
    failed_page_navigation_action = any(
        not result.success and result.name in {"ui_click", "ui_open_surface"}
        for result in tool_results
    )
    navigation_action_no_progress = (
        workflow_goal == "navigation" and failed_page_navigation_action
    )
    snapshot_verified_navigation_progress = (
        workflow_goal in {"navigation", "form_write"}
        and only_snapshot_round
        and any(
            _snapshot_result_indicates_navigation_progress(
                result=result,
                page_context=page_context,
            )
            for result in snapshot_calls
        )
    )
    missing_form_session_no_progress = workflow_goal == "form_write" and any(
        _is_missing_active_form_result(result) for result in tool_results
    )
    if snapshot_verified_navigation_progress:
        return [], {}
    if (
        not repeated_snapshot
        and not only_snapshot_round
        and not only_discovery_round
        and not navigation_action_no_progress
        and not missing_form_session_no_progress
    ):
        return [], {}

    available_tool_names = {tool.name for tool in tools}
    available_ui_tools = page_context_available_ui_tools(
        page_context, available_tool_names=available_tool_names
    )
    recovery_tool_names = list(workflow_plan.preferred_names)
    if repeated_snapshot or only_snapshot_round or navigation_action_no_progress:
        recovery_tool_names = list(workflow_plan.allowed_names)
    elif only_discovery_round:
        recovery_tool_names = list(
            workflow_plan.preferred_names or workflow_plan.allowed_names
        )
    if workflow_goal == "form_write" and workflow_plan.workflow_state.has_active_form:
        recovery_tool_names = [
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ]
    if workflow_goal == "search":
        recovery_tool_names = [
            "ui_click",
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
            "ui_read_table",
            "ui_read_region",
            "ui_list_interactables",
        ]
    if workflow_goal == "row_detail" and workflow_plan.workflow_phase == "read":
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
        only_discovery_round=only_discovery_round,
        navigation_action_no_progress=navigation_action_no_progress,
        missing_form_session_no_progress=missing_form_session_no_progress,
    )
    if not preferred_tool_names:
        return [], {}

    if navigation_action_no_progress:
        recovery_reason = "page_navigation_failed_no_progress"
    elif missing_form_session_no_progress:
        recovery_reason = "page_form_session_missing"
    elif only_discovery_round:
        recovery_reason = "page_discovery_only_round"
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
    workflow_kind = str(workflow_plan.workflow_kind or "page_workflow").strip() or (
        "page_workflow"
    )
    workflow_snapshot = {
        "intent_kind": workflow_kind,
        "stage": workflow_plan.workflow_stage,
        "phase": workflow_plan.workflow_phase,
        "goal": workflow_plan.workflow_goal,
        "state": workflow_plan.workflow_state.to_dict(),
        "completion": workflow_plan.completion_contract.to_dict(),
        "progress": dict(progress),
        "allowed_tool_names": list(preferred_tool_names),
        "preferred_tool_names": list(preferred_tool_names),
    }
    diagnostics = {
        "reason": recovery_reason,
        "intent_kind": workflow_kind,
        "preferred_tool_names": preferred_tool_names,
        "round_tool_names": round_tool_names,
        "workflow_stage": workflow_plan.workflow_stage,
        "workflow_phase": workflow_plan.workflow_phase,
        "workflow_goal": workflow_plan.workflow_goal,
        "page_workflow_kind": workflow_kind,
        "page_workflow_stage": workflow_plan.workflow_stage,
        "page_workflow_phase": workflow_plan.workflow_phase,
        "page_workflow_goal": workflow_plan.workflow_goal,
        "workflow_state": workflow_plan.workflow_state.to_dict(),
        "workflow_completion": workflow_plan.completion_contract.to_dict(),
        "page_workflow_state": workflow_plan.workflow_state.to_dict(),
        "page_workflow_completion": workflow_plan.completion_contract.to_dict(),
        "page_workflow_progress": progress,
        "page_workflow": workflow_snapshot,
    }
    return preferred_tool_names, diagnostics


def build_page_no_progress_recovery_default(
    *,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    return build_page_no_progress_recovery(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        tools=tools,
        input_variables=input_variables,
        extract_last_user_text=_extract_last_user_text_impl,
        first_page_workflow_goal=_first_page_workflow_goal_impl,
        tool_call_name=_tool_call_name_impl,
    )
