"""Native web-search gateway helpers."""

from __future__ import annotations

from app.ai.exceptions import (
    ProviderConnectionError,
    ProviderTimeoutError,
)
from app.ai.web_search.types import (
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
)
from app.core.i18n import _
from app.enums.ai import CallStatusEnum


def raise_retryable_native_web_search_failure(
    run: SearchProviderRun,
    *,
    provider_code: str,
    model_code: str,
) -> SearchProviderRun:
    if run.status == STATUS_TIMEOUT:
        raise ProviderTimeoutError(
            message=run.failure_reason or _("ai.error.provider_timeout"),
            provider_code=provider_code,
            model_code=model_code,
        )
    if run.status == STATUS_UPSTREAM_ERROR:
        raise ProviderConnectionError(
            message=run.failure_reason or _("ai.error.provider_connection"),
            provider_code=provider_code,
            model_code=model_code,
        )
    return run


def native_web_search_error_status(error: Exception) -> str:
    if isinstance(error, ProviderTimeoutError):
        return STATUS_TIMEOUT
    return STATUS_UPSTREAM_ERROR


def native_web_search_call_status(status: str) -> str:
    if status == STATUS_TIMEOUT:
        return CallStatusEnum.TIMEOUT.value
    if status in {STATUS_UPSTREAM_ERROR, STATUS_UNSUPPORTED}:
        return CallStatusEnum.FAILED.value
    return CallStatusEnum.SUCCESS.value


__all__ = [
    "native_web_search_call_status",
    "native_web_search_error_status",
    "raise_retryable_native_web_search_failure",
]
