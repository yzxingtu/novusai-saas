"""Streaming helpers for native Responses web-search execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.adapters.openai_compatible.support.native_web_search_parser import (
    native_web_search_field,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


@dataclass(slots=True)
class NativeWebSearchStreamCapture:
    final_text: str
    response_usage: Any
    saw_web_search_call: bool


def _handle_native_web_search_stream_event(
    *,
    adapter: Any,
    event: Any,
    collected_text_parts: list[str],
    response_usage: Any,
    saw_web_search_call: bool,
) -> tuple[Any, bool]:
    event_type = getattr(event, "type", "") or ""
    if event_type.startswith("response.web_search_call"):
        return response_usage, True

    if event_type == "response.output_text.delta":
        delta = getattr(event, "delta", "") or ""
        if delta:
            collected_text_parts.append(delta)
        return response_usage, saw_web_search_call

    if event_type == "response.output_text.done":
        text = getattr(event, "text", "") or ""
        if text and not collected_text_parts:
            collected_text_parts.append(text)
        return getattr(event, "usage", None) or response_usage, saw_web_search_call

    if event_type == "response.output_item.done":
        item = getattr(event, "item", None)
        item_type = native_web_search_field(item, "type")
        if item_type == "web_search_call":
            return response_usage, True
        if item_type != "message":
            return response_usage, saw_web_search_call
        for content in native_web_search_field(item, "content") or []:
            if native_web_search_field(content, "type") != "output_text":
                continue
            text = str(native_web_search_field(content, "text") or "")
            if text and not collected_text_parts:
                collected_text_parts.append(text)
        return response_usage, saw_web_search_call

    if event_type == "response.completed":
        response = getattr(event, "response", None)
        response_usage = native_web_search_field(response, "usage") or response_usage
        if response is not None and not collected_text_parts:
            final_text = adapter._extract_responses_text(response)
            if final_text:
                collected_text_parts.append(final_text)
        return response_usage, saw_web_search_call

    return response_usage, saw_web_search_call


async def consume_native_web_search_stream(
    *,
    adapter: Any,
    stream: Any,
    provider_label: str,
    model: str,
    aclose_stream: Any,
) -> NativeWebSearchStreamCapture | None:
    collected_text_parts: list[str] = []
    response_usage: Any = None
    saw_web_search_call = False

    try:
        async for event in stream:
            response_usage, saw_web_search_call = _handle_native_web_search_stream_event(
                adapter=adapter,
                event=event,
                collected_text_parts=collected_text_parts,
                response_usage=response_usage,
                saw_web_search_call=saw_web_search_call,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Native web search stream fallback consumption failed: provider={} model={} error={}",
            provider_label,
            model,
            str(exc),
        )
        return None
    finally:
        await aclose_stream(stream)

    return NativeWebSearchStreamCapture(
        final_text="".join(collected_text_parts).strip(),
        response_usage=response_usage,
        saw_web_search_call=saw_web_search_call,
    )


__all__ = [
    "NativeWebSearchStreamCapture",
    "consume_native_web_search_stream",
]
