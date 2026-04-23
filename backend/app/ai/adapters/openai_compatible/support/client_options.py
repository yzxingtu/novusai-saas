"""Client override helpers for OpenAI-compatible protocol calls."""

from __future__ import annotations

from typing import Any


def with_client_retry_override(
    client: Any,
    *,
    max_retries: Any = None,
) -> Any:
    """Apply a per-request retry override when the SDK client supports it."""
    if max_retries is None:
        return client
    with_options = getattr(client, "with_options", None)
    if not callable(with_options):
        return client
    try:
        return with_options(max_retries=max_retries)
    except TypeError:
        return client


__all__ = ["with_client_retry_override"]
