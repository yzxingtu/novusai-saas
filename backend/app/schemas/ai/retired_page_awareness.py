"""Retired page-awareness request guards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.i18n import _

RETIRED_PAGE_AWARENESS_INPUT_KEYS = frozenset(
    {
        "page_context",
        "page_data",
        "page_session_id",
    }
)


def retired_page_awareness_input_keys(
    payload: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    return sorted(
        key for key in RETIRED_PAGE_AWARENESS_INPUT_KEYS if key in payload
    )


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


__all__ = [
    "RETIRED_PAGE_AWARENESS_INPUT_KEYS",
    "ensure_no_retired_page_awareness_input",
    "retired_page_awareness_input_keys",
]
