from __future__ import annotations

import time

from app.ai.web_search.public_html import _normalize_text
from app.ai.web_search.types import STATUS_NO_RESULTS, STATUS_SUCCESS


def conv_id(context: object | None) -> int:
    if context is None or getattr(context, "conversation_id", None) is None:
        return 0
    return int(context.conversation_id)


def duplicate_query_signature(
    *,
    query: str,
    strategy: str,
    provider_label: str,
    model_code: str,
    locale: str | None,
    max_results: int,
    context: object | None,
) -> tuple[int, str, str, str, str, str, int]:
    return (
        conv_id(context),
        _normalize_text(query).lower(),
        strategy,
        provider_label,
        model_code,
        str(locale or ""),
        int(max_results),
    )


def decorate_duplicate_query_output(
    *,
    output: str,
    signature: tuple[int, str, str, str, str, str, int],
    status: str,
    seen_signatures: set[tuple[int, str, str, str, str, str, int]],
) -> str:
    if signature[0] <= 0 or status not in {STATUS_SUCCESS, STATUS_NO_RESULTS}:
        return output
    if signature in seen_signatures:
        return (
            output
            + "\n\n[Note: This exact query was already searched in this conversation; "
            "use fetch_url on a candidate URL from earlier results instead of repeating web_search.]"
        )
    seen_signatures.add(signature)
    return output


def record_native_backend_outcome(
    *,
    conv_id_value: int,
    backend_key: str,
    status: str,
    fail_streak: dict[tuple[int, str], int],
    disabled: dict[int, set[str]],
) -> tuple[bool, int]:
    key = (conv_id_value, backend_key)
    if status in {STATUS_SUCCESS, STATUS_NO_RESULTS}:
        fail_streak.pop(key, None)
        if conv_id_value:
            disabled.setdefault(conv_id_value, set()).discard(backend_key)
        return False, 0
    fail_streak[key] = fail_streak.get(key, 0) + 1
    if conv_id_value and fail_streak[key] >= 3:
        disabled.setdefault(conv_id_value, set()).add(backend_key)
        return True, fail_streak[key]
    return False, fail_streak[key]


def native_backend_disabled(
    *,
    conv_id_value: int,
    backend_key: str,
    disabled: dict[int, set[str]],
) -> bool:
    return bool(conv_id_value) and backend_key in disabled.get(conv_id_value, set())


def remaining_tool_budget_seconds(context: object | None) -> float | None:
    if context is None:
        return None
    deadline = getattr(context, "tool_deadline_monotonic", None)
    if deadline is None:
        return None
    try:
        remaining = float(deadline) - time.perf_counter()
    except (TypeError, ValueError):
        return None
    return max(0.0, remaining)


def clamp_stage_timeout_seconds(
    requested_seconds: int,
    *,
    context: object | None,
    min_stage_timeout_seconds: int,
    timeout_safety_margin_seconds: float,
) -> int:
    requested = max(min_stage_timeout_seconds, int(requested_seconds))
    remaining = remaining_tool_budget_seconds(context)
    if remaining is None:
        return requested
    bounded = min(
        float(requested),
        max(
            float(min_stage_timeout_seconds),
            remaining - timeout_safety_margin_seconds,
        ),
    )
    return max(min_stage_timeout_seconds, int(bounded))

