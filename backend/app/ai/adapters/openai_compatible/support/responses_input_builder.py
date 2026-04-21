"""Responses API input conversion helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.types import ChatMessage


class ResponsesInputAdapterProtocol(Protocol):
    async def _resolve_image_url_for_llm(
        self,
        att_url: str,
        att_mime: str,
        *,
        attachment_id: object = None,
    ) -> str | None: ...


async def build_responses_message_content(
    *,
    adapter: ResponsesInputAdapterProtocol,
    msg: ChatMessage,
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> str | list[dict[str, Any]]:
    if msg.role != "user" or not msg.attachments:
        return msg.content or ""

    parts: list[dict[str, Any]] = []
    if msg.content:
        parts.append({"type": "input_text", "text": msg.content})

    for att in msg.attachments:
        att_type = str(att.get("type") or "").lower()
        url = str(att.get("url") or "").strip()
        name = att.get("name") or att.get("filename") or "file"
        att_mime = str(att.get("mime_type") or "")
        attachment_id = att.get("attachment_id")

        if att_type == "image":
            if supports_vision and url:
                resolved = await adapter._resolve_image_url_for_llm(
                    url,
                    att_mime,
                    attachment_id=attachment_id,
                )
                if resolved:
                    parts.append(
                        {
                            "type": "input_image",
                            "image_url": resolved,
                            "detail": "auto",
                        }
                    )
                else:
                    parts.append(
                        {
                            "type": "input_text",
                            "text": (
                                f"[Image: {name or 'uploaded image'} "
                                "(could not load for model)]"
                            ),
                        }
                    )
            else:
                parts.append({"type": "input_text", "text": f"[Image: {name}]"})
            continue

        if att_type == "file":
            if url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[File: {name}]"})
            continue

        if att_type == "audio":
            if supports_audio and url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[Audio: {name}]"})
            continue

        if att_type == "video":
            if supports_video and url:
                parts.append(
                    {
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    }
                )
            else:
                parts.append({"type": "input_text", "text": f"[Video: {name}]"})
            continue

        parts.append({"type": "input_text", "text": f"[Attachment: {name}]"})

    return parts or (msg.content or "")


async def convert_messages_to_responses_input(
    *,
    adapter: ResponsesInputAdapterProtocol,
    messages: list[ChatMessage],
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "tool":
            converted.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id or "",
                    "output": msg.content or "",
                }
            )
            continue

        if msg.role == "assistant" and msg.tool_calls:
            for tool_call in msg.tool_calls:
                function = tool_call.get("function") or {}
                tc_id = tool_call.get("call_id") or tool_call.get("id") or ""
                converted.append(
                    {
                        "type": "function_call",
                        "call_id": tc_id,
                        "id": tool_call.get("id") or tc_id,
                        "name": function.get("name", ""),
                        "arguments": function.get("arguments", "{}") or "{}",
                        "status": "completed",
                    }
                )
            if not (msg.content or "").strip():
                continue

        content = await build_responses_message_content(
            adapter=adapter,
            msg=msg,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
        )
        converted.append(
            {
                "type": "message",
                "role": msg.role,
                "content": content,
            }
        )

    return converted


__all__ = [
    "build_responses_message_content",
    "convert_messages_to_responses_input",
]
