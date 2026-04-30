"""Helpers for resolving user-visible AI reply language."""

from __future__ import annotations

import re
from typing import Any

from app.core.i18n import get_locale

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_LOCALE_KEY_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+){2,}$")


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
    if isinstance(input_variables, dict):
        explicit_locale = normalize_page_locale(
            input_variables.get("reply_locale")
            or input_variables.get("user_locale")
            or input_variables.get("locale")
        )
        if explicit_locale:
            return explicit_locale

    return normalize_page_locale(get_locale()) or "zh_CN"


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
    "infer_page_locale_from_text",
    "infer_user_message_locale",
    "looks_like_locale_key",
    "normalize_page_locale",
    "page_language_name",
    "resolve_page_locale",
    "resolve_visible_reply_locale",
]
