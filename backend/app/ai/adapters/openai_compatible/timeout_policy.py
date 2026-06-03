"""Timeout policy helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any

DEFAULT_STREAM_TIMEOUT_SECONDS = 20.0


def normalize_timeout_seconds(value: Any) -> float | None:
    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    if timeout <= 0:
        return None
    return timeout
