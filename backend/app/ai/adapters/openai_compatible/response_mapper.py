"""Response metadata helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from typing import Any


def attach_protocol_metadata(
    metadata: dict[str, Any] | None,
    *,
    protocol_path: str,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload.setdefault("protocol_path", protocol_path)
    return payload
