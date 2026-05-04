"""Policy helpers for native Responses web search support."""

from __future__ import annotations

from collections.abc import Callable

from openai import APITimeoutError

from app.ai.exceptions import (
    ContentFilterError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderTimeoutError,
)
from app.ai.web_search.types import (
    STATUS_POLICY_FILTERED,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
)

NATIVE_WEB_SEARCH_MODEL_PREFIXES: tuple[str, ...] = (
    "gpt-4.1",
    "gpt-4o",
    "gpt-5",
    "o3",
    "o4",
)


def _enabled_flag(value: object) -> bool:
    return value is True


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_hosted_web_search_smoke_evidence(config: object) -> bool:
    if not isinstance(config, dict):
        return False
    if _enabled_flag(config.get("smoke_validated")):
        return True
    if _enabled_flag(config.get("smoke_tested")):
        return True
    if _enabled_flag(config.get("approved_replay")):
        return True
    return any(
        _non_empty_string(config.get(key))
        for key in (
            "smoke_evidence",
            "smoke_artifact",
            "smoke_fixture",
            "smoke_replay",
            "replay_fixture",
        )
    )


def _has_hosted_web_search_support_flag(
    config: object,
    *,
    allow_enabled_alias: bool = False,
) -> bool:
    if not isinstance(config, dict):
        return False
    explicit_support = (
        _enabled_flag(config.get("supports_hosted_web_search"))
        or _enabled_flag(config.get("hosted_web_search_supported"))
        or _enabled_flag(config.get("native_web_search_supported"))
    )
    if explicit_support:
        return True
    if not allow_enabled_alias:
        return False
    return _enabled_flag(config.get("enabled")) or _enabled_flag(
        config.get("supported")
    )


def _supports_and_smoked(
    support_config: object,
    *,
    smoke_config: object | None = None,
    allow_enabled_alias: bool = False,
) -> bool:
    if not _has_hosted_web_search_support_flag(
        support_config,
        allow_enabled_alias=allow_enabled_alias,
    ):
        return False
    if _has_hosted_web_search_smoke_evidence(support_config):
        return True
    return _has_hosted_web_search_smoke_evidence(smoke_config)


def provider_config_supports_hosted_web_search(provider_config: object) -> bool:
    if not isinstance(provider_config, dict):
        return False

    hosted_config = provider_config.get("hosted_web_search")
    if _supports_and_smoked(provider_config, smoke_config=hosted_config):
        return True
    if _supports_and_smoked(
        hosted_config,
        smoke_config=provider_config,
        allow_enabled_alias=True,
    ):
        return True

    web_search_config = provider_config.get("web_search")
    if not isinstance(web_search_config, dict):
        return False
    if _supports_and_smoked(web_search_config):
        return True

    nested_hosted_config = web_search_config.get("hosted_web_search")
    if not isinstance(nested_hosted_config, dict):
        nested_hosted_config = web_search_config.get("hosted")
    return _supports_and_smoked(
        nested_hosted_config,
        smoke_config=web_search_config,
        allow_enabled_alias=True,
    )


def supports_native_web_search_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return False
    return any(
        normalized.startswith(prefix) for prefix in NATIVE_WEB_SEARCH_MODEL_PREFIXES
    )


def map_native_web_search_error(
    error: Exception,
    *,
    extract_status_code: Callable[[Exception], int | None],
) -> str:
    if isinstance(error, (APITimeoutError, ProviderTimeoutError)):
        return STATUS_TIMEOUT
    if isinstance(error, ContentFilterError):
        return STATUS_POLICY_FILTERED
    if isinstance(error, ModelNotFoundError):
        return STATUS_UNSUPPORTED
    if isinstance(error, ProviderConnectionError):
        return STATUS_UPSTREAM_ERROR

    status_code = extract_status_code(error)
    message = str(error).lower()
    if (
        "unsupported" in message
        or "not support" in message
        or "unknown parameter" in message
        or "invalid tool" in message
        or ("web_search" in message and "available" in message)
    ):
        return STATUS_UNSUPPORTED
    if (
        "content_filter" in message
        or "content policy" in message
        or "safety" in message
        or "policy" in message
    ):
        return STATUS_POLICY_FILTERED
    if status_code in {400, 404}:
        return STATUS_UNSUPPORTED
    if status_code == 408:
        return STATUS_TIMEOUT
    return STATUS_UPSTREAM_ERROR


__all__ = [
    "NATIVE_WEB_SEARCH_MODEL_PREFIXES",
    "map_native_web_search_error",
    "provider_config_supports_hosted_web_search",
    "supports_native_web_search_model",
]
