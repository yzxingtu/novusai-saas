"""Compatibility re-export for native web-search policy helpers."""

from app.ai.adapters.openai_compatible.support.native_web_search_policy import (
    NATIVE_WEB_SEARCH_MODEL_PREFIXES,
    map_native_web_search_error,
    provider_config_supports_hosted_web_search,
    supports_native_web_search_model,
)

__all__ = [
    "NATIVE_WEB_SEARCH_MODEL_PREFIXES",
    "map_native_web_search_error",
    "provider_config_supports_hosted_web_search",
    "supports_native_web_search_model",
]
