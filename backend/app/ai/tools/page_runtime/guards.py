from __future__ import annotations

import re
from typing import Any

_PASSWORD_TYPES = {"password", "passcode", "passwd"}
_SENSITIVE_NAME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "captcha",
        re.compile(
            r"(captcha|otp|one[-_\s]?time[-_\s]?password|verification[-_\s]?code|verify[-_\s]?code)",
            re.IGNORECASE,
        ),
    ),
    (
        "token",
        re.compile(
            r"(token|api[-_\s]?key|secret|access[-_\s]?key|client[-_\s]?secret|private[-_\s]?key)",
            re.IGNORECASE,
        ),
    ),
    ("file_upload", re.compile(r"(upload|uploader)", re.IGNORECASE)),
)
_DESTRUCTIVE_HINTS = (
    "delete",
    "destroy",
    "drop",
    "publish",
    "reject",
    "remove",
    "reset",
    "send",
    "submit",
    "truncate",
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def validate_ui_epoch(expected_ui_epoch: Any, actual_ui_epoch: Any) -> dict[str, Any] | None:
    if expected_ui_epoch is None or actual_ui_epoch is None:
        return None
    try:
        expected = int(expected_ui_epoch)
        actual = int(actual_ui_epoch)
    except (TypeError, ValueError):
        return None
    if expected == actual:
        return None
    return {
        "data": {
            "actual_ui_epoch": actual,
            "expected_ui_epoch": expected,
        },
        "error_type": "stale_context",
        "message": "UI context is stale. Read the page again before acting.",
    }


def classify_sensitive_field(
    field_name: Any = None,
    field_type: Any = None,
) -> str | None:
    normalized_type = _normalize_text(field_type)
    if normalized_type in _PASSWORD_TYPES:
        return "password"
    normalized_name = _normalize_text(field_name)
    for category, pattern in _SENSITIVE_NAME_PATTERNS:
        if pattern.search(normalized_name):
            return category
    return None


def classify_forbidden_field(
    *,
    field_name: Any = None,
    field_type: Any = None,
) -> dict[str, Any] | None:
    category = classify_sensitive_field(field_name=field_name, field_type=field_type)
    if not category:
        return None
    return {
        "data": {"field_category": category},
        "error_type": "forbidden",
        "message": f"AI may not operate {category} fields.",
    }


def requires_confirmation(
    action_name: str,
    *,
    confirm: bool = False,
    submit_policy: Any = None,
    target_hint: Any = None,
) -> dict[str, Any] | None:
    if confirm:
        return None
    normalized_action = _normalize_text(action_name)
    normalized_target = _normalize_text(target_hint)
    should_confirm = normalized_action == "ui_submit_form"
    if _normalize_text(submit_policy) == "confirm":
        should_confirm = True
    if normalized_action in {"ui_click", "ui_navigate"} and any(
        hint in normalized_target for hint in _DESTRUCTIVE_HINTS
    ):
        should_confirm = True
    if not should_confirm:
        return None
    return {
        "data": {"target_hint": target_hint},
        "error_type": "confirmation_required",
        "message": "This action requires confirmation.",
    }


def detect_guard_failure(
    *,
    action_name: str,
    actual_ui_epoch: Any = None,
    confirm: bool = False,
    expected_ui_epoch: Any = None,
    field_name: Any = None,
    field_type: Any = None,
    submit_policy: Any = None,
    target_hint: Any = None,
) -> dict[str, Any] | None:
    return (
        validate_ui_epoch(expected_ui_epoch, actual_ui_epoch)
        or classify_forbidden_field(field_name=field_name, field_type=field_type)
        or requires_confirmation(
            action_name,
            confirm=confirm,
            submit_policy=submit_policy,
            target_hint=target_hint,
        )
    )
