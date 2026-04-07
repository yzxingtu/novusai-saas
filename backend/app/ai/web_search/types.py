"""
Web search internal types. / 联网搜索内部类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_SUCCESS = "success"
STATUS_UNSUPPORTED = "unsupported"
STATUS_TIMEOUT = "timeout"
STATUS_UPSTREAM_ERROR = "upstream_error"
STATUS_PARSE_ERROR = "parse_error"
STATUS_NO_RESULTS = "no_results"
STATUS_POLICY_FILTERED = "policy_filtered"

PROVIDER_MODE_NATIVE = "native"
PROVIDER_MODE_PUBLIC = "public"

STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC = "native_first_fallback_public"

DEFAULT_PUBLIC_PROVIDERS = ("baidu", "so360")


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str
    source: str
    provider: str
    provider_mode: str
    rank: int
    published_at: str | None = None

    def to_summary_item(self) -> dict[str, str | int]:
        payload: dict[str, str | int] = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "rank": self.rank,
        }
        if self.published_at:
            payload["published_at"] = self.published_at
        return payload


@dataclass
class SearchProviderRun:
    provider: str | None
    provider_mode: str | None
    backend_key: str | None
    status: str
    items: list[SearchResultItem] = field(default_factory=list)
    failure_reason: str | None = None
    latency_ms: int = 0
    attempted_backends: list[str] = field(default_factory=list)
    cache_hit: bool = False
    native_attempted: bool = True
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class WebSearchExecutionMeta:
    status: str
    attempted_backends: list[str] = field(default_factory=list)
    selected_backend: str | None = None
    used_fallback: bool = False
    failure_reason: str | None = None
    latency_ms: int = 0
    provider: str | None = None
    provider_mode: str | None = None
    provider_chain: list[str] = field(default_factory=list)
    fallback_reason: str | None = None
    native_failure_kind: str | None = None
    cache_hit: bool = False


@dataclass
class WebSearchExecution:
    output: str
    items: list[SearchResultItem]
    meta: WebSearchExecutionMeta


@dataclass
class NativeSearchCapability:
    supported: bool
    provider: str | None = None
    reason: str | None = None


__all__ = [
    "DEFAULT_PUBLIC_PROVIDERS",
    "NativeSearchCapability",
    "PROVIDER_MODE_NATIVE",
    "PROVIDER_MODE_PUBLIC",
    "STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC",
    "STATUS_NO_RESULTS",
    "STATUS_PARSE_ERROR",
    "STATUS_POLICY_FILTERED",
    "STATUS_SUCCESS",
    "STATUS_TIMEOUT",
    "STATUS_UNSUPPORTED",
    "STATUS_UPSTREAM_ERROR",
    "SearchProviderRun",
    "SearchResultItem",
    "WebSearchExecution",
    "WebSearchExecutionMeta",
]
