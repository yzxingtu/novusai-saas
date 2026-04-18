"""Page-flow no-progress recovery helpers extracted from BaseEngine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name as _tool_call_name_impl
from .tool_router import ToolRouter
from .tool_policy_helpers import first_page_intent_kind as _first_page_intent_kind_impl
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
    render_contract: Callable[..., str] = render_prompt_contract,
) -> tuple[str | None, list[str], dict[str, Any]]:
    if not tool_calls or not tools or not isinstance(input_variables, dict):
        return None, [], {}

    from app.ai.tools.semantic_defaults import (
        page_context_available_ui_tools,
        page_context_has_active_form,
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
        tool_call_name(tool_call) for tool_call in tool_calls if tool_call_name(tool_call)
    ]
    if not round_tool_names:
        return None, [], {}

    snapshot_calls = [result for result in tool_results if result.name == "ui_get_snapshot"]
    repeated_snapshot = len(snapshot_calls) > 1
    only_snapshot_round = set(round_tool_names) == {"ui_get_snapshot"}
    failed_page_navigation_action = any(
        not result.success and result.name in {"ui_click", "ui_open_surface"}
        for result in tool_results
    )
    navigation_action_no_progress = (
        page_intent_kind == "page_navigation" and failed_page_navigation_action
    )
    missing_form_session_no_progress = (
        page_intent_kind == "page_form_write"
        and any(_is_missing_active_form_result(result) for result in tool_results)
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
    recovery_preferences = {
        "page_navigation": [
            "ui_list_interactables",
            "ui_click",
            "ui_open_surface",
            "ui_get_snapshot",
        ],
        "page_search": [
            "ui_read_region",
            "ui_list_interactables",
            "ui_click",
        ],
        "page_pagination": [
            "ui_read_table",
            "ui_click",
            "ui_list_interactables",
        ],
        "page_row_detail": [
            "ui_read_region",
            "ui_read_table",
            "ui_get_snapshot",
        ],
        "page_form_read": [
            "ui_get_form_state",
            "ui_read_region",
            "ui_get_snapshot",
        ],
        "page_screenshot": [
            "ui_get_snapshot",
        ],
    }
    if page_intent_kind == "page_form_read" and not page_context_has_active_form(page_context):
        recovery_preferences["page_form_read"] = [
            "ui_list_interactables",
            "ui_click",
            "ui_open_surface",
            "ui_get_form_state",
            "ui_read_region",
            "ui_get_snapshot",
        ]
    if page_intent_kind == "page_form_write":
        if page_context_has_active_form(page_context):
            recovery_preferences["page_form_write"] = [
                "ui_fill_form",
                "ui_set_field",
                "ui_submit_form",
            ]
        else:
            recovery_preferences["page_form_write"] = list(
                ToolRouter.page_intent_tool_preferences(
                    "page_form_write",
                    input_variables=input_variables,
                )[1]
            )
    preferred_tool_names = [
        name
        for name in recovery_preferences.get(page_intent_kind, [])
        if name in available_ui_tools
    ]
    if not preferred_tool_names:
        return None, [], {}

    page_key = str(page_context.get("page_key") or "").strip()
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
    hint = render_contract("page_flow_recovery")
    return (
        hint,
        preferred_tool_names,
        {
            "reason": recovery_reason,
            "intent_kind": page_intent_kind,
            "current_page_key": page_key,
            "preferred_tool_names": preferred_tool_names,
            "round_tool_names": round_tool_names,
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
