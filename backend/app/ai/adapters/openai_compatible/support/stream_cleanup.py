"""Shared stream cleanup helpers for OpenAI-compatible protocol flows."""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


async def aclose_openai_stream(stream: Any) -> None:
    """Close upstream SDK streams once a terminal SSE event has been emitted."""
    if stream is None or not hasattr(stream, "aclose"):
        return
    try:
        await stream.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.debug("OpenAI upstream stream aclose (ignored): {}", exc)


__all__ = ["aclose_openai_stream"]
