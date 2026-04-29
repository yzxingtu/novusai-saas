from __future__ import annotations

from urllib.parse import urlparse

from app.ai.web_search.types import DEFAULT_FALLBACK_PROVIDER
from app.core.config import settings
from app.schemas.ai.provider import (
    AIProviderWebSearchConfig,
    normalize_provider_web_search_config,
)


def normalized_hostname(raw_url: str | None) -> str:
    try:
        parsed = urlparse(str(raw_url or "").strip())
    except Exception:
        return ""
    return str(parsed.hostname or "").strip().lower()


def is_trusted_openai_compatible_host(
    hostname: str,
    *,
    trusted_hosts: frozenset[str],
) -> bool:
    if not hostname:
        return False
    return hostname in trusted_hosts or hostname.endswith(".openai.azure.com")


def is_native_runtime_readiness_candidate(
    provider: object | None,
    *,
    trusted_hosts: frozenset[str],
) -> tuple[bool, str]:
    if provider is None:
        return False, "runtime_provider_missing"
    provider_type = str(getattr(provider, "type", "") or "").strip().lower()
    if provider_type != "openai_compatible":
        return False, f"provider_type_native_denied:{provider_type or 'unknown'}"
    host = normalized_hostname(getattr(provider, "base_url", None))
    if is_trusted_openai_compatible_host(host, trusted_hosts=trusted_hosts):
        return True, f"trusted_openai_compatible_host:{host}"
    if not host:
        reason = "untrusted_openai_compatible_runtime_candidate:missing_base_url_host"
    else:
        reason = f"untrusted_openai_compatible_runtime_candidate:{host}"
    return False, reason


def default_web_search_config() -> AIProviderWebSearchConfig:
    return AIProviderWebSearchConfig(
        enabled=bool(settings.WEB_SEARCH_DEFAULT_ENABLED),
        max_results_cap=int(settings.WEB_SEARCH_DEFAULT_MAX_RESULTS_CAP),
        native_timeout_seconds=int(settings.WEB_SEARCH_DEFAULT_NATIVE_TIMEOUT_SECONDS),
        fallback_provider=DEFAULT_FALLBACK_PROVIDER,
        fallback_timeout_seconds=int(settings.WEB_SEARCH_DEFAULT_PUBLIC_TIMEOUT_SECONDS),
    )


def normalize_provider_web_search_settings(
    provider_config: dict | None,
) -> AIProviderWebSearchConfig:
    raw_web_search = (
        provider_config.get("web_search")
        if isinstance(provider_config, dict)
        else None
    )
    defaults = default_web_search_config()
    return normalize_provider_web_search_config(
        raw_web_search,
        defaults=defaults,
    )
