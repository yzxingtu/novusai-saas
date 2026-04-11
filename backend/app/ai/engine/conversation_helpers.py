"""Conversation runtime helpers extracted for reuse/testability."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any

from app.ai.text_semantics import strip_model_function_call_markup


def strip_model_fc_tokens(text: str) -> str:
    return strip_model_function_call_markup(text)


async def await_if_needed(value: Awaitable[Any] | Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def serialize_context_sources(context_sources: list[Any] | None) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for source in context_sources or []:
        if isinstance(source, dict):
            serialized.append(
                {
                    "kind": str(source.get("kind") or "").strip() or None,
                    "name": str(source.get("name") or "").strip() or None,
                    "active": bool(source.get("active", True)),
                    "metadata": dict(source.get("metadata") or {}),
                }
            )
            continue
        if source is None:
            continue
        serialized.append(
            {
                "kind": str(getattr(source, "kind", "") or "").strip() or None,
                "name": str(getattr(source, "name", "") or "").strip() or None,
                "active": bool(getattr(source, "active", True)),
                "metadata": dict(getattr(source, "metadata", {}) or {}),
            }
        )
    return serialized

