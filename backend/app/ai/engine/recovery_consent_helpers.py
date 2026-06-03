"""Consent-payload helpers for recovery orchestration."""

from __future__ import annotations

from typing import Any

from app.ai.types import ChatMessage

from .types import RecoveryDecision


def pending_consent_payload_from_tool_calls(
    tool_calls: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    for tool_call in tool_calls or []:
        payload = tool_call.get("pending_consent")
        if isinstance(payload, dict) and not payload.get("resolved"):
            return dict(payload)
    return None


def extract_pending_consent_payload(
    messages: list[ChatMessage],
) -> dict[str, Any] | None:
    for message in reversed(messages):
        meta = message.metadata or {}
        payload = meta.get("pending_consent")
        if isinstance(payload, dict) and not payload.get("resolved"):
            return dict(payload)
        payload = pending_consent_payload_from_tool_calls(message.tool_calls)
        if payload:
            return payload
    return None


def pending_consent_payload_from_decision(
    decision: RecoveryDecision | None,
) -> dict[str, Any] | None:
    if decision is None:
        return None
    meta = dict(decision.metadata or {})
    payload = meta.get("pending_consent")
    return dict(payload) if isinstance(payload, dict) else None


def ensure_latest_assistant_pending_consent(
    messages: list[ChatMessage],
    payload: dict[str, Any] | None,
) -> None:
    if not isinstance(payload, dict) or not payload:
        return
    normalized_payload = dict(payload)
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        metadata = dict(message.metadata or {})
        metadata["pending_consent"] = normalized_payload
        message.metadata = metadata
        return
    messages.append(
        ChatMessage(
            role="assistant",
            content="",
            metadata={"pending_consent": normalized_payload},
        )
    )
