"""Audio input helpers for OpenAI-compatible multimodal adapters."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.tools.security import SSRFBlockedError
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

AUDIO_MIME_TO_OPENAI_FORMAT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mpeg3": "mpeg",
    "audio/mpg": "mpeg",
}

AUDIO_FETCH_TIMEOUT_SEC: float = 30.0
AUDIO_MAX_BYTES: int = 25 * 1024 * 1024


async def fetch_audio_bytes(
    url: str,
    *,
    extract_data_url_payload_fn: Callable[[str], str | None],
    validate_url: Callable[[str], Awaitable[None]],
    async_client_factory: Callable[..., Any],
) -> bytes | None:
    """Resolve an audio URL to bytes for native input_audio blocks."""
    if not url or not url.strip():
        return None

    normalized_url = url.strip()
    if normalized_url.startswith("data:audio"):
        payload = extract_data_url_payload_fn(normalized_url)
        if payload is None:
            return None
        try:
            return base64.b64decode(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Audio data URL base64 decode failed: {}", exc)
            return None

    try:
        await validate_url(normalized_url)
    except SSRFBlockedError as exc:
        logger.warning("Audio fetch URL blocked (SSRF): {}", exc)
        return None

    try:
        async with async_client_factory(timeout=AUDIO_FETCH_TIMEOUT_SEC) as client:
            resp = await client.get(normalized_url)
            resp.raise_for_status()
            content_length = resp.headers.get("content-length")
            try:
                declared_size = (
                    int(content_length)
                    if content_length and content_length.strip().isdigit()
                    else None
                )
            except (TypeError, ValueError, AttributeError):
                declared_size = None
            if declared_size is not None and declared_size > AUDIO_MAX_BYTES:
                logger.warning(
                    "Audio too large (content-length={} > {}), skip native",
                    declared_size,
                    AUDIO_MAX_BYTES,
                )
                return None
            data = resp.content
            if len(data) > AUDIO_MAX_BYTES:
                logger.warning(
                    "Audio body too large ({} > {}), skip native",
                    len(data),
                    AUDIO_MAX_BYTES,
                )
                return None
            return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fetch audio URL failed: {}", exc)
        return None


__all__ = [
    "AUDIO_FETCH_TIMEOUT_SEC",
    "AUDIO_MAX_BYTES",
    "AUDIO_MIME_TO_OPENAI_FORMAT",
    "fetch_audio_bytes",
]
