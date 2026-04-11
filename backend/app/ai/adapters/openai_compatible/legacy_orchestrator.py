"""Compatibility re-export for legacy adapter execution helpers."""

from __future__ import annotations

from app.ai.adapters.openai_compatible.compat.legacy_protocol_execution import (
    execute_legacy_chat,
    execute_legacy_stream,
    log_responses_tool_call_fallback,
    responses_tool_call_fallback_enabled,
    stream_chat_completions_with_sync_rescue,
)

__all__ = [
    "execute_legacy_chat",
    "execute_legacy_stream",
    "log_responses_tool_call_fallback",
    "responses_tool_call_fallback_enabled",
    "stream_chat_completions_with_sync_rescue",
]
