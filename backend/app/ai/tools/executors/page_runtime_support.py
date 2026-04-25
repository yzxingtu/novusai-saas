"""Shared helpers for page-aware UI executors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def text(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length]}..."


def normalize_public_message(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _mapping_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, dict):
            return dumped
    return None


def resolve_explicit_page_context(context: Any) -> dict[str, Any]:
    if context is None:
        return {}
    page_context = _mapping_payload(getattr(context, "page_context", None))
    return page_context or {}


def resolve_explicit_page_session_id(context: Any) -> str | None:
    if context and getattr(context, "page_session_id", None):
        session_id = text(context.page_session_id, max_length=64)
        if session_id:
            return session_id
    page_context = resolve_explicit_page_context(context)
    if page_context:
        session_id = text(page_context.get("page_session_id"), max_length=64)
        if session_id:
            return session_id
    return None


def resolve_page_session_id(context: Any) -> str | None:
    return resolve_explicit_page_session_id(context)


def read_executor_cache_value(context: Any, key: str) -> Any:
    if context is None:
        return None
    cache = getattr(context, "executor_cache", None)
    if isinstance(cache, dict) and key in cache:
        return cache.get(key)
    return None


def store_executor_cache_value(context: Any, key: str, value: Any) -> None:
    if context is None:
        return
    cache = getattr(context, "executor_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            context.executor_cache = cache
        except Exception:
            return
    cache[key] = value


def user_role_to_namespace(user_role: str) -> str:
    if user_role == "platform_admin":
        return "/admin"
    if user_role == "tenant_user":
        return "/user"
    return "/tenant"
