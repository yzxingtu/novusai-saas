"""Request builders for native Responses web-search calls."""

from __future__ import annotations

from typing import Any

NATIVE_WEB_SEARCH_TOOL: dict[str, str] = {
    "type": "web_search",
    "search_context_size": "medium",
}
NATIVE_WEB_SEARCH_INCLUDE_SOURCES: tuple[str, ...] = (
    "web_search_call.action.sources",
)


def build_native_web_search_request(
    *,
    model: str,
    query: str,
    instructions: str,
    timeout_seconds: int,
    stream: bool,
    include_sources: bool = False,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": model,
        "input": query,
        "instructions": instructions,
        "tools": [dict(NATIVE_WEB_SEARCH_TOOL)],
        "tool_choice": "required",
        "timeout": float(timeout_seconds),
    }
    if stream:
        request["stream"] = True
    if include_sources and not stream:
        request["include"] = list(NATIVE_WEB_SEARCH_INCLUDE_SOURCES)
    return request


__all__ = [
    "NATIVE_WEB_SEARCH_INCLUDE_SOURCES",
    "NATIVE_WEB_SEARCH_TOOL",
    "build_native_web_search_request",
]
