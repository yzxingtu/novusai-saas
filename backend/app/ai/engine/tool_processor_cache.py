from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolResult

from .execution_state_machine import get_current_execution_state_machine

_PARALLEL_SAFE_TOOLS: frozenset[str] = frozenset(
    {
        "web_search",
        "fetch_url",
        "get_current_time",
        "get_current_weather",
        "get_weather_forecast",
        "calculate",
        "format_json",
    }
)


def is_parallel_safe_tool_call(
    func_name: str,
    arguments: dict[str, Any] | None = None,
) -> bool:
    """Allow readonly batches to run concurrently."""
    _ = arguments
    return str(func_name or "").strip() in _PARALLEL_SAFE_TOOLS


class ToolProcessorCache:
    def __init__(self, sandbox: ToolSandbox | None) -> None:
        self._sandbox = sandbox
        self._readonly_success_cache: dict[str, tuple[ToolResult, int]] = {}
        self._search_query_cache: dict[str, tuple[ToolResult, int]] = {}

    def bump_readonly_cache_epoch_if_needed(
        self,
        func_name: str,
        arguments: dict[str, Any],
        result: ToolResult,
    ) -> None:
        _ = func_name, arguments, result
        return

    def _normalized_readonly_cache_key(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
    ) -> str | None:
        """Return cache key for dedupe, or None if tool should never be deduped."""
        name = (func_name or "").strip()
        if not name:
            return None
        if name in {
            "get_current_weather",
            "get_weather_forecast",
            "get_current_time",
            "web_search",
            "fetch_url",
        }:
            pass
        else:
            return None
        try:
            payload = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = str(arguments)
        conv_segment = f"|cid={int(conversation_id or 0)}"
        return f"{name}|{payload}{conv_segment}"

    def _cache_kind_for_tool(self, func_name: str) -> str:
        name = (func_name or "").strip()
        if name == "web_search":
            return "search_query"
        return "readonly"

    def _cache_signature(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
    ) -> tuple[str, str] | None:
        key = self._normalized_readonly_cache_key(
            func_name,
            arguments,
            conversation_id,
        )
        if not key:
            return None
        kind = self._cache_kind_for_tool(func_name)
        return kind, key

    def _cache_store_for_kind(self, kind: str) -> dict[str, tuple[ToolResult, int]]:
        state = get_current_execution_state_machine()
        if state is not None:
            return state.cache_for_kind(kind)
        if kind == "search_query":
            return self._search_query_cache
        return self._readonly_success_cache

    def try_readonly_cache_hit(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
        tool_call_id: str,
    ) -> tuple[ToolResult, int] | None:
        signature = self._cache_signature(
            func_name,
            arguments,
            conversation_id,
        )
        if not signature:
            return None
        kind, key = signature
        cache_store = self._cache_store_for_kind(kind)
        hit = cache_store.get(key)
        if not hit:
            return None
        cached_result, cached_ms = hit
        if not cached_result.success:
            return None
        state = get_current_execution_state_machine()
        if state is not None:
            state.register_cache_hit(kind)
        return replace(cached_result, tool_call_id=tool_call_id, duration_ms=0), cached_ms

    def store_readonly_cache(
        self,
        func_name: str,
        arguments: dict[str, Any],
        conversation_id: int | None,
        result: ToolResult,
        duration_ms: int,
        tool_call_id: str,
    ) -> None:
        signature = self._cache_signature(
            func_name,
            arguments,
            conversation_id,
        )
        if not signature or not result.success:
            return
        kind, key = signature
        cache_store = self._cache_store_for_kind(kind)
        cache_store[key] = (
            replace(result, tool_call_id=tool_call_id, duration_ms=duration_ms),
            duration_ms,
        )
