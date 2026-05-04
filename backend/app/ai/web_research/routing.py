"""
Provider router for platform-owned WebResearch execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.ai.web_research.contracts import FetchProvider, SearchProvider

ProviderT = TypeVar("ProviderT")


@dataclass(frozen=True, slots=True)
class ProviderResolution(Generic[ProviderT]):
    provider: ProviderT
    requested_provider_id: str
    selected_provider_id: str
    disable_reason: str | None = None


class WebResearchProviderRouter:
    """Resolve default or explicitly requested WebResearch providers."""

    def __init__(
        self,
        *,
        search_providers: Mapping[str, SearchProvider],
        fetch_providers: Mapping[str, FetchProvider],
        default_search_provider_id: str,
        default_fetch_provider_id: str,
        disabled_search_providers: Mapping[str, str] | None = None,
        disabled_fetch_providers: Mapping[str, str] | None = None,
    ) -> None:
        self._search_providers = dict(search_providers)
        self._fetch_providers = dict(fetch_providers)
        self._default_search_provider_id = default_search_provider_id
        self._default_fetch_provider_id = default_fetch_provider_id
        self._disabled_search_providers = dict(disabled_search_providers or {})
        self._disabled_fetch_providers = dict(disabled_fetch_providers or {})

    @classmethod
    def from_providers(
        cls,
        *,
        search_provider: SearchProvider,
        fetch_provider: FetchProvider,
    ) -> WebResearchProviderRouter:
        return cls(
            search_providers={search_provider.provider_id: search_provider},
            fetch_providers={fetch_provider.provider_id: fetch_provider},
            default_search_provider_id=search_provider.provider_id,
            default_fetch_provider_id=fetch_provider.provider_id,
        )

    def resolve_search_provider(
        self,
        provider_id: str | None = None,
    ) -> ProviderResolution[SearchProvider]:
        return self._resolve_provider(
            providers=self._search_providers,
            disabled_providers=self._disabled_search_providers,
            requested_provider_id=provider_id or self._default_search_provider_id,
            default_provider_id=self._default_search_provider_id,
            provider_kind="search",
        )

    def resolve_fetch_provider(
        self,
        provider_id: str | None = None,
    ) -> ProviderResolution[FetchProvider]:
        return self._resolve_provider(
            providers=self._fetch_providers,
            disabled_providers=self._disabled_fetch_providers,
            requested_provider_id=provider_id or self._default_fetch_provider_id,
            default_provider_id=self._default_fetch_provider_id,
            provider_kind="fetch",
        )

    @staticmethod
    def _resolve_provider(
        *,
        providers: Mapping[str, ProviderT],
        disabled_providers: Mapping[str, str],
        requested_provider_id: str,
        default_provider_id: str,
        provider_kind: str,
    ) -> ProviderResolution[ProviderT]:
        disabled_reason = disabled_providers.get(requested_provider_id)
        if disabled_reason:
            provider = providers.get(default_provider_id)
            if provider is None:
                raise LookupError(
                    f"default {provider_kind} provider is not registered: "
                    f"{default_provider_id}"
                )
            return ProviderResolution(
                provider=provider,
                requested_provider_id=requested_provider_id,
                selected_provider_id=default_provider_id,
                disable_reason=disabled_reason,
            )

        provider = providers.get(requested_provider_id)
        if provider is not None:
            return ProviderResolution(
                provider=provider,
                requested_provider_id=requested_provider_id,
                selected_provider_id=requested_provider_id,
            )

        default_provider = providers.get(default_provider_id)
        if default_provider is None:
            raise LookupError(
                f"default {provider_kind} provider is not registered: "
                f"{default_provider_id}"
            )
        return ProviderResolution(
            provider=default_provider,
            requested_provider_id=requested_provider_id,
            selected_provider_id=default_provider_id,
            disable_reason=f"{provider_kind}_provider_not_registered",
        )


__all__ = ["ProviderResolution", "WebResearchProviderRouter"]
