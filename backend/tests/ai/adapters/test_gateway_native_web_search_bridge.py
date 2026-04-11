from __future__ import annotations

import pytest

from app.ai.exceptions import ProviderConnectionError, ProviderTimeoutError
from app.ai.gateway_support.native_web_search_bridge import (
    native_web_search_call_status,
    native_web_search_error_status,
    raise_retryable_native_web_search_failure,
)
from app.ai.web_search.types import (
    STATUS_NO_RESULTS,
    STATUS_TIMEOUT,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
)
from app.enums.ai import CallStatusEnum


def _make_run(status: str) -> SearchProviderRun:
    return SearchProviderRun(
        provider="provider",
        provider_mode="native",
        backend_key="native:provider:model",
        status=status,
        items=[],
        attempted_backends=["native:provider:model"],
    )


def test_native_web_search_error_status_mapping() -> None:
    timeout_error = ProviderTimeoutError(
        "timeout",
        provider_code="provider",
        model_code="model",
    )
    connection_error = ProviderConnectionError("connection")

    assert native_web_search_error_status(timeout_error) == STATUS_TIMEOUT
    assert native_web_search_error_status(connection_error) == STATUS_UPSTREAM_ERROR


def test_native_web_search_call_status_mapping() -> None:
    assert native_web_search_call_status(STATUS_TIMEOUT) == CallStatusEnum.TIMEOUT.value
    assert native_web_search_call_status(STATUS_UPSTREAM_ERROR) == CallStatusEnum.FAILED.value
    assert native_web_search_call_status(STATUS_NO_RESULTS) == CallStatusEnum.SUCCESS.value


def test_raise_retryable_native_web_search_failure_timeout() -> None:
    with pytest.raises(ProviderTimeoutError):
        raise_retryable_native_web_search_failure(
            _make_run(STATUS_TIMEOUT),
            provider_code="provider",
            model_code="model",
        )


def test_raise_retryable_native_web_search_failure_connection() -> None:
    with pytest.raises(ProviderConnectionError):
        raise_retryable_native_web_search_failure(
            _make_run(STATUS_UPSTREAM_ERROR),
            provider_code="provider",
            model_code="model",
        )


def test_raise_retryable_native_web_search_failure_passthrough() -> None:
    run = _make_run(STATUS_NO_RESULTS)
    assert (
        raise_retryable_native_web_search_failure(
            run,
            provider_code="provider",
            model_code="model",
        )
        is run
    )
