"""Compatibility facade for native Responses web-search execution."""

from app.ai.adapters.openai_compatible.support.native_web_search_facade import (
    NativeWebSearchAdapterProtocol,
    native_web_search_via_responses,
    native_web_search_via_stream,
)

__all__ = [
    "NativeWebSearchAdapterProtocol",
    "native_web_search_via_responses",
    "native_web_search_via_stream",
]
