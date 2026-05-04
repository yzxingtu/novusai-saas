"""
Provider contracts and runtime options for WebResearch.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.ai.web_research.evidence import PageEvidence, SearchResultSet


@dataclass(frozen=True, slots=True)
class SearchOptions:
    max_results: int = 5
    allow_snippet_quality: bool = False
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FetchOptions:
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebResearchRunOptions:
    search_provider_id: str | None = None
    fetch_provider_id: str | None = None
    max_search_results: int = 5
    max_fetches: int = 1
    require_fetch: bool = True
    allow_snippet_quality: bool = False
    pipeline_id: str | None = None
    provider_disable_reason: str | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


class SearchProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def search(self, query: str, options: SearchOptions) -> SearchResultSet: ...


class FetchProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def fetch(self, url: str, options: FetchOptions) -> PageEvidence: ...


__all__ = [
    "FetchOptions",
    "FetchProvider",
    "SearchOptions",
    "SearchProvider",
    "WebResearchRunOptions",
]
