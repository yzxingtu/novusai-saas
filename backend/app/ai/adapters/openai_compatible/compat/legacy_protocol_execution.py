"""Legacy protocol execution bridge for OpenAI-compatible adapters."""

from __future__ import annotations

from .legacy_protocol_execution_helpers import (
    LegacyCompatAdapterProtocol,
    execute_legacy_chat,
    execute_legacy_stream,
    stream_chat_completions_with_sync_rescue,
)
from .legacy_protocol_fallback_support import (
    log_responses_tool_call_fallback,
    responses_tool_call_fallback_enabled,
)

__all__ = [
    "LegacyCompatAdapterProtocol",
    "execute_legacy_chat",
    "execute_legacy_stream",
    "log_responses_tool_call_fallback",
    "responses_tool_call_fallback_enabled",
    "stream_chat_completions_with_sync_rescue",
]
