"""Message conversion helpers for multimodal adapter execution."""

from __future__ import annotations

from typing import Any

from app.ai.adapters.openai_compatible.support.audio_inputs import (
    AUDIO_MIME_TO_OPENAI_FORMAT,
)
from app.ai.adapters.openai_compatible.support.chat_multimodal_messages import (
    convert_chat_messages,
)
from app.ai.adapters.openai_compatible.support.responses_input_builder import (
    build_responses_message_content as build_responses_message_content_impl,
)
from app.ai.adapters.openai_compatible.support.responses_input_builder import (
    convert_messages_to_responses_input as convert_messages_to_responses_input_impl,
)
from app.ai.types import ChatMessage

SUPPORTS_NATIVE_AUDIO: bool = True


async def convert_messages_to_responses_input_for_adapter(
    *,
    adapter: Any,
    messages: list[ChatMessage],
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> list[dict[str, Any]]:
    return await convert_messages_to_responses_input_impl(
        adapter=adapter,
        messages=messages,
        supports_vision=supports_vision,
        supports_audio=supports_audio,
        supports_video=supports_video,
    )


async def build_responses_message_content_for_adapter(
    *,
    adapter: Any,
    msg: ChatMessage,
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> str | list[dict[str, Any]]:
    return await build_responses_message_content_impl(
        adapter=adapter,
        msg=msg,
        supports_vision=supports_vision,
        supports_audio=supports_audio,
        supports_video=supports_video,
    )


async def convert_chat_messages_for_adapter(
    *,
    adapter: Any,
    messages: list[ChatMessage],
    supports_vision: bool = True,
    supports_audio: bool = False,
    supports_video: bool = False,
) -> list[dict[str, Any]]:
    return await convert_chat_messages(
        adapter=adapter,
        messages=messages,
        supports_vision=supports_vision,
        supports_audio=supports_audio,
        supports_video=supports_video,
        supports_native_audio=SUPPORTS_NATIVE_AUDIO,
        audio_mime_to_openai_format=AUDIO_MIME_TO_OPENAI_FORMAT,
    )


__all__ = [
    "SUPPORTS_NATIVE_AUDIO",
    "build_responses_message_content_for_adapter",
    "convert_chat_messages_for_adapter",
    "convert_messages_to_responses_input_for_adapter",
]
