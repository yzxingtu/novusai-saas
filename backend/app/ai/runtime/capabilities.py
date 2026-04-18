"""
Capability registry primitives / 能力注册表基础原语

Provides reusable registry + merge logic for runtime capability assembly.
提供可复用的运行时能力注册与合并逻辑。
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.types import CapabilityBundle, CapabilityDescriptor, ContextSource
from app.ai.tools.types import ToolDefinition


@dataclass
class CapabilityContext:
    """
    Capability assembly input context / 能力装配输入上下文
    """

    agent: Any
    request: Any
    skill_result: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityFragment:
    """
    Partial capability payload for a single provider.
    单个 provider 产出的能力片段。
    """

    tools: list[ToolDefinition] = field(default_factory=list)
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    capability_descriptors: list[CapabilityDescriptor] = field(default_factory=list)
    context_sources: list[ContextSource] = field(default_factory=list)


CapabilityProviderResult = CapabilityFragment | CapabilityBundle | None
CapabilityProvider = Callable[
    [CapabilityContext],
    CapabilityProviderResult | Awaitable[CapabilityProviderResult],
]


@dataclass
class _RegisteredProvider:
    name: str
    provider: CapabilityProvider


class CapabilityRegistry:
    """
    Runtime capability provider registry / 运行时能力 provider 注册表
    """

    def __init__(self) -> None:
        self._providers: list[_RegisteredProvider] = []

    def register(
        self,
        name: str,
        provider: CapabilityProvider,
        *,
        replace: bool = False,
    ) -> None:
        normalized = (name or "").strip()
        if not normalized:
            raise ValueError("Capability provider name must not be empty")

        existing_idx = next(
            (
                idx
                for idx, item in enumerate(self._providers)
                if item.name == normalized
            ),
            None,
        )
        if existing_idx is not None:
            if not replace:
                raise ValueError(
                    f"Capability provider already registered: {normalized}"
                )
            self._providers[existing_idx] = _RegisteredProvider(
                name=normalized,
                provider=provider,
            )
            return

        self._providers.append(
            _RegisteredProvider(
                name=normalized,
                provider=provider,
            )
        )

    def list_provider_names(self) -> list[str]:
        return [item.name for item in self._providers]

    async def build_bundle(
        self,
        context: CapabilityContext,
        *,
        base_bundle: CapabilityBundle | None = None,
    ) -> CapabilityBundle:
        bundle = base_bundle or CapabilityBundle()
        for item in self._providers:
            raw_fragment = item.provider(context)
            if inspect.isawaitable(raw_fragment):
                raw_fragment = await raw_fragment
            if raw_fragment is None:
                continue
            self._merge_fragment(bundle, raw_fragment)
        return bundle

    @classmethod
    def _merge_fragment(
        cls,
        bundle: CapabilityBundle,
        fragment: CapabilityFragment | CapabilityBundle,
    ) -> None:
        if isinstance(fragment, CapabilityBundle):
            tools = fragment.tools
            consent_modes = fragment.tool_consent_modes
            descriptors = fragment.capability_descriptors
            context_sources = fragment.context_sources
        else:
            tools = fragment.tools
            consent_modes = fragment.tool_consent_modes
            descriptors = fragment.capability_descriptors
            context_sources = fragment.context_sources

        cls._merge_tools(bundle, tools)
        bundle.tool_consent_modes.update(consent_modes or {})
        cls._merge_descriptors(bundle, descriptors or [])
        cls._merge_context_sources(bundle, context_sources or [])

    @staticmethod
    def _merge_tools(bundle: CapabilityBundle, incoming: list[ToolDefinition]) -> None:
        if not incoming:
            return
        index_by_name = {tool.name: idx for idx, tool in enumerate(bundle.tools)}
        for tool in incoming:
            name = (tool.name or "").strip()
            if not name:
                continue
            idx = index_by_name.get(name)
            if idx is None:
                index_by_name[name] = len(bundle.tools)
                bundle.tools.append(tool)
            else:
                bundle.tools[idx] = tool

    @staticmethod
    def _merge_descriptors(
        bundle: CapabilityBundle,
        descriptors: list[CapabilityDescriptor],
    ) -> None:
        if not descriptors:
            return
        seen_keys = set()
        for descriptor in bundle.capability_descriptors:
            normalized_name = str(descriptor.name or "").strip()
            normalized_source = str(descriptor.source or "").strip()
            if not normalized_name:
                continue
            if descriptor.kind == "prompt_skill":
                seen_keys.add((descriptor.kind, normalized_name))
            seen_keys.add((descriptor.kind, normalized_name, normalized_source))
        for descriptor in descriptors:
            normalized_name = str(descriptor.name or "").strip()
            normalized_source = str(descriptor.source or "").strip()
            if not normalized_name:
                continue
            descriptor.name = normalized_name
            descriptor.source = normalized_source
            key = (
                (descriptor.kind, normalized_name)
                if descriptor.kind == "prompt_skill"
                else (descriptor.kind, normalized_name, normalized_source)
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            seen_keys.add((descriptor.kind, normalized_name, normalized_source))
            bundle.capability_descriptors.append(descriptor)

    @staticmethod
    def _merge_context_sources(
        bundle: CapabilityBundle,
        context_sources: list[ContextSource],
    ) -> None:
        if not context_sources:
            return
        index_by_key = {
            (source.kind, source.name): idx
            for idx, source in enumerate(bundle.context_sources)
        }
        for source in context_sources:
            key = (source.kind, source.name)
            idx = index_by_key.get(key)
            if idx is None:
                index_by_key[key] = len(bundle.context_sources)
                bundle.context_sources.append(source)
            else:
                bundle.context_sources[idx] = source


__all__ = [
    "CapabilityContext",
    "CapabilityFragment",
    "CapabilityProvider",
    "CapabilityRegistry",
]
