"""Small pure helpers extracted from BaseEngine for cohesion."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from app.ai.types import ChatMessage

_PAGE_NAVIGATION_OPERATION_NAMES = {
    "ui_click",
    "ui_open_surface",
}


def build_user_message(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not isinstance(raw_arguments, str) or not raw_arguments.strip():
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def tool_call_name(tool_call: dict[str, Any]) -> str:
    func = tool_call.get("function") or {}
    return str(func.get("name") or tool_call.get("name") or "").strip()


def tool_call_operation_name(tool_call: dict[str, Any]) -> str:
    normalized_name = tool_call_name(tool_call)
    if not normalized_name.startswith("ui_"):
        return ""
    raw_arguments = (tool_call.get("function") or {}).get("arguments")
    if isinstance(raw_arguments, str) and raw_arguments.strip() and not parse_tool_arguments(
        raw_arguments
    ):
        return ""
    if normalized_name.startswith("ui_"):
        return normalized_name
    return ""


def truncate_tool_calls_after_navigation(
    tool_calls: list[dict[str, Any]],
    *,
    navigation_operation_names: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    for index, tool_call in enumerate(tool_calls):
        operation_name = tool_call_operation_name(tool_call)
        if operation_name in navigation_operation_names:
            if index < len(tool_calls) - 1:
                return tool_calls[: index + 1], True
            return tool_calls, False
    return tool_calls, False


def truncate_tool_calls_after_page_navigation(
    tool_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    return truncate_tool_calls_after_navigation(
        tool_calls,
        navigation_operation_names=_PAGE_NAVIGATION_OPERATION_NAMES,
    )


def messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [dataclasses.asdict(message) for message in messages]


def truncate_preview(text: str, *, max_chars: int = 280) -> str:
    value = " ".join((text or "").split())
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 3]}..."


def stable_unique_text_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized
