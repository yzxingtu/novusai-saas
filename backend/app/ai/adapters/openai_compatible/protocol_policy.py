"""Compatibility re-export for legacy adapter policy helpers."""

from __future__ import annotations

from app.ai.adapters.openai_compatible.compat.legacy_protocol_policy import (
    extract_status_code,
    should_fallback_from_responses_error,
    should_skip_sync_rescue_after_stream_error,
)

__all__ = [
    "extract_status_code",
    "should_fallback_from_responses_error",
    "should_skip_sync_rescue_after_stream_error",
]
