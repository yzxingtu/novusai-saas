"""Page-flow no-progress recovery helpers extracted from BaseEngine."""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha1
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
    "新建",
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


def _load_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not str(value or "").strip():
        return {}
    try:
        payload = json.loads(str(value or "").strip())
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _tool_call_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    function_block = tool_call.get("function")
    if not isinstance(function_block, dict):
        return {}
    raw_arguments = function_block.get("arguments")
    if isinstance(raw_arguments, dict):
        return dict(raw_arguments)
    return _load_json_object(raw_arguments)


def _tool_call(
    *,
    name: str,
    arguments: dict[str, Any] | None = None,
    reason: str,
) -> dict[str, Any]:
    serialized_arguments = json.dumps(
        arguments or {},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    digest = sha1(serialized_arguments.encode("utf-8")).hexdigest()[:8]
    safe_name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    safe_name = safe_name.strip("_") or "page_tool"
    return {
        "id": f"fc_page_recovery_{safe_name}_{digest}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments or {}, ensure_ascii=False, default=str),
        },
        "metadata": {
            "synthetic_page_workflow_tool_call": True,
            "reason": reason,
        },
    }


def _result_payloads(result: ToolResult) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    output_payload = _load_json_object(result.output)
    if output_payload:
        payloads.append(output_payload)
    if isinstance(result.summary_payload, dict):
        summary_payload = dict(result.summary_payload)
        payloads.append(summary_payload)
        data = summary_payload.get("data")
        if isinstance(data, dict):
            payloads.append(dict(data))
            form_session = data.get("form_session")
            if isinstance(form_session, dict):
                payloads.append(dict(form_session))
    return payloads


def _last_successful_result(tool_results: list[ToolResult]) -> ToolResult | None:
    for result in reversed(tool_results):
        if result.success:
            return result
    return None


def _active_form_state(
    *,
    page_context: dict[str, Any],
    tool_results: list[ToolResult],
) -> dict[str, Any]:
    for result in reversed(tool_results):
        for payload in _result_payloads(result):
            form_session = payload.get("form_session")
            if isinstance(form_session, dict):
                return dict(form_session)
            active_form_summary = payload.get("active_form_summary")
            if isinstance(active_form_summary, dict):
                state = dict(active_form_summary)
                active_form_session_id = str(
                    payload.get("active_form_session_id") or ""
                ).strip()
                if active_form_session_id and not str(
                    state.get("form_session_id") or ""
                ).strip():
                    state["form_session_id"] = active_form_session_id
                return state
            if (
                str(payload.get("form_session_id") or "").strip()
                or str(payload.get("active_form_session_id") or "").strip()
                or isinstance(payload.get("fields"), list)
                or isinstance(payload.get("remaining_required_fields"), list)
            ):
                return dict(payload)
    active_summary = page_context.get("active_form_summary")
    if isinstance(active_summary, dict):
        state = dict(active_summary)
        active_form_session_id = str(
            page_context.get("active_form_session_id") or ""
        ).strip()
        if active_form_session_id and not str(state.get("form_session_id") or "").strip():
            state["form_session_id"] = active_form_session_id
        return state
    active_id = str(page_context.get("active_form_session_id") or "").strip()
    return {"form_session_id": active_id} if active_id else {}


def _form_session_id_from_round(
    *,
    page_context: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
) -> str:
    state = _active_form_state(page_context=page_context, tool_results=tool_results)
    form_session_id = str(
        state.get("form_session_id") or state.get("active_form_session_id") or ""
    ).strip()
    if form_session_id:
        return form_session_id
    for tool_call in reversed(tool_calls):
        arguments = _tool_call_arguments(tool_call)
        form_session_id = str(arguments.get("form_session_id") or "").strip()
        if form_session_id:
            return form_session_id
    return ""


def _requested_name_value(user_text: str) -> str:
    normalized = str(user_text or "").strip()
    if not normalized:
        return ""
    markers = ("名称叫", "名字叫", "命名为", "name is", "named")
    for marker in markers:
        marker_index = normalized.lower().find(marker.lower())
        if marker_index < 0:
            continue
        value = normalized[marker_index + len(marker) :].strip(" ：:，,。.")
        value = value.split("，", 1)[0].split(",", 1)[0].split("。", 1)[0].strip()
        if value:
            return value[:120]
    return ""


def _iter_interactable_items(tool_results: list[ToolResult]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in reversed(tool_results):
        if not result.success or result.name not in {
            "ui_get_snapshot",
            "ui_list_interactables",
        }:
            continue
        for payload in _result_payloads(result):
            raw_items = payload.get("items")
            if result.name == "ui_get_snapshot" and not isinstance(raw_items, list):
                raw_items = payload.get("nodes")
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if isinstance(item, dict):
                    items.append(dict(item))
        if items:
            break
    return items


def _item_label(item: dict[str, Any]) -> str:
    return str(
        item.get("label")
        or item.get("summary")
        or item.get("title")
        or item.get("text")
        or item.get("content")
        or ""
    ).strip()


def _item_locator(item: dict[str, Any]) -> str:
    return str(item.get("locator") or item.get("target_locator") or "").strip()


def _find_create_surface_item(items: list[dict[str, Any]]) -> dict[str, Any]:
    create_terms = ("创建", "新增", "添加", "新建", "create", "add", "new")
    for item in items:
        haystack = f"{_item_label(item)} {_item_locator(item)}".lower()
        if any(term in haystack for term in create_terms) and not bool(
            item.get("disabled")
        ):
            return item
    return {}


def _form_is_submittable(form_state: dict[str, Any]) -> bool:
    if bool(form_state.get("can_submit")):
        return True
    remaining = form_state.get("remaining_required_fields")
    if isinstance(remaining, list) and not remaining:
        return True
    return str(form_state.get("stage") or "").strip() in {
        "ready_to_submit",
        "submitting",
    }


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


def build_page_deterministic_recovery_step(
    *,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    extract_last_user_text: Callable[[list[ChatMessage]], str],
    first_page_workflow_goal: Callable[..., str | None],
    tool_call_name: Callable[[dict[str, Any]], str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not tool_calls or not tool_results or not tools or not isinstance(
        input_variables,
        dict,
    ):
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
    if not round_tool_names:
        return [], {}

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
    if not workflow_goal:
        return [], {}

    workflow_plan = ToolRouter.page_intent_tool_plan(
        "page_workflow",
        user_text=user_text,
        input_variables=input_variables,
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": workflow_goal,
        },
    )
    workflow_goal = str(workflow_plan.workflow_goal or workflow_goal or "").strip()
    available_tool_names = {tool.name for tool in tools}
    available_ui_tools = set(
        page_context_available_ui_tools(
            page_context,
            available_tool_names=available_tool_names,
        )
    )
    last_result = _last_successful_result(tool_results)
    if last_result is None:
        return [], {}

    next_call: dict[str, Any] | None = None
    if (
        workflow_goal == "page_summary"
        and last_result.name == "ui_get_snapshot"
        and "ui_read_region" in available_ui_tools
    ):
        next_call = _tool_call(
            name="ui_read_region",
            arguments={
                "locator": "main",
                "ui_epoch": page_context.get("ui_epoch"),
            },
            reason="page_summary_main_region_after_snapshot",
        )
    elif workflow_goal == "form_write":
        form_state = _active_form_state(
            page_context=page_context,
            tool_results=tool_results,
        )
        form_session_id = _form_session_id_from_round(
            page_context=page_context,
            tool_calls=tool_calls,
            tool_results=tool_results,
        )
        requested_name = _requested_name_value(user_text)
        if (
            requested_name
            and form_session_id
            and last_result.name in {"ui_get_form_state", "ui_open_surface", "ui_click"}
            and "ui_fill_form" in available_ui_tools
        ):
            next_call = _tool_call(
                name="ui_fill_form",
                arguments={
                    "form_session_id": form_session_id,
                    "fields": {"name": requested_name},
                    "ui_epoch": page_context.get("ui_epoch"),
                },
                reason="page_form_fill_name_from_active_form",
            )
        elif (
            form_session_id
            and last_result.name in {"ui_fill_form", "ui_set_field"}
            and _form_is_submittable(form_state)
            and "ui_submit_form" in available_ui_tools
        ):
            next_call = _tool_call(
                name="ui_submit_form",
                arguments={
                    "form_session_id": form_session_id,
                    "confirm": True,
                    "ui_epoch": page_context.get("ui_epoch"),
                },
                reason="page_form_submit_after_fill",
            )
        elif (
            not form_session_id
            and last_result.name in {"ui_get_snapshot", "ui_list_interactables"}
            and {"ui_open_surface", "ui_click"} & available_ui_tools
        ):
            create_item = _find_create_surface_item(
                _iter_interactable_items(tool_results)
            )
            target_locator = _item_locator(create_item)
            if target_locator:
                tool_name = (
                    "ui_open_surface"
                    if "ui_open_surface" in available_ui_tools
                    else "ui_click"
                )
                next_call = _tool_call(
                    name=tool_name,
                    arguments={
                        "target_locator": target_locator,
                        "ui_epoch": page_context.get("ui_epoch"),
                    },
                    reason="page_form_open_create_surface_from_interactables",
                )

    if next_call is None:
        return [], {}

    synthetic_tool_name = str(
        ((next_call.get("function") or {}) if isinstance(next_call, dict) else {}).get(
            "name"
        )
        or ""
    ).strip()
    progress = _build_recovery_progress(
        recovery_reason="page_deterministic_next_step",
        preferred_tool_names=[synthetic_tool_name] if synthetic_tool_name else [],
        round_tool_names=round_tool_names,
        workflow_plan=workflow_plan,
    )
    diagnostics = {
        "reason": "page_deterministic_next_step",
        "intent_kind": "page_workflow",
        "synthetic_tool_names": [synthetic_tool_name] if synthetic_tool_name else [],
        "round_tool_names": round_tool_names,
        "workflow_stage": workflow_plan.workflow_stage,
        "workflow_phase": workflow_plan.workflow_phase,
        "workflow_goal": workflow_goal,
        "page_workflow_kind": "page_workflow",
        "page_workflow_stage": workflow_plan.workflow_stage,
        "page_workflow_phase": workflow_plan.workflow_phase,
        "page_workflow_goal": workflow_goal,
        "workflow_state": workflow_plan.workflow_state.to_dict(),
        "workflow_completion": workflow_plan.completion_contract.to_dict(),
        "page_workflow_state": workflow_plan.workflow_state.to_dict(),
        "page_workflow_completion": workflow_plan.completion_contract.to_dict(),
        "page_workflow_progress": progress,
    }
    return [next_call], diagnostics


def build_page_deterministic_recovery_step_default(
    *,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return build_page_deterministic_recovery_step(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        tools=tools,
        input_variables=input_variables,
        extract_last_user_text=_extract_last_user_text_impl,
        first_page_workflow_goal=_first_page_workflow_goal_impl,
        tool_call_name=_tool_call_name_impl,
    )
