"""Compatibility re-export for native web-search parser helpers."""

from app.ai.adapters.openai_compatible.support.native_web_search_parser import (
    coerce_int,
    extract_native_web_search_items,
    extract_native_web_search_items_from_text,
    extract_native_web_search_request_count,
    extract_native_web_search_usage,
    extract_urls_from_native_web_search_text,
    is_verifiable_native_web_search_url,
    native_web_search_field,
    normalize_native_web_search_snippet,
)

__all__ = [
    "coerce_int",
    "extract_native_web_search_items",
    "extract_native_web_search_items_from_text",
    "extract_native_web_search_request_count",
    "extract_native_web_search_usage",
    "extract_urls_from_native_web_search_text",
    "is_verifiable_native_web_search_url",
    "native_web_search_field",
    "normalize_native_web_search_snippet",
]
