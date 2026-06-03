"""Attachment fetch/resolve helpers for multimodal adapters."""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.adapters.openai_compatible.support.audio_inputs import (
    fetch_audio_bytes,
)
from app.ai.text_semantics import extract_data_url_payload
from app.ai.tools.security import UrlValidator
from app.ai.utils.chat_attachment_media import resolve_image_url_for_llm


async def fetch_audio_bytes_for_adapter(url: str) -> bytes | None:
    return await fetch_audio_bytes(
        url,
        extract_data_url_payload_fn=lambda value: extract_data_url_payload(
            value,
            media_prefix="audio",
        ),
        validate_url=UrlValidator.validate,
        async_client_factory=httpx.AsyncClient,
    )


async def resolve_image_url_for_adapter(
    *,
    config: dict[str, Any],
    att_url: str,
    att_mime: str,
    attachment_id: object = None,
) -> str | None:
    db = config.get("internal_db")
    tenant_id = config.get("internal_tenant_id")
    return await resolve_image_url_for_llm(
        att_url,
        att_mime or None,
        db=db,
        tenant_id=tenant_id,
        attachment_id=attachment_id,
    )


__all__ = [
    "fetch_audio_bytes_for_adapter",
    "resolve_image_url_for_adapter",
]
