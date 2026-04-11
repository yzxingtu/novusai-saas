"""Client factories for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from openai import AsyncOpenAI


def build_openai_client(*, api_key: str, base_url: str | None) -> AsyncOpenAI:
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


def build_chat_completions_v1_retry_base_url(base_url: str | None) -> str | None:
    cleaned_base_url = str(base_url or "").strip()
    if not cleaned_base_url:
        return None

    parsed = urlparse(cleaned_base_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    normalized_path = parsed.path.rstrip("/")
    if normalized_path:
        return None

    return parsed._replace(path="/v1", params="", query="", fragment="").geturl()


def resolve_retry_client(
    *,
    api_key: str,
    base_url: str | None,
    cached_client: AsyncOpenAI | Any | None,
    cached_base_url: str | None,
) -> tuple[AsyncOpenAI | Any | None, str | None]:
    retry_base_url = build_chat_completions_v1_retry_base_url(base_url)
    if not retry_base_url:
        return None, None
    if cached_client is not None and cached_base_url == retry_base_url:
        return cached_client, cached_base_url
    return (
        AsyncOpenAI(api_key=api_key, base_url=retry_base_url),
        retry_base_url,
    )
