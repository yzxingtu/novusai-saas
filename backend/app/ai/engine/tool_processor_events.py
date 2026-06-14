from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult
from app.core.i18n import _


def build_tool_start_event(
    func_name: str,
    arguments: dict[str, Any],
    skill_info: dict[str, str | None] | None = None,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    """Build tool_start SSE event / 构建 tool_start SSE 事件"""
    event: dict[str, Any] = {
        "event": "tool_start",
        "name": func_name,
        "arguments": arguments,
    }
    if tool_call_id:
        event["id"] = tool_call_id
    if skill_info:
        event.update(skill_info)
    return event


def build_tool_call_event(
    result: ToolResult,
    duration_ms: int,
    skill_info: dict[str, str | None] | None = None,
    name_override: str | None = None,
) -> dict[str, Any]:
    """
    Build tool_call SSE event / 构建 tool_call SSE 事件
    """
    event: dict[str, Any] = {
        "event": "tool_call",
        "name": name_override or result.name,
        "success": result.success,
        "duration_ms": duration_ms,
    }
    if result.tool_call_id:
        event["id"] = result.tool_call_id
    if skill_info:
        event.update(skill_info)

    if result.display_name:
        event["display_name"] = result.display_name
    if result.summary:
        event["summary"] = result.summary
    if result.result_link:
        event["result_link"] = result.result_link
    if result.summary_payload:
        event["summary_payload"] = result.summary_payload

    if result.success and result.output:
        if '"__crud_form_fill__"' in result.output:
            event["output"] = result.output
        else:
            truncated = result.output[:500]
            if len(result.output) > 500:
                truncated += "..."
            event["output"] = truncated
    elif not result.success and result.error:
        event["error"] = result.error[:300]
        if result.error_type:
            event["error_type"] = result.error_type

    return event


def build_confirmation_event(
    parsed: dict[str, Any],
    func_name: str | None = None,
) -> dict[str, Any]:
    """Build confirmation_request SSE event / 构建 confirmation_request SSE 事件"""
    event: dict[str, Any] = {
        "event": "confirmation_request",
        "action": parsed.get("action", ""),
        "table": parsed.get("table", ""),
        "preview": (
            parsed.get("preview") or parsed.get("diff") or parsed.get("record")
        ),
    }
    normalized_name = str(func_name or "").strip()
    if normalized_name:
        event["tool_name"] = normalized_name
    # File-generation confirmation (e.g. plugin codegen) / 文件生成类确认（如插件 codegen）
    if parsed.get("files"):
        event["files"] = parsed["files"]
        event["message"] = parsed.get("message", "")
        event["total_new"] = parsed.get("total_new", 0)
        event["total_conflict"] = parsed.get("total_conflict", 0)
    # Pass through approval_presentation for frontend card rendering
    # 透传 approval_presentation 避免卡片先显示原始数据再切换（闪烁）
    approval = parsed.get("approval_presentation") or parsed.get(
        "approvalPresentation"
    )
    if approval and isinstance(approval, dict):
        event["approval_presentation"] = approval
    return event


def build_consent_reject_event(
    func_name: str,
    skill_info: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build consent rejection tool_call SSE event / 构建 consent 拒绝的 tool_call SSE 事件"""
    event: dict[str, Any] = {
        "event": "tool_call",
        "name": func_name,
        "success": False,
        "duration_ms": 0,
        "error": _("tool.error.consent_rejected"),
    }
    if skill_info:
        event.update(skill_info)
    return event


def build_consent_ask_event(
    func_name: str,
    arguments: dict[str, Any],
    skill_info: dict[str, str | None] | None = None,
    interaction_mode_effective: str | None = None,
) -> dict[str, Any]:
    """Build consent ask SSE event / 构建 consent 询问的 SSE 事件"""
    event: dict[str, Any] = {
        "event": "tool_consent_request",
        "name": func_name,
        "arguments": arguments,
    }
    if interaction_mode_effective:
        event["interaction_mode_effective"] = interaction_mode_effective
    if skill_info:
        event.update(skill_info)
    return event
