"""Tool gating helpers for turn-level research."""

from __future__ import annotations

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import tool_call_name


def needs_fetch_url_before_summary(messages: list[ChatMessage]) -> bool:
    """True when web_search succeeded but fetch_url has not been attempted yet."""
    has_success_search_with_candidates = False
    fetch_attempted = False
    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            name = tool_call_name(tool_call)
            if name == "web_search" and tool_call.get("success") is True:
                payload = tool_call.get("summary_payload")
                payload = payload if isinstance(payload, dict) else {}
                items = payload.get("items")
                candidate_urls = (
                    [
                        str(item.get("url") or "").strip()
                        for item in items
                        if isinstance(item, dict)
                        and str(item.get("url") or "").strip()
                    ]
                    if isinstance(items, list)
                    else []
                )
                raw_count = payload.get("result_count")
                try:
                    result_count = int(raw_count) if raw_count is not None else None
                except (TypeError, ValueError):
                    result_count = None
                if result_count is None:
                    result_count = len(candidate_urls)
                if result_count > 0 and candidate_urls:
                    has_success_search_with_candidates = True
            if name == "fetch_url":
                fetch_attempted = True
    return bool(has_success_search_with_candidates and not fetch_attempted)


def apply_fetch_url_only_gate(
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    all_tools: list[ToolDefinition] | None,
) -> list[ToolDefinition]:
    if not needs_fetch_url_before_summary(messages):
        return tools
    fetch_defs = [tool for tool in (all_tools or tools) if tool.name == "fetch_url"]
    return fetch_defs if fetch_defs else tools
