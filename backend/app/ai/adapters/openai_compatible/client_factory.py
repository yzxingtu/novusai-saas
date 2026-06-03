"""Client factories for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

_DEFAULT_OPENAI_MAX_RETRIES = 0


def build_openai_client(*, api_key: str, base_url: str | None) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "max_retries": _DEFAULT_OPENAI_MAX_RETRIES,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)
