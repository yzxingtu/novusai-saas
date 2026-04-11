"""Multimodal message helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.support.multimodal_runtime import (
    SUPPORTS_NATIVE_AUDIO,
    build_responses_message_content_for_adapter,
    convert_chat_messages_for_adapter,
    convert_messages_to_responses_input_for_adapter,
    fetch_audio_bytes_for_adapter,
    resolve_image_url_for_adapter,
)
from app.ai.types import ChatMessage


class OpenAIAdapterMultimodalMixin:
    """Delegates multimodal conversion and attachment resolution."""

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict[str, Any]]:
        return await convert_messages_to_responses_input_for_adapter(
            adapter=self,
            messages=messages,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
        )

    async def _build_responses_message_content(
        self,
        msg: ChatMessage,
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> str | list[dict[str, Any]]:
        return await build_responses_message_content_for_adapter(
            adapter=self,
            msg=msg,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
        )

    async def _fetch_audio_bytes(self, url: str) -> bytes | None:
        return await fetch_audio_bytes_for_adapter(url)

    async def _resolve_image_url_for_llm(
        self,
        att_url: str,
        att_mime: str,
        *,
        attachment_id: object = None,
    ) -> str | None:
        return await resolve_image_url_for_adapter(
            config=self.config,
            att_url=att_url,
            att_mime=att_mime,
            attachment_id=attachment_id,
        )

    async def _convert_messages(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict[str, Any]]:
        return await convert_chat_messages_for_adapter(
            adapter=self,
            messages=messages,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
        )


__all__ = ["OpenAIAdapterMultimodalMixin", "SUPPORTS_NATIVE_AUDIO"]
