"""Retired page-awareness request guards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.i18n import _

RETIRED_PAGE_AWARENESS_INPUT_KEYS = frozenset(
    {
        "append_content",
        "editor_ops",
        "get_editor_html",
        "get_editor_text",
        "get_page_context",
        "insert_content",
        "invoke_page_operation",
        "last_page_key",
        "last_page_op",
        "list_page_operations",
        "page_context",
        "page_data",
        "page_operation",
        "page_ops",
        "page_runtime",
        "page_session",
        "page_session_id",
        "replace_content",
        "replace_section",
    }
)

RETIRED_PAGE_AWARENESS_INPUT_PREFIXES = ("pageop_", "ui_")


def retired_page_awareness_input_keys(
    payload: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    retired_keys: list[str] = []
    for key in payload:
        text = str(key or "").strip()
        if not text:
            continue
        normalized = text.lower()
        if normalized in RETIRED_PAGE_AWARENESS_INPUT_KEYS or normalized.startswith(
            RETIRED_PAGE_AWARENESS_INPUT_PREFIXES
        ):
            retired_keys.append(text)
    return sorted(set(retired_keys))


def ensure_no_retired_page_awareness_input(
    payload: Mapping[str, Any] | None,
) -> None:
    retired_keys = retired_page_awareness_input_keys(payload)
    if retired_keys:
        raise ValueError(
            _(
                "agent_chat.error.retired_page_awareness_fields",
                fields=", ".join(retired_keys),
            )
        )


def assert_no_retired_page_awareness_input(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    ensure_no_retired_page_awareness_input(payload)
    return dict(payload or {})


__all__ = [
    "RETIRED_PAGE_AWARENESS_INPUT_KEYS",
    "RETIRED_PAGE_AWARENESS_INPUT_PREFIXES",
    "assert_no_retired_page_awareness_input",
    "ensure_no_retired_page_awareness_input",
    "retired_page_awareness_input_keys",
]
