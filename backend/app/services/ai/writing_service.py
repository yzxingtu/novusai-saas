"""
Rich-text AI message template service / 富文本 AI 消息模板服务。

This module intentionally does not expose an independent writing runtime.
Rich-text editor actions are normalized into a single AgentChat user message;
the caller must resolve the `system.ai_writing` assignment through the existing
agent-assignment API and then send the message through the global AgentChat /
conversation route.
/ 本模块不再暴露独立 AI 写作运行时。富文本编辑器动作会被规整成一条
AgentChat 用户消息；调用方必须通过既有智能体分配 API 解析 `system.ai_writing`
绑定，再通过全局 AgentChat/会话路由发送该消息。
"""

from __future__ import annotations

from typing import Any

from app.ai.skills.rich_text_actions import (
    MAX_AFTER_TEXT,
    MAX_BEFORE_TEXT,
    MAX_INSTRUCTION,
    MAX_SELECTED_TEXT,
    RICH_TEXT_AI_FEATURE_CODE,
    VALID_RICH_TEXT_FEATURES,
    RichTextAIActionError,
    build_default_rich_text_skill_package_definition,
    build_rich_text_action_catalog,
    build_rich_text_ai_messages,
    build_rich_text_ai_request_message,
    get_rich_text_action_template,
    normalize_rich_text_action_key,
)
from app.core.i18n import _
from app.exceptions import ValidationException

FEATURE_CODE = RICH_TEXT_AI_FEATURE_CODE
VALID_FEATURES = VALID_RICH_TEXT_FEATURES


def normalize_writing_action(feature: str) -> str:
    """Strictly normalize a rich-text action; unknown actions are validation errors."""
    try:
        return normalize_rich_text_action_key(feature, default=None)
    except RichTextAIActionError as exc:
        message = _("ai_writing.invalid_feature").format(feature=feature)
        raise ValidationException(
            message=message,
            errors=[{"loc": ["action"], "msg": message, "type": "value_error"}],
        ) from exc


def is_valid_writing_action(feature: str) -> bool:
    """Return whether a feature/action name is accepted by the writing service."""
    try:
        normalize_writing_action(feature)
    except ValidationException:
        return False
    return True


def _raise_action_validation(message_key: str, *, action: str, loc: str) -> None:
    message = _(message_key).format(action=action)
    raise ValidationException(
        message=message,
        errors=[{"loc": [loc], "msg": message, "type": "value_error"}],
    )


def _validate_action_input(action_key: str, body: dict[str, Any]) -> None:
    """Validate explicit editor payload without accepting page/DOM context."""
    template = get_rich_text_action_template(action_key)
    selected_text = str(body.get("selected_text") or "").strip()
    before_text = str(body.get("before_text") or "").strip()
    after_text = str(body.get("after_text") or "").strip()
    instruction = str(body.get("instruction") or "").strip()
    format_instruction = str(body.get("format_instruction") or "").strip()

    if template.selection_policy == "selection_required" and not selected_text:
        _raise_action_validation(
            "ai_writing.selection_required",
            action=action_key,
            loc="selected_text",
        )

    instruction_ok = bool(instruction or format_instruction)
    if template.requires_instruction and action_key != "format" and not instruction_ok:
        _raise_action_validation(
            "ai_writing.instruction_required",
            action=action_key,
            loc="instruction",
        )

    if action_key == "insert" and not (
        instruction_ok or selected_text or before_text or after_text
    ):
        _raise_action_validation(
            "ai_writing.input_required",
            action=action_key,
            loc="instruction",
        )


def build_ai_messages(
    feature: str,
    *,
    selected_text: str = "",
    before_text: str = "",
    after_text: str = "",
    context_title: str = "",
    instruction: str = "",
    target_lang: str = "English",
    format_instruction: str = "",
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """构建富文本 AI prompt 消息 / Build rich-text AI prompt messages."""
    action_key = normalize_writing_action(feature)
    _validate_action_input(
        action_key,
        {
            "selected_text": selected_text,
            "before_text": before_text,
            "after_text": after_text,
            "instruction": instruction,
            "format_instruction": format_instruction,
        },
    )
    return build_rich_text_ai_messages(
        action_key,
        selected_text=selected_text,
        before_text=before_text,
        after_text=after_text,
        context_title=context_title,
        instruction=instruction,
        target_lang=target_lang,
        format_instruction=format_instruction,
        chat_history=chat_history,
    )


def build_rich_text_agent_chat_message(feature: str, body: dict[str, Any]) -> str:
    """构建可发送到全局 AgentChat 的富文本操作消息。

    EN: Build the rich-text operation message that should be sent through the
    global AgentChat conversation route. This helper does not resolve an agent,
    open an SSE stream, or write AI action logs; those responsibilities stay in
    the normal AgentChat runtime.
    """
    payload = dict(body or {})
    action_key = normalize_writing_action(feature)
    _validate_action_input(action_key, payload)
    format_instruction = str(payload.get("format_instruction") or "")
    messages = build_ai_messages(
        action_key,
        selected_text=payload.get("selected_text", ""),
        before_text=payload.get("before_text", ""),
        after_text=payload.get("after_text", ""),
        context_title=payload.get("context_title")
        or payload.get("document_title")
        or "",
        instruction=payload.get("instruction", ""),
        target_lang=payload.get("target_lang", "English"),
        format_instruction=format_instruction,
        chat_history=payload.get("history"),
    )
    return build_rich_text_ai_request_message(
        messages,
        format_instruction=format_instruction,
    )


def build_agent_chat_message(feature: str, body: dict[str, Any]) -> str:
    """Compatibility alias for the global AgentChat message builder."""
    return build_rich_text_agent_chat_message(feature, body)


__all__ = [
    "FEATURE_CODE",
    "MAX_AFTER_TEXT",
    "MAX_BEFORE_TEXT",
    "MAX_INSTRUCTION",
    "MAX_SELECTED_TEXT",
    "VALID_FEATURES",
    "build_agent_chat_message",
    "build_ai_messages",
    "build_default_rich_text_skill_package_definition",
    "build_rich_text_action_catalog",
    "build_rich_text_agent_chat_message",
    "get_rich_text_action_template",
    "is_valid_writing_action",
    "normalize_rich_text_action_key",
    "normalize_writing_action",
]
