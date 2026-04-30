"""Message and response inspection helpers for tool policy."""

from __future__ import annotations

from app.ai.text_semantics import has_question_indicator
from app.ai.types import ChatMessage, ChatResponse


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


def response_has_native_web_search_evidence(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    raw_response = getattr(response, "raw_response", None)
    if not isinstance(raw_response, dict):
        return False

    for item in raw_response.get("output") or []:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "web_search_call":
            action = item.get("action")
            if not isinstance(action, dict):
                return True
            sources = action.get("sources")
            if isinstance(sources, list) and any(
                isinstance(source, dict)
                and str(source.get("url") or "").startswith(("http://", "https://"))
                for source in sources
            ):
                return True
            continue
        if item_type != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if str(content.get("type") or "").strip() != "output_text":
                continue
            for annotation in content.get("annotations") or []:
                if not isinstance(annotation, dict):
                    continue
                if str(annotation.get("type") or "").strip() != "url_citation":
                    continue
                if str(annotation.get("url") or "").startswith(("http://", "https://")):
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
    "response_has_native_web_search_evidence",
]
