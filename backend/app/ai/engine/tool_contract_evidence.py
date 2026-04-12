"""Evidence collection helpers for tool contract diagnostics."""

from __future__ import annotations

from app.ai.types import ChatMessage

from .tool_policy_helpers import tool_family_for_name


def collect_tool_family_evidence(messages: list[ChatMessage]) -> dict[str, int]:
    counts = {"web_research": 0, "weather": 0, "page_ops": 0}
    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            family = tool_family_for_name(
                str(
                    (tool_call.get("function") or {}).get("name")
                    or tool_call.get("name")
                    or ""
                ).strip()
            )
            if family in counts:
                counts[family] += 1
    return counts
