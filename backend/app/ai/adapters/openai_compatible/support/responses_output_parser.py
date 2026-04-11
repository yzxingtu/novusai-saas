"""Responses API output parsers kept outside protocol facades."""

from __future__ import annotations

from typing import Any


def extract_responses_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "output_text":
                text = getattr(content, "text", None)
                if text:
                    parts.append(text)
    return "".join(parts)


def extract_responses_tool_calls(response: Any) -> list[dict] | None:
    tool_calls: list[dict] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "function_call":
            continue
        call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
        tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": getattr(item, "name", None) or "",
                    "arguments": getattr(item, "arguments", None) or "{}",
                },
            }
        )
    return tool_calls or None


__all__ = ["extract_responses_text", "extract_responses_tool_calls"]
