"""Helpers for resolving page locale and user-visible page language."""

from __future__ import annotations

import re
from typing import Any

from app.core.i18n import get_locale

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_LOCALE_KEY_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+){2,}$")
_PAGE_CONTEXT_KEY = "page_context"


def normalize_page_locale(locale: Any) -> str | None:
    normalized = str(locale or "").strip().replace("_", "-").lower()
    if not normalized:
        return None
    if normalized.startswith("zh"):
        return "zh_CN"
    if normalized.startswith("en"):
        return "en"
    return None


def resolve_page_locale(input_variables: dict[str, Any] | None) -> str:
    page_context = (
        input_variables.get(_PAGE_CONTEXT_KEY)
        if isinstance(input_variables, dict)
        else None
    )
    if isinstance(page_context, dict):
        page_data = (
            page_context.get("page_data")
            if isinstance(page_context.get("page_data"), dict)
            else {}
        )
        explicit_locale = normalize_page_locale(
            page_data.get("locale") or page_context.get("locale")
        )
        if explicit_locale:
            return explicit_locale

        inferred_locale = infer_page_locale_from_page_context(page_context)
        if inferred_locale:
            return inferred_locale

    return normalize_page_locale(get_locale()) or "zh_CN"


def infer_page_locale_from_page_context(page_context: dict[str, Any]) -> str | None:
    page_data = (
        page_context.get("page_data")
        if isinstance(page_context.get("page_data"), dict)
        else {}
    )
    breadcrumb = (
        page_data.get("navigation_context", {}).get("breadcrumb")
        if isinstance(page_data.get("navigation_context"), dict)
        else None
    )
    text_candidates: list[str] = []
    for value in (
        page_context.get("page_title"),
        page_data.get("entity_description"),
    ):
        if isinstance(value, str) and value.strip():
            text_candidates.append(value)
    if isinstance(breadcrumb, list):
        text_candidates.extend(
            str(item).strip()
            for item in breadcrumb
            if isinstance(item, str) and str(item).strip()
        )
    return infer_page_locale_from_text(*text_candidates)


def infer_page_locale_from_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if looks_like_locale_key(text):
            continue
        if _CJK_RE.search(text):
            return "zh_CN"
        if len(_LATIN_RE.findall(text)) >= 3:
            return "en"
    return None


def infer_user_message_locale(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or looks_like_locale_key(text):
        return None
    if _CJK_RE.search(text):
        return "zh_CN"
    if len(_LATIN_RE.findall(text)) >= 6:
        return "en"
    return None


def resolve_visible_reply_locale(
    messages: list[Any] | None,
    input_variables: dict[str, Any] | None,
) -> str:
    if isinstance(messages, list):
        for message in reversed(messages):
            role = (
                message.get("role")
                if isinstance(message, dict)
                else getattr(message, "role", None)
            )
            if str(role or "").strip() != "user":
                continue
            content = (
                message.get("content")
                if isinstance(message, dict)
                else getattr(message, "content", None)
            )
            inferred_locale = infer_user_message_locale(content)
            if inferred_locale:
                return inferred_locale
    return resolve_page_locale(input_variables)


def looks_like_locale_key(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or " " in text:
        return False
    return bool(_LOCALE_KEY_RE.fullmatch(text.lower()))


def page_language_name(locale: str) -> str:
    return "中文(Chinese)" if normalize_page_locale(locale) == "zh_CN" else "English"


__all__ = [
    "infer_page_locale_from_page_context",
    "infer_page_locale_from_text",
    "infer_user_message_locale",
    "looks_like_locale_key",
    "normalize_page_locale",
    "page_language_name",
    "resolve_page_locale",
    "resolve_visible_reply_locale",
]
