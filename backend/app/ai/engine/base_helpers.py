"""Small pure helpers extracted from BaseEngine for cohesion."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from app.ai.types import ChatMessage

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
    raw_arguments = (tool_call.get("function") or {}).get("arguments")
    if isinstance(raw_arguments, str) and raw_arguments.strip() and not parse_tool_arguments(
        raw_arguments
    ):
        return ""
    return tool_call_name(tool_call)


def keep_tool_calls_for_round(
    tool_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    return tool_calls, False


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
