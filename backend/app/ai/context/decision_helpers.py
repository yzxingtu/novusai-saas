"""
Context decision helpers / 上下文判定辅助

Shared helpers for context-specific heuristics that should not rely on BaseEngine
private methods.
"""

from __future__ import annotations

from typing import Any

from app.ai.text_semantics import has_question_indicator
from app.ai.types import ChatMessage


def _tool_call_name(tool_call: dict[str, Any]) -> str:
    func = tool_call.get("function") or {}
    return str(func.get("name") or tool_call.get("name") or "").strip()


def extract_recent_successful_tool_names(
    messages: list[ChatMessage],
    *,
    limit: int = 12,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for msg in reversed(messages):
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = _tool_call_name(tool_call)
            if not tool_name or tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
            if len(names) >= limit:
                return names

    return names


def extract_last_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        text = (msg.content or "").strip()
        if text:
            return text
    return ""


def looks_like_generic_follow_up(user_text: str) -> bool:
    raw = (user_text or "").strip()
    if not raw:
        return False
    if "?" in raw or "？" in raw:
        return False
    if has_question_indicator(raw):
        return False
    normalized = " ".join(raw.lower().split())
    if len(normalized) <= 24:
        return True
    return len(normalized) <= 44 and len(normalized.split()) <= 6
