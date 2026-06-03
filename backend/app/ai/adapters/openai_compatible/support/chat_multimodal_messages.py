"""Chat-completions multimodal message conversion helpers."""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.adapters.openai_compatible.support.audio_inputs import (
    build_input_audio_part,
)
from app.ai.types import ChatMessage


class ChatMultimodalAdapterProtocol(Protocol):
    async def _fetch_audio_bytes(self, url: str) -> bytes | None: ...

    async def _resolve_image_url_for_llm(
        self,
        att_url: str,
        att_mime: str,
        *,
        attachment_id: object = None,
    ) -> str | None: ...


async def convert_chat_messages(
    *,
    adapter: ChatMultimodalAdapterProtocol,
    messages: list[ChatMessage],
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
    supports_native_audio: bool = True,
    audio_mime_to_openai_format: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Convert shared ChatMessage objects into chat.completions payloads."""
    openai_messages: list[dict[str, Any]] = []
    audio_formats = audio_mime_to_openai_format or {}

    for msg in messages:
        openai_msg: dict[str, Any] = {"role": msg.role}

        if msg.role == "user" and msg.attachments:
            content_parts: list[dict[str, Any]] = []
            if msg.content:
                content_parts.append({"type": "text", "text": msg.content})
            for att in msg.attachments:
                att_type = str(att.get("type") or "").lower()
                att_url = str(att.get("url") or "")
                att_name = str(att.get("name") or "")
                att_mime = str(att.get("mime_type") or "")
                attachment_id = att.get("attachment_id")
                if att_type == "image" and att_url:
                    if supports_vision:
                        resolved = await adapter._resolve_image_url_for_llm(
                            att_url,
                            att_mime,
                            attachment_id=attachment_id,
                        )
                        if resolved:
                            content_parts.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": resolved},
                                }
                            )
                        else:
                            content_parts.append(
                                {
                                    "type": "text",
                                    "text": (
                                        f"[Image: {att_name or 'uploaded image'} "
                                        "(could not load for model)]"
                                    ),
                                }
                            )
                    else:
                        content_parts.append(
                            {
                                "type": "text",
                                "text": f"[Image: {att_name or 'uploaded image'}]",
                            }
                        )
                elif att_type == "audio":
                    hint = f"[Audio: {att_name or 'uploaded audio'}]"
                    if not att_url:
                        content_parts.append({"type": "text", "text": hint})
                    elif supports_audio and supports_native_audio:
                        bytes_result = await adapter._fetch_audio_bytes(att_url)
                        if bytes_result is None:
                            content_parts.append({"type": "text", "text": hint})
                        else:
                            content_parts.append(
                                build_input_audio_part(
                                    bytes_result,
                                    att_mime,
                                    audio_mime_to_openai_format=audio_formats,
                                )
                            )
                    else:
                        content_parts.append({"type": "text", "text": hint})
                elif att_type == "video" and att_url:
                    content_parts.append(
                        {
                            "type": "text",
                            "text": f"[Video: {att_name or 'uploaded video'}]",
                        }
                    )
                elif att_type == "file" and att_name:
                    file_hint = f"[Attached file: {att_name}"
                    if att_mime:
                        file_hint += f", type: {att_mime}"
                    file_hint += "]"
                    content_parts.append({"type": "text", "text": file_hint})
            openai_msg["content"] = content_parts if content_parts else msg.content
        else:
            openai_msg["content"] = msg.content

        if msg.name:
            openai_msg["name"] = msg.name
        if msg.tool_calls:
            openai_msg["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            openai_msg["tool_call_id"] = msg.tool_call_id

        openai_messages.append(openai_msg)

    return openai_messages


__all__ = ["convert_chat_messages"]
