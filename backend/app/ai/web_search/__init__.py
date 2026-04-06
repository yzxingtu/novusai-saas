"""
Lightweight web search package exports.
轻量级联网搜索包导出，避免适配器初始化循环依赖。
"""

from app.ai.web_search.types import (
    DEFAULT_PUBLIC_PROVIDERS,
    NativeSearchCapability,
    PROVIDER_MODE_NATIVE,
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC,
    SearchProviderRun,
    SearchResultItem,
    WebSearchExecution,
    WebSearchExecutionMeta,
)

__all__ = [
    "DEFAULT_PUBLIC_PROVIDERS",
    "NativeSearchCapability",
    "PROVIDER_MODE_NATIVE",
    "PROVIDER_MODE_PUBLIC",
    "STATUS_NO_RESULTS",
    "STATUS_PARSE_ERROR",
    "STATUS_POLICY_FILTERED",
    "STATUS_SUCCESS",
    "STATUS_TIMEOUT",
    "STATUS_UNSUPPORTED",
    "STATUS_UPSTREAM_ERROR",
    "STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC",
    "SearchProviderRun",
    "SearchResultItem",
    "WebSearchExecution",
    "WebSearchExecutionMeta",
]
