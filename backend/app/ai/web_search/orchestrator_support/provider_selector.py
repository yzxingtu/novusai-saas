from __future__ import annotations

from urllib.parse import urlparse

from app.ai.web_search.types import STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC
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


def is_verified_native_runtime_candidate(
    provider: object | None,
    *,
    allow_unverified_runtime_target: bool,
    trusted_hosts: frozenset[str],
) -> tuple[bool, str]:
    if provider is None:
        return False, "runtime_provider_missing"
    if allow_unverified_runtime_target:
        return True, "allow_unverified_runtime_target_override"
    provider_type = str(getattr(provider, "type", "") or "").strip().lower()
    if provider_type != "openai_compatible":
        return True, "provider_type_verified_by_default"
    host = normalized_hostname(getattr(provider, "base_url", None))
    if is_trusted_openai_compatible_host(host, trusted_hosts=trusted_hosts):
        return True, f"trusted_openai_compatible_host:{host}"
    if not host:
        return (
            False,
            "untrusted_openai_compatible_runtime_target:missing_base_url_host",
        )
    return False, f"untrusted_openai_compatible_runtime_target:{host}"


def default_web_search_config(default_public_providers: list[str]) -> AIProviderWebSearchConfig:
    return AIProviderWebSearchConfig(
        enabled=bool(settings.WEB_SEARCH_DEFAULT_ENABLED),
        strategy=str(settings.WEB_SEARCH_DEFAULT_STRATEGY).strip()
        or STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC,
        max_results_cap=int(settings.WEB_SEARCH_DEFAULT_MAX_RESULTS_CAP),
        native_timeout_seconds=int(settings.WEB_SEARCH_DEFAULT_NATIVE_TIMEOUT_SECONDS),
        public_timeout_seconds=int(settings.WEB_SEARCH_DEFAULT_PUBLIC_TIMEOUT_SECONDS),
        public_providers=[
            provider
            for provider in settings.WEB_SEARCH_DEFAULT_PUBLIC_PROVIDERS
            if str(provider or "").strip()
        ]
        or list(default_public_providers),
    )


def normalize_provider_web_search_settings(
    provider_config: dict | None,
    *,
    default_public_providers: list[str],
) -> AIProviderWebSearchConfig:
    raw_web_search = (
        provider_config.get("web_search")
        if isinstance(provider_config, dict)
        else None
    )
    defaults = default_web_search_config(default_public_providers)
    return normalize_provider_web_search_config(
        raw_web_search,
        defaults=defaults,
    )

