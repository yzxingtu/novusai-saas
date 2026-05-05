"""Message and response inspection helpers for tool policy."""

from __future__ import annotations

from app.ai.text_semantics import has_question_indicator
from app.ai.types import ChatMessage


def messages_have_blocking_pending_interaction(messages: list[ChatMessage]) -> bool:
    tail = messages[-8:] if len(messages) > 8 else messages
    for message in reversed(tail):
        meta = message.metadata or {}
        pending_consent = meta.get("pending_consent")
        if isinstance(pending_consent, dict) and not pending_consent.get("resolved"):
            return True
        pending_confirmation = meta.get("pending_confirmation")
        if isinstance(pending_confirmation, dict) and not pending_confirmation.get(
            "resolved"
        ):
            return True
        for tool_call in message.tool_calls or []:
            if isinstance(tool_call.get("pending_consent"), dict) and not tool_call[
                "pending_consent"
            ].get("resolved"):
                return True
            if isinstance(
                tool_call.get("pending_confirmation"), dict
            ) and not tool_call["pending_confirmation"].get("resolved"):
                return True
    return False


def looks_like_generic_follow_up(user_text: str) -> bool:
    raw = (user_text or "").strip()
    if not raw:
        return False
    if "?" in raw or "？" in raw:
        return False
    if has_question_indicator(raw):
        return False
    normalized = " ".join(raw.lower().split())
    if len(normalized) <= 24:
        return True
    return len(normalized) <= 44 and len(normalized.split()) <= 6


__all__ = [
    "looks_like_generic_follow_up",
    "messages_have_blocking_pending_interaction",
]
