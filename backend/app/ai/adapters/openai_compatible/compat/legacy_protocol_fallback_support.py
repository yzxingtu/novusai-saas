"""Fallback-policy helpers for legacy OpenAI-compatible protocol execution."""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager

from .legacy_protocol_policy import (
    extract_status_code,
    should_fallback_from_responses_error,
)

logger = LogManager.get_logger("ai")

_RESPONSES_TOOL_FALLBACK_DISABLED = {"0", "false", "no", "off"}


def responses_tool_call_fallback_enabled(
    provider_config: dict[str, Any] | None,
) -> bool:
    raw_value = (provider_config or {}).get("responses_tool_call_fallback_enabled")
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() not in _RESPONSES_TOOL_FALLBACK_DISABLED


def log_responses_tool_call_fallback(
    *,
    model: str,
    stream: bool,
    error: Exception,
) -> None:
    logger.warning(
        "Responses tool call failed, fallback to chat.completions: model={} stream={} error_type={} status_code={} error={}",
        model,
        stream,
        type(error).__name__,
        extract_status_code(error),
        str(error),
    )


def should_fallback_after_responses_error(
    *,
    capabilities: Any,
    provider_config: dict[str, Any] | None,
    error: Exception,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    runtime_disable_cross_protocol_fallback: bool,
    fallback_blocked_by_visible_chunk: bool = False,
    model: str | None = None,
    stream: bool = False,
) -> bool:
    if fallback_blocked_by_visible_chunk:
        if model:
            logger.warning(
                "Responses stream failed after visible/tool chunk; skip cross-protocol fallback: model={} error_type={} error={}",
                model,
                type(error).__name__,
                str(error),
            )
        return False
    if runtime_disable_cross_protocol_fallback:
        return False
    should_fallback = should_fallback_from_responses_error(
        capabilities=capabilities,
        error=error,
        tools=tools,
        tool_choice=tool_choice,
        use_responses_api=use_responses_api,
        fallback_switch_enabled=responses_tool_call_fallback_enabled(provider_config),
    )
    if should_fallback:
        log_responses_tool_call_fallback(
            model=model or "",
            stream=stream,
            error=error,
        )
    return should_fallback


__all__ = [
    "log_responses_tool_call_fallback",
    "responses_tool_call_fallback_enabled",
    "should_fallback_after_responses_error",
]
