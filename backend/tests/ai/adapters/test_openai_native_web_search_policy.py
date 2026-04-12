from __future__ import annotations

from app.ai.adapters.openai_compatible import native_web_search_policy as facade
from app.ai.adapters.openai_compatible.native_web_search_policy import (
    map_native_web_search_error,
    supports_native_web_search_model,
)
from app.ai.adapters.openai_compatible.support import (
    native_web_search_policy as support,
)
from app.ai.exceptions import ProviderConnectionError, ProviderTimeoutError


class _StatusError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def test_native_web_search_policy_facade_exports_support_symbols() -> None:
    assert facade.supports_native_web_search_model is support.supports_native_web_search_model
    assert facade.map_native_web_search_error is support.map_native_web_search_error
    assert facade.NATIVE_WEB_SEARCH_MODEL_PREFIXES == support.NATIVE_WEB_SEARCH_MODEL_PREFIXES


def test_supports_native_web_search_model_requires_supported_prefix() -> None:
    assert supports_native_web_search_model("gpt-5.4") is True
    assert supports_native_web_search_model("o4-mini") is True
    assert supports_native_web_search_model("deepseek-chat") is False


def test_map_native_web_search_error_handles_timeout_and_connection() -> None:
    def extract_status_code(error: Exception) -> int | None:
        return getattr(error, "status_code", None)

    assert (
        map_native_web_search_error(
            ProviderTimeoutError("timed out"),
            extract_status_code=extract_status_code,
        )
        == "timeout"
    )
    assert (
        map_native_web_search_error(
            ProviderConnectionError("network down"),
            extract_status_code=extract_status_code,
        )
        == "upstream_error"
    )
    assert (
        map_native_web_search_error(
            _StatusError(400, "unsupported tool"),
            extract_status_code=extract_status_code,
        )
        == "unsupported"
    )
