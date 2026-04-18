"""Policy helpers for page-runtime ui_* tools."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.ai.runtime.contracts import PAGE_CONTEXT_KEY

from .contracts import PageRuntimeGuardResult

_FORBIDDEN_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"password|passcode|passwd", re.IGNORECASE),
    re.compile(r"token|api[-_\s]?key|secret|private[-_\s]?key", re.IGNORECASE),
    re.compile(
        r"captcha|otp|verification[-_\s]?code|verify[-_\s]?code",
        re.IGNORECASE,
    ),
)
_CONFIRM_KEYWORDS: tuple[str, ...] = (
    "delete",
    "drop",
    "destroy",
    "remove",
    "truncate",
)


def resolve_page_context(context: Any) -> dict[str, Any]:
    if context and isinstance(getattr(context, "variables", None), dict):
        raw = context.variables.get(PAGE_CONTEXT_KEY)
        if isinstance(raw, dict):
            return raw
    return {}


def resolve_page_session_id(context: Any) -> str:
    if context and getattr(context, "page_session_id", None):
        return str(context.page_session_id).strip()
    page_context = resolve_page_context(context)
    return str(page_context.get("page_session_id") or "").strip()


def stale_context_guard(
    *,
    arguments: Mapping[str, Any],
    page_context: Mapping[str, Any],
) -> PageRuntimeGuardResult:
    expected = arguments.get("ui_epoch")
    current = page_context.get("ui_epoch")
    if not isinstance(expected, int) or not isinstance(current, int):
      return PageRuntimeGuardResult(allowed=True)
    if expected == current:
        return PageRuntimeGuardResult(allowed=True)
    return PageRuntimeGuardResult(
        allowed=False,
        error_type="stale_context",
        message="UI context is stale. Refresh the page snapshot before continuing.",
        payload={
            "current_ui_epoch": current,
            "expected_ui_epoch": expected,
            "retry_with": ["ui_read_page", "ui_get_snapshot"],
        },
    )


def _iter_field_names(tool_name: str, arguments: Mapping[str, Any]) -> list[str]:
    if tool_name == "ui_set_field":
        field_name = str(arguments.get("field_name") or "").strip()
        return [field_name] if field_name else []
    if tool_name != "ui_fill_form":
        return []
    fields = arguments.get("fields")
    if not isinstance(fields, Mapping):
        return []
    return [str(name).strip() for name in fields if str(name).strip()]


def forbidden_field_guard(
    *,
    arguments: Mapping[str, Any],
    tool_name: str,
) -> PageRuntimeGuardResult:
    for field_name in _iter_field_names(tool_name, arguments):
        if any(pattern.search(field_name) for pattern in _FORBIDDEN_FIELD_PATTERNS):
            return PageRuntimeGuardResult(
                allowed=False,
                error_type="forbidden_field",
                message=f"Field '{field_name}' is forbidden for AI page operations.",
                payload={"field_name": field_name},
            )
    return PageRuntimeGuardResult(allowed=True)


def confirmation_guard(
    *,
    arguments: Mapping[str, Any],
    tool_name: str,
) -> PageRuntimeGuardResult:
    if bool(arguments.get("confirm")):
        return PageRuntimeGuardResult(allowed=True)
    if tool_name == "ui_submit_form":
        return PageRuntimeGuardResult(
            allowed=False,
            error_type="confirmation_required",
            message="Submitting the form requires confirmation.",
        )
    if tool_name in {"ui_click", "ui_open_surface"}:
        haystack = " ".join(
            str(
                value
                for value in (
                    arguments.get("target_locator"),
                    arguments.get("surface"),
                )
            ).lower()
        )
        if any(keyword in haystack for keyword in _CONFIRM_KEYWORDS):
            return PageRuntimeGuardResult(
                allowed=False,
                error_type="confirmation_required",
                message="Delete-like page actions require confirmation.",
            )
    return PageRuntimeGuardResult(allowed=True)

