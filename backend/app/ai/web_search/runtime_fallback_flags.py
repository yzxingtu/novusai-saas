"""Runtime flags shared by hosted-search fallback and builtin web_search."""

from __future__ import annotations

from typing import Any

_HOSTED_WEB_SEARCH_FALLBACK_PREFIX = "hosted_web_search_unavailable:"


def _fallback_records(turn_record: Any) -> list[Any]:
    if turn_record is None:
        return []
    if isinstance(turn_record, dict):
        raw_records = turn_record.get("fallback_history")
    else:
        raw_records = getattr(turn_record, "fallback_history", None)
    if isinstance(raw_records, list):
        return list(raw_records)
    return []


def _fallback_reason(record: Any) -> str:
    if isinstance(record, dict):
        return str(record.get("reason") or "").strip()
    return str(getattr(record, "reason", "") or "").strip()


def hosted_web_search_fallback_observed(turn_record: Any) -> bool:
    """Return true once provider-hosted web search already failed this turn."""
    for record in _fallback_records(turn_record):
        if _fallback_reason(record).startswith(_HOSTED_WEB_SEARCH_FALLBACK_PREFIX):
            return True
    return False


def runtime_info_with_web_search_fallback_flags(
    runtime_model_info: dict[str, Any] | None,
    *,
    turn_record: Any,
) -> dict[str, Any] | None:
    if not isinstance(runtime_model_info, dict):
        return runtime_model_info
    if not hosted_web_search_fallback_observed(turn_record):
        return runtime_model_info

    runtime_info = dict(runtime_model_info)
    runtime_info["web_search_skip_native_provider"] = True
    runtime_info["web_search_skip_native_reason"] = "hosted_web_search_unavailable"
    return runtime_info


__all__ = [
    "hosted_web_search_fallback_observed",
    "runtime_info_with_web_search_fallback_flags",
]
