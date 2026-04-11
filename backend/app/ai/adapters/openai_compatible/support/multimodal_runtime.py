"""Compatibility facade for multimodal support helpers."""

from __future__ import annotations

from app.ai.adapters.openai_compatible.support.multimodal_attachment_runtime import (
    fetch_audio_bytes_for_adapter,
    resolve_image_url_for_adapter,
)
from app.ai.adapters.openai_compatible.support.multimodal_conversion_runtime import (
    SUPPORTS_NATIVE_AUDIO,
    build_responses_message_content_for_adapter,
    convert_chat_messages_for_adapter,
    convert_messages_to_responses_input_for_adapter,
)

__all__ = [
    "SUPPORTS_NATIVE_AUDIO",
    "build_responses_message_content_for_adapter",
    "convert_chat_messages_for_adapter",
    "convert_messages_to_responses_input_for_adapter",
    "fetch_audio_bytes_for_adapter",
    "resolve_image_url_for_adapter",
]
