"""
Public HTML backend cache and cooldown state.
公共 HTML 后端缓存与降速状态。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.web_search.public_html_parsing import normalize_text
from app.ai.web_search.types import (
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    SearchProviderRun,
)
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.web_search")

_BACKEND_FAIL_STREAK: dict[tuple[int, str], int] = {}
_BACKEND_DISABLED: dict[int, set[str]] = {}
_BACKEND_QUERY_CACHE: dict[
    tuple[int, str, str, str, str, str, str, int],
    SearchProviderRun,
] = {}


def conv_id(context: "ExecutionContext | None") -> int:
    if context is None or context.conversation_id is None:
        return 0
    return int(context.conversation_id)


def backend_cache_key(
    *,
    backend_key: str,
    query: str,
    strategy: str | None,
    runtime_provider_label: str | None,
    runtime_model_code: str | None,
    locale: str | None,
    max_results: int,
    context: "ExecutionContext | None",
) -> tuple[int, str, str, str, str, str, str, int]:
    return (
        conv_id(context),
        backend_key,
        normalize_text(query).lower(),
        str(strategy or "").strip().lower(),
        str(runtime_provider_label or "").strip().lower(),
        str(runtime_model_code or "").strip().lower(),
        str(locale or ""),
        int(max_results),
    )


def record_backend_outcome(conv_id_value: int, backend_key: str, status: str) -> None:
    key = (conv_id_value, backend_key)
    if status in {STATUS_SUCCESS, STATUS_NO_RESULTS}:
        _BACKEND_FAIL_STREAK.pop(key, None)
        if conv_id_value:
            _BACKEND_DISABLED.setdefault(conv_id_value, set()).discard(backend_key)
        return
    _BACKEND_FAIL_STREAK[key] = _BACKEND_FAIL_STREAK.get(key, 0) + 1
    if conv_id_value and _BACKEND_FAIL_STREAK[key] >= 2:
        _BACKEND_DISABLED.setdefault(conv_id_value, set()).add(backend_key)
        logger.info(
            "web_search backend cooling down: backend={} conv_id={} streak={}",
            backend_key,
            conv_id_value,
            _BACKEND_FAIL_STREAK[key],
        )


def backend_is_disabled(conv_id_value: int, backend_key: str) -> bool:
    return bool(conv_id_value) and backend_key in _BACKEND_DISABLED.get(
        conv_id_value, set()
    )


def get_backend_cache(
    cache_key: tuple[int, str, str, str, str, str, str, int],
) -> SearchProviderRun | None:
    return _BACKEND_QUERY_CACHE.get(cache_key)


def set_backend_cache(
    cache_key: tuple[int, str, str, str, str, str, str, int],
    run: SearchProviderRun,
) -> None:
    _BACKEND_QUERY_CACHE[cache_key] = run


__all__ = [
    "backend_cache_key",
    "backend_is_disabled",
    "conv_id",
    "get_backend_cache",
    "record_backend_outcome",
    "set_backend_cache",
]
