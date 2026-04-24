"""
Context capability assembler / 上下文能力装配器

Builds a unified CapabilityBundle for runtime-v2 while staying compatible with
legacy execution flow.
为 runtime-v2 构建统一 CapabilityBundle，同时保持旧执行链路兼容。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

from app.ai.context.orchestrator import ContextPipelineOrchestrator
from app.ai.memory_policy import resolve_memory_runtime_policy
from app.ai.runtime.capabilities import (
    CapabilityContext,
    CapabilityFragment,
    CapabilityRegistry,
)
from app.ai.runtime.contracts import PAGE_CONTEXT_KEY
from app.ai.runtime.types import (
    CapabilityBundle,
    CapabilityDescriptor,
    ContextSource,
    collect_selected_skill_names,
)
from app.ai.skills.activation import (
    execution_capability_descriptors_for_turn,
    execution_selected_tool_names_for_turn,
    execution_tools_for_turn,
)
from app.services.ai.model_capability_lookup import resolve_runtime_model_capabilities


@dataclass
class ContextAssemblerState:
    """
    Runtime state snapshots produced by context engine.
    由 context engine 产出的运行态快照。
    """

    knowledge_base_ids: list[int] = field(default_factory=list)
    requested_knowledge_base_ids: list[int] = field(default_factory=list)
    dropped_knowledge_base_ids: list[int] = field(default_factory=list)
    rag_sources: list[dict[str, Any]] = field(default_factory=list)
    rag_source_kinds: list[str] = field(default_factory=list)
    memory_recalled: bool = False
    session_memory_injected: bool = False
    memory_recall_slice: dict[str, Any] | None = None
    runtime_model_capabilities: dict[str, Any] | None = None

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_ids": list(self.knowledge_base_ids or []),
            "requested_knowledge_base_ids": list(
                self.requested_knowledge_base_ids or []
            ),
            "dropped_knowledge_base_ids": list(self.dropped_knowledge_base_ids or []),
            "rag_sources": list(self.rag_sources or []),
            "rag_source_kinds": list(self.rag_source_kinds or []),
            "memory_recalled": bool(self.memory_recalled),
            "session_memory_injected": bool(self.session_memory_injected),
            "memory_recall_slice": dict(self.memory_recall_slice or {}),
            "runtime_model_capabilities": dict(self.runtime_model_capabilities or {}),
        }


class ContextAssembler:
    """
    Capability bundle assembler / 能力包装配器
    """

    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or self._build_default_registry()

    async def assemble_bundle(
        self,
        *,
        agent: Any,
        request: Any,
        skill_result: Any | None = None,
        state: ContextAssemblerState | None = None,
        intent_plan: list[Any] | None = None,
    ) -> CapabilityBundle:
        assembly_state = state or ContextAssemblerState()
        if not assembly_state.runtime_model_capabilities:
            assembly_state.runtime_model_capabilities = (
                await resolve_runtime_model_capabilities(
                    model=getattr(agent, "model", None),
                )
            )

        capability_context = CapabilityContext(
            agent=agent,
            request=request,
            skill_result=skill_result,
            state=assembly_state.to_state_dict(),
        )
        provider_names = self._provider_names_for_intent_plan(
            intent_plan,
            request=request,
        )
        if provider_names is None:
            bundle = await self.registry.build_bundle(capability_context)
        else:
            bundle = await self._build_bundle_for_provider_names(
                capability_context,
                provider_names,
            )
        activation = getattr(skill_result, "turn_activation", None)
        if activation is not None and activation.applied:
            bundle.selected_tool_names_override = list(
                execution_selected_tool_names_for_turn(skill_result)
            )
            bundle.selected_skill_names_override = list(
                getattr(skill_result, "selected_skill_names", []) or []
            )
        return bundle

    @classmethod
    def _build_default_registry(cls) -> CapabilityRegistry:
        registry = CapabilityRegistry()
        for name, provider in cls._default_provider_map().items():
            registry.register(name, provider)
        return registry

    @classmethod
    def _default_provider_map(cls) -> dict[str, Any]:
        return {
            "skills": cls._collect_skill_capabilities,
            "page_context": cls._collect_page_context_capabilities,
            "knowledge_base": cls._collect_knowledge_capabilities,
            "memory": cls._collect_memory_capabilities,
            "runtime_model": cls._collect_runtime_model_capabilities,
        }

    @classmethod
    async def _build_bundle_for_provider_names(
        cls,
        context: CapabilityContext,
        provider_names: list[str],
    ) -> CapabilityBundle:
        bundle = CapabilityBundle()
        provider_map = cls._default_provider_map()
        for provider_name in provider_names:
            provider = provider_map.get(provider_name)
            if provider is None:
                continue
            raw_fragment = provider(context)
            if inspect.isawaitable(raw_fragment):
                raw_fragment = await raw_fragment
            if raw_fragment is None:
                continue
            CapabilityRegistry._merge_fragment(bundle, raw_fragment)
        return bundle

    @staticmethod
    def _provider_names_for_intent_plan(
        intent_plan: list[Any] | None,
        *,
        request: Any | None = None,
    ) -> list[str] | None:
        if intent_plan is None:
            return None

        flags = ContextPipelineOrchestrator.compute_intent_flags(
            intent_plan,
            request,
        )
        memory_policy = resolve_memory_runtime_policy(request)
        has_session_memory_context = bool(
            request is not None
            and (
                bool(memory_policy.session_memory_runtime_enabled)
                or bool(getattr(request, "session_memory_injected", False))
            )
        )

        provider_names = ["skills"]
        if flags.has_page_intent:
            provider_names.append("page_context")
        if not flags.all_shortcircuit and flags.has_knowledge_intent:
            provider_names.append("knowledge_base")
        if memory_policy.memory_context_enabled or has_session_memory_context:
            provider_names.append("memory")
        provider_names.append("runtime_model")
        return provider_names

    @staticmethod
    def _stable_unique_names(values: list[Any]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @classmethod
    def _turn_skill_activation_from_metadata(
        cls,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None

        selected_tool_names = cls._stable_unique_names(
            list(metadata.get("selected_tool_names") or [])
        )
        selected_skill_names = cls._stable_unique_names(
            list(metadata.get("selected_skill_names") or [])
        )
        inventory_selected_tool_names = cls._stable_unique_names(
            list(metadata.get("inventory_selected_tool_names") or [])
        )
        inventory_selected_skill_names = cls._stable_unique_names(
            list(metadata.get("inventory_selected_skill_names") or [])
        )
        reason = str(metadata.get("turn_skill_activation_reason") or "").strip() or None
        applied = bool(metadata.get("turn_skill_activation_applied"))

        if not (
            applied
            or reason
            or selected_tool_names
            or selected_skill_names
            or inventory_selected_tool_names
            or inventory_selected_skill_names
        ):
            return None

        return {
            "applied": applied,
            "reason": reason,
            "tool_count": len(selected_tool_names),
            "selected_tool_names": selected_tool_names,
            "skill_count": len(selected_skill_names),
            "selected_skill_names": selected_skill_names,
            "inventory_tool_count": len(inventory_selected_tool_names),
            "inventory_selected_tool_names": inventory_selected_tool_names,
            "inventory_skill_count": len(inventory_selected_skill_names),
            "inventory_selected_skill_names": inventory_selected_skill_names,
        }

    @staticmethod
    def _collect_skill_capabilities(context: CapabilityContext) -> CapabilityFragment:
        skill_result = context.skill_result
        if skill_result is None:
            return CapabilityFragment()

        activation = getattr(skill_result, "turn_activation", None)
        if activation is not None and activation.applied:
            tools = list(execution_tools_for_turn(skill_result))
            descriptors = list(execution_capability_descriptors_for_turn(skill_result))
        else:
            tools = list(getattr(skill_result, "tools", []) or [])
            descriptors = list(
                getattr(skill_result, "capability_descriptors", []) or []
            )
        tool_consent_modes = dict(getattr(skill_result, "tool_consent_modes", {}) or {})
        if not descriptors:
            descriptors = ContextAssembler._build_skill_descriptors_from_tools(tools)

        inventory_selected_tool_names = ContextAssembler._stable_unique_names(
            [
                getattr(tool, "name", None)
                for tool in list(getattr(skill_result, "tools", []) or [])
            ]
        )
        inventory_selected_skill_names = ContextAssembler._stable_unique_names(
            list(getattr(skill_result, "inventory_selected_skill_names", []) or [])
        )
        selected_tool_names = ContextAssembler._stable_unique_names(
            list(getattr(skill_result, "selected_tool_names", []) or [])
        )
        selected_skill_names = ContextAssembler._stable_unique_names(
            list(getattr(skill_result, "selected_skill_names", []) or [])
        )
        if activation is None or not activation.applied:
            if not selected_tool_names:
                selected_tool_names = ContextAssembler._stable_unique_names(
                    [getattr(tool, "name", "") for tool in tools]
                )
            if not selected_skill_names:
                selected_skill_names = ContextAssembler._stable_unique_names(
                    collect_selected_skill_names(
                        descriptors=descriptors,
                        tools=tools,
                    )
                )
        context_sources: list[ContextSource] = []
        should_emit_skill_source = bool(
            (
                activation is not None
                and activation.applied
                and (selected_tool_names or selected_skill_names)
            )
            or (
                (activation is None or not activation.applied)
                and (tools or selected_skill_names)
            )
        )
        if should_emit_skill_source:
            context_sources.append(
                ContextSource(
                    kind="skill",
                    name="skill_resolver",
                    active=True,
                    metadata={
                        "tool_count": len(selected_tool_names),
                        "selected_tool_names": selected_tool_names,
                        "skill_count": len(selected_skill_names),
                        "selected_skill_names": selected_skill_names,
                        "inventory_tool_count": len(inventory_selected_tool_names),
                        "inventory_selected_tool_names": inventory_selected_tool_names,
                        "inventory_skill_count": len(inventory_selected_skill_names),
                        "inventory_selected_skill_names": (
                            inventory_selected_skill_names
                        ),
                        "turn_skill_activation_applied": bool(
                            activation is not None and activation.applied
                        ),
                        "turn_skill_activation_reason": (
                            str(getattr(activation, "reason", "") or "").strip() or None
                        ),
                    },
                )
            )

        return CapabilityFragment(
            tools=tools,
            tool_consent_modes=tool_consent_modes,
            capability_descriptors=descriptors,
            context_sources=context_sources,
        )

    @staticmethod
    def _collect_page_context_capabilities(
        context: CapabilityContext,
    ) -> CapabilityFragment:
        page_context = ContextAssembler._extract_page_context(context.request)
        if not page_context:
            return CapabilityFragment()

        page_key = str(page_context.get("page_key") or "").strip() or "page_context"
        page_title = str(page_context.get("page_title") or "").strip()
        page_data = (
            page_context.get("page_data") if isinstance(page_context, dict) else {}
        )
        metadata = {
            "page_key": page_key,
            "page_title": page_title or None,
            "has_page_data": isinstance(page_data, dict),
        }

        return CapabilityFragment(
            capability_descriptors=[
                CapabilityDescriptor(
                    name=page_key,
                    kind="context_provider",
                    source="request.page_context",
                    description="Page context provided by frontend runtime.",
                    metadata=metadata,
                )
            ],
            context_sources=[
                ContextSource(
                    kind="page_context",
                    name=page_key,
                    active=True,
                    metadata=metadata,
                )
            ],
        )

    @staticmethod
    def _collect_knowledge_capabilities(
        context: CapabilityContext,
    ) -> CapabilityFragment:
        state = context.state or {}
        kb_ids = [
            int(kb_id)
            for kb_id in (state.get("knowledge_base_ids") or [])
            if str(kb_id).strip()
        ]
        requested_kb_ids = [
            int(kb_id)
            for kb_id in (state.get("requested_knowledge_base_ids") or [])
            if str(kb_id).strip()
        ]
        dropped_kb_ids = [
            int(kb_id)
            for kb_id in (state.get("dropped_knowledge_base_ids") or [])
            if str(kb_id).strip()
        ]
        rag_sources = list(state.get("rag_sources") or [])
        rag_source_kinds = list(state.get("rag_source_kinds") or [])

        if (
            not kb_ids
            and not requested_kb_ids
            and not dropped_kb_ids
            and not rag_sources
            and not rag_source_kinds
        ):
            return CapabilityFragment()

        metadata = {
            "knowledge_base_ids": kb_ids,
            "knowledge_base_count": len(kb_ids),
            "requested_knowledge_base_ids": requested_kb_ids,
            "dropped_knowledge_base_ids": dropped_kb_ids,
            "binding_restriction_applied": bool(requested_kb_ids and dropped_kb_ids),
            "rag_source_count": len(rag_sources),
            "rag_source_kinds": rag_source_kinds,
        }

        return CapabilityFragment(
            capability_descriptors=[
                CapabilityDescriptor(
                    name="knowledge_base",
                    kind="context_provider",
                    source="agent.rag_config",
                    description="Knowledge base retrieval and RAG context injection.",
                    metadata=metadata,
                )
            ],
            context_sources=[
                ContextSource(
                    kind="knowledge_base",
                    name="knowledge_base",
                    active=bool(kb_ids or rag_sources),
                    metadata=metadata,
                )
            ],
        )

    @staticmethod
    def _collect_memory_capabilities(context: CapabilityContext) -> CapabilityFragment:
        request = context.request
        state = context.state or {}
        memory_policy = resolve_memory_runtime_policy(request)
        memory_recalled = bool(state.get("memory_recalled"))
        session_memory_injected = bool(state.get("session_memory_injected"))
        memory_recall_slice = dict(state.get("memory_recall_slice") or {})

        if (
            not memory_policy.session_memory_runtime_enabled
            and not memory_policy.long_term_memory_runtime_enabled
            and not memory_recalled
            and not session_memory_injected
        ):
            return CapabilityFragment()

        context_sources: list[ContextSource] = []
        capability_descriptors: list[CapabilityDescriptor] = []

        if memory_policy.session_memory_runtime_enabled:
            session_metadata = {
                "scene": memory_policy.scene,
                "channel": memory_policy.channel,
                "source": memory_policy.source,
                "runtime_enabled": True,
                "read_enabled": memory_policy.session_memory_read_enabled,
                "write_enabled": memory_policy.session_memory_write_enabled,
                "injected": session_memory_injected,
            }
            capability_descriptors.append(
                CapabilityDescriptor(
                    name="session_memory",
                    kind="context_provider",
                    source="request.memory",
                    description="Session memory state from Redis.",
                    metadata=session_metadata,
                )
            )
            if session_memory_injected:
                context_sources.append(
                    ContextSource(
                        kind="session_memory",
                        name="session_memory",
                        active=True,
                        metadata=session_metadata,
                    )
                )

        if memory_policy.long_term_memory_runtime_enabled or memory_recalled:
            long_term_metadata = {
                "runtime_enabled": memory_policy.long_term_memory_runtime_enabled,
                "recall_enabled": memory_policy.long_term_memory_recall_enabled,
                "capture_enabled": memory_policy.long_term_memory_capture_enabled,
                "recalled": memory_recalled,
                "recall_count": int(memory_recall_slice.get("count", 0) or 0),
                "scope_type": memory_recall_slice.get("scope_type"),
                "external_context_polluted": memory_policy.external_context_polluted,
                "external_context_reason": memory_policy.external_context_reason,
            }
            capability_descriptors.append(
                CapabilityDescriptor(
                    name="long_term_memory",
                    kind="context_provider",
                    source="context.long_term_memory",
                    description="Long-term memory profile/recall integration.",
                    metadata=long_term_metadata,
                )
            )
            context_sources.append(
                ContextSource(
                    kind="long_term_memory",
                    name="long_term_memory",
                    active=bool(
                        memory_policy.long_term_memory_recall_enabled
                        and memory_recalled
                    ),
                    metadata=long_term_metadata,
                )
            )

        return CapabilityFragment(
            capability_descriptors=capability_descriptors,
            context_sources=context_sources,
        )

    @staticmethod
    def _collect_runtime_model_capabilities(
        context: CapabilityContext,
    ) -> CapabilityFragment:
        raw_caps = dict((context.state or {}).get("runtime_model_capabilities") or {})
        model = getattr(context.agent, "model", None)
        model_code = str(getattr(model, "code", "") or "").strip() or "runtime_model"
        provider = getattr(model, "provider", None)
        provider_code = str(getattr(provider, "code", "") or "").strip()

        normalized_caps = {
            key: value
            for key, value in raw_caps.items()
            if value is not None and value != ""
        }
        if not normalized_caps and model is None:
            return CapabilityFragment()

        metadata = {
            **normalized_caps,
            "model_id": getattr(model, "id", None),
            "model_code": model_code if model_code != "runtime_model" else None,
            "provider_code": provider_code or None,
        }

        return CapabilityFragment(
            capability_descriptors=[
                CapabilityDescriptor(
                    name=model_code,
                    kind="context_provider",
                    source="runtime.model_capability",
                    description="Runtime model capability profile for this turn.",
                    metadata=metadata,
                )
            ],
            context_sources=[
                ContextSource(
                    kind="runtime_model_capability",
                    name=model_code,
                    active=bool(normalized_caps),
                    metadata=metadata,
                )
            ],
        )

    @staticmethod
    def _extract_page_context(request: Any) -> dict[str, Any] | None:
        input_variables = getattr(request, "input_variables", None)
        if not isinstance(input_variables, dict):
            return None
        page_context = input_variables.get(PAGE_CONTEXT_KEY)
        if not isinstance(page_context, dict):
            return None
        return page_context

    @staticmethod
    def _build_skill_descriptors_from_tools(
        tools: list[Any],
    ) -> list[CapabilityDescriptor]:
        descriptors: list[CapabilityDescriptor] = []
        grouped_tool_names: dict[tuple[str, str], list[str]] = {}
        skill_metadata: dict[tuple[str, str], dict[str, Any]] = {}

        for tool in tools:
            skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
            if not skill_name:
                continue
            source = str(getattr(tool, "source_package_name", "") or "").strip()
            source = f"skill_package:{source}" if source else "skill_resolver"
            key = (skill_name, source)
            tool_name = str(getattr(tool, "name", "") or "").strip()
            bucket = grouped_tool_names.setdefault(key, [])
            if tool_name and tool_name not in bucket:
                bucket.append(tool_name)
            skill_metadata.setdefault(
                key,
                {
                    "skill_id": getattr(tool, "source_skill_id", None),
                    "skill_type": getattr(tool, "source_skill_type", None),
                },
            )

        for (skill_name, source), resolved_tool_names in grouped_tool_names.items():
            metadata = dict(skill_metadata.get((skill_name, source)) or {})
            descriptors.append(
                CapabilityDescriptor(
                    name=skill_name,
                    kind="capability_pack",
                    source=source,
                    description="Resolved from tool bindings.",
                    metadata={
                        **metadata,
                        "resolved_tool_names": list(resolved_tool_names),
                        "resolved_tool_count": len(resolved_tool_names),
                        "has_execution_tools": bool(resolved_tool_names),
                    },
                )
            )
        return descriptors


class ContextCapabilityBundleProjection:
    """
    Projection helper for publishing assembled capability bundles.
    上下文能力 bundle 的统一投影辅助。
    """

    @staticmethod
    def apply_to_skill_result(
        *,
        skill_result: Any | None,
        bundle: CapabilityBundle,
    ) -> None:
        if skill_result is None:
            return
        skill_result.tools = list(bundle.tools)
        skill_result.tool_consent_modes = dict(bundle.tool_consent_modes)
        if hasattr(skill_result, "capability_descriptors"):
            skill_result.capability_descriptors = list(bundle.capability_descriptors)

    @staticmethod
    def to_diagnostics(bundle: CapabilityBundle) -> dict[str, Any]:
        selected_tool_names = ContextAssembler._stable_unique_names(
            list(bundle.selected_tool_names or [])
        )
        selected_skill_names = ContextAssembler._stable_unique_names(
            list(bundle.selected_skill_names or [])
        )
        context_sources = [
            {
                "kind": source.kind,
                "name": source.name,
                "active": source.active,
                "metadata": dict(source.metadata or {}),
            }
            for source in bundle.context_sources
        ]
        diagnostics = {
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "tool_consent_modes": dict(bundle.tool_consent_modes),
            "context_sources": context_sources,
            "capability_descriptor_count": len(bundle.capability_descriptors),
            "context_source_kinds": ContextAssembler._stable_unique_names(
                [source.get("kind") for source in context_sources]
            ),
        }
        skill_source = next(
            (
                source
                for source in context_sources
                if str(source.get("kind") or "").strip() == "skill"
            ),
            None,
        )
        turn_skill_activation = ContextAssembler._turn_skill_activation_from_metadata(
            dict((skill_source or {}).get("metadata") or {})
        )
        if turn_skill_activation:
            diagnostics["turn_skill_activation"] = turn_skill_activation
        return diagnostics


_DEFAULT_CONTEXT_ASSEMBLER: ContextAssembler | None = None


def get_context_assembler() -> ContextAssembler:
    global _DEFAULT_CONTEXT_ASSEMBLER
    if _DEFAULT_CONTEXT_ASSEMBLER is None:
        _DEFAULT_CONTEXT_ASSEMBLER = ContextAssembler()
    return _DEFAULT_CONTEXT_ASSEMBLER


__all__ = [
    "ContextAssembler",
    "ContextAssemblerState",
    "ContextCapabilityBundleProjection",
    "get_context_assembler",
]
