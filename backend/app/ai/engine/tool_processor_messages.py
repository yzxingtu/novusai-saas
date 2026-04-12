from __future__ import annotations

import json
from typing import Any

from app.ai.text_semantics import is_confirmation_reply, is_rejection_reply
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _


def build_tool_message(result: ToolResult, tc_id: str) -> ChatMessage:
    """Build tool role message / 构建 tool 角色消息"""
    content = result.output if result.success else _("tool.error.prefix", error=result.error)
    return ChatMessage(role="tool", content=content, tool_call_id=tc_id)


def build_attachment_relay_message(result: ToolResult) -> ChatMessage | None:
    """Build a minimal internal attachment relay when tool output includes media. / 工具输出包含媒体时构建最小内部附件承载消息。"""
    if not result.success or not result.attachments:
        return None

    return ChatMessage(
        role="user",
        content="",
        attachments=result.attachments,
        internal_only=True,
    )


def annotate_tool_call(
    tool_call: dict[str, Any],
    *,
    duration_ms: int | None = None,
    pending_confirmation: dict[str, Any] | None = None,
    pending_consent: dict[str, Any] | None = None,
    result: ToolResult | None = None,
    skill_info: dict[str, str | None] | None = None,
) -> None:
    """Attach recoverable runtime metadata onto assistant tool_calls / 将可恢复的运行态元数据挂到 assistant.tool_calls。"""
    if skill_info:
        if skill_info.get("skill_name"):
            tool_call["skill_name"] = skill_info["skill_name"]
        if skill_info.get("package_name"):
            tool_call["package_name"] = skill_info["package_name"]

    if duration_ms is not None:
        tool_call["duration_ms"] = duration_ms

    if pending_confirmation:
        tool_call["pending_confirmation"] = pending_confirmation

    if pending_consent:
        tool_call["pending_consent"] = pending_consent

    if result:
        tool_call["success"] = result.success
        if result.display_name:
            tool_call["display_name"] = result.display_name
        if result.summary:
            tool_call["summary"] = result.summary
        if result.summary_payload:
            tool_call["summary_payload"] = result.summary_payload
        if result.result_link:
            tool_call["result_link"] = result.result_link
        if result.error_type:
            tool_call["error_type"] = result.error_type


def build_pending_confirmation_payload(
    parsed: dict[str, Any],
    func_name: str | None = None,
) -> dict[str, Any]:
    """Build recoverable pending confirmation payload / 构建可恢复的待确认信息。"""
    payload = {
        "action": parsed.get("action", ""),
        "table": parsed.get("table", ""),
        "preview": (parsed.get("preview") or parsed.get("diff") or parsed.get("record")),
    }
    normalized_name = str(func_name or "").strip()
    if normalized_name:
        payload["tool_name"] = normalized_name
    return payload


def build_pending_consent_payload(
    func_name: str,
    arguments: dict[str, Any],
    skill_info: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build recoverable pending consent payload / 构建可恢复的待授权信息。"""
    payload: dict[str, Any] = {
        "tool_name": func_name,
        "arguments": arguments,
    }
    if skill_info:
        if skill_info.get("skill_name"):
            payload["skill_name"] = skill_info["skill_name"]
        if skill_info.get("package_name"):
            payload["package_name"] = skill_info["package_name"]
    return payload


def build_assistant_tool_call_message(
    content: str,
    tool_calls: list[dict[str, Any]],
    reasoning_content: str | None = None,
) -> ChatMessage:
    """Build assistant message containing tool_calls / 构建包含 tool_calls 的 assistant 消息"""
    return ChatMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning_content,
    )


def check_confirmation_output(result: ToolResult) -> dict[str, Any] | None:
    """
    Check if tool output contains requires_confirmation (CRUD preview confirmation).
    检查工具输出是否包含 requires_confirmation（CRUD 预览确认）。

    Returns:
        Parsed confirmation data dict, or None / 解析后的确认数据 dict，或 None
    """
    if not (result.success and result.output):
        return None
    try:
        parsed = json.loads(result.output)
        if isinstance(parsed, dict) and parsed.get("requires_confirmation"):
            return parsed
    except (ValueError, TypeError):
        pass
    return None


def find_pending_confirmation(
    messages: list[ChatMessage],
) -> dict[str, Any] | None:
    """
    Search message history for pending tool call confirmation. / 搜索消息历史中待确认的工具调用。

    Searches backward, finds tool message with requires_confirmation,
    matches corresponding assistant tool_call, returns directly executable tool call info.
    从后往前搜索，找到 requires_confirmation 的 tool 消息后，
    匹配对应的 assistant tool_call。

    Returns:
        {"name", "arguments", "tool_call_id"} or None
    """
    pending_tc_id: str | None = None
    inject_confirmed = False
    for msg in reversed(messages):
        if msg.role == "tool" and msg.content:
            try:
                parsed = json.loads(msg.content)
                if isinstance(parsed, dict) and parsed.get("requires_confirmation"):
                    pending_tc_id = msg.tool_call_id
                    inject_confirmed = not bool(
                        parsed.get("consent_required")
                        or parsed.get("action") == "tool_consent"
                    )
                    break
            except (ValueError, TypeError):
                continue

    if not pending_tc_id:
        return None

    # Find corresponding assistant tool_call / 找到对应的 assistant tool_call
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("id") == pending_tc_id:
                    func = tc.get("function", {})
                    raw_args = func.get("arguments", "{}")
                    try:
                        arguments = (
                            json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        )
                    except json.JSONDecodeError:
                        arguments = {}
                    # Only mutation-preview injects confirmed=True; consent_mode=ask replays args / 仅变更预览注入 confirmed；询问模式原样重放参数
                    if inject_confirmed:
                        arguments["confirmed"] = True
                    return {
                        "name": func.get("name", ""),
                        "arguments": arguments,
                        "tool_call_id": pending_tc_id,
                    }
    return None


def is_confirmation_text(text: str) -> bool:
    """Check if text is a short confirmation reply / 检查是否为简短确认回复"""
    return is_confirmation_reply(text)


def is_rejection_text(text: str) -> bool:
    """Check if text is a short rejection reply / 检查是否为简短拒绝回复"""
    return is_rejection_reply(text)


def approved_pending_consent_tool_names(
    interaction_updates: list[dict[str, Any]] | None,
) -> set[str]:
    approved: set[str] = set()
    for update in interaction_updates or []:
        if str(update.get("kind") or "").strip() != "pending_consent":
            continue
        if bool(update.get("rejected")):
            continue
        tool_name = str(update.get("tool_name") or "").strip()
        if tool_name:
            approved.add(tool_name)
    return approved


def build_consent_reject_message(
    tc_id: str,
) -> ChatMessage:
    """Build tool message for consent rejection / 构建 consent 被拒绝的 tool 消息"""
    return ChatMessage(
        role="tool",
        content=_("tool.error.consent_rejected"),
        tool_call_id=tc_id,
    )


def build_consent_ask_message(
    tc_id: str,
    func_name: str,
    arguments: dict[str, Any],
) -> ChatMessage:
    """Build tool message for consent requiring user confirmation / 构建 consent 需要用户确认的 tool 消息"""
    payload = json.dumps(
        {
            "requires_confirmation": True,
            "consent_required": True,
            "action": "tool_consent",
            "tool_name": func_name,
            "arguments": arguments,
        },
        ensure_ascii=False,
    )
    return ChatMessage(role="tool", content=payload, tool_call_id=tc_id)
