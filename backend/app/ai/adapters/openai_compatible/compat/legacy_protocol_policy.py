"""Legacy protocol fallback policy for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Protocol

from app.ai.runtime.protocol_recovery_policy import ProtocolRecoveryPolicy


class CrossProtocolCapabilities(Protocol):
    def is_cross_protocol_fallback_allowed(
        self,
        *,
        from_wire_api: str,
        to_wire_api: str,
    ) -> bool: ...


def extract_status_code(error: Exception) -> int | None:
    return ProtocolRecoveryPolicy.extract_status_code(error)


def should_fallback_from_responses_error(
    *,
    capabilities: CrossProtocolCapabilities,
    error: Exception,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    fallback_switch_enabled: bool,
) -> bool:
    return ProtocolRecoveryPolicy.should_cross_protocol_fallback_from_responses_error(
        capabilities=capabilities,
        error=error,
        tools=tools,
        tool_choice=tool_choice,
        use_responses_api=use_responses_api,
        fallback_switch_enabled=fallback_switch_enabled,
    )


def should_skip_sync_rescue_after_stream_error(error: Exception | None) -> bool:
    return ProtocolRecoveryPolicy.should_skip_sync_rescue_after_stream_error(
        error,
    )


__all__ = [
    "extract_status_code",
    "should_fallback_from_responses_error",
    "should_skip_sync_rescue_after_stream_error",
]
