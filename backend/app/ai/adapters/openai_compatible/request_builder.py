"""Request/endpoint helpers for OpenAI-compatible adapters."""

from __future__ import annotations

from app.ai.adapters.openai_compatible.capabilities import normalize_wire_api


def build_endpoint_url(*, base_url: str | None, endpoint_path: str) -> str:
    normalized_base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
    return f"{normalized_base_url}/{endpoint_path.lstrip('/')}"


def resolve_chat_endpoint_path(*, wire_api: str) -> str:
    normalized_wire_api = normalize_wire_api(wire_api)
    return "responses" if normalized_wire_api == "responses" else "chat/completions"
