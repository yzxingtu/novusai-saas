"""Shared helpers for page-aware UI executors."""

from __future__ import annotations

from typing import Any

from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY


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


def resolve_page_session_id(context: Any) -> str | None:
    if context and getattr(context, "page_session_id", None):
        session_id = text(context.page_session_id, max_length=64)
        if session_id:
            return session_id
    if context and isinstance(getattr(context, "variables", None), dict):
        page_context = context.variables.get(PAGE_CONTEXT_KEY)
        if isinstance(page_context, dict):
            session_id = text(page_context.get("page_session_id"), max_length=64)
            if session_id:
                return session_id
    return None


def user_role_to_namespace(user_role: str) -> str:
    if user_role == "platform_admin":
        return "/admin"
    if user_role == "tenant_user":
        return "/user"
    return "/tenant"

