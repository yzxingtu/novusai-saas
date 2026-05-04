"""
Default provider adapters for WebResearchRuntime.
"""

from app.ai.web_research.providers.builtin_fetch import (
    BUILTIN_FETCH_URL_PROVIDER_ID,
    BuiltinFetchUrlProvider,
    page_evidence_from_fetch_tool_result,
)
from app.ai.web_research.providers.builtin_search import (
    BUILTIN_WEB_SEARCH_PROVIDER_ID,
    BuiltinWebSearchProvider,
)

__all__ = [
    "BUILTIN_FETCH_URL_PROVIDER_ID",
    "BUILTIN_WEB_SEARCH_PROVIDER_ID",
    "BuiltinFetchUrlProvider",
    "BuiltinWebSearchProvider",
    "page_evidence_from_fetch_tool_result",
]
