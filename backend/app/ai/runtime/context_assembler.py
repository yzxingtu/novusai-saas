"""
Context capability assembler / 上下文能力装配器

Builds a unified CapabilityBundle for runtime-v2 while staying compatible with
legacy execution flow.
为 runtime-v2 构建统一 CapabilityBundle，同时保持旧执行链路兼容。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.capabilities import (
    CapabilityContext,
    CapabilityFragment,
    CapabilityRegistry,
)
from app.ai.runtime.types import CapabilityBundle, CapabilityDescriptor, ContextSource
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY
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
        return await self.registry.build_bundle(capability_context)

    @classmethod
    def _build_default_registry(cls) -> CapabilityRegistry:
        registry = CapabilityRegistry()
        registry.register("skills", cls._collect_skill_capabilities)
        registry.register("page_context", cls._collect_page_context_capabilities)
        registry.register("knowledge_base", cls._collect_knowledge_capabilities)
        registry.register("memory", cls._collect_memory_capabilities)
        registry.register("runtime_model", cls._collect_runtime_model_capabilities)
        return registry

    @staticmethod
    def _stable_unique_names(values: list[Any]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _collect_skill_capabilities(context: CapabilityContext) -> CapabilityFragment:
        skill_result = context.skill_result
        if skill_result is None:
            return CapabilityFragment()

        tools = list(getattr(skill_result, "tools", []) or [])
        tool_consent_modes = dict(getattr(skill_result, "tool_consent_modes", {}) or {})
        descriptors = list(getattr(skill_result, "capability_descriptors", []) or [])
        if not descriptors:
            descriptors = ContextAssembler._build_skill_descriptors_from_tools(tools)

        selected_skill_names = ContextAssembler._stable_unique_names(
            [
                descriptor.name
                for descriptor in descriptors
                if descriptor.kind == "prompt_skill"
            ]
        )
        context_sources: list[ContextSource] = []
        if tools or selected_skill_names:
            selected_tool_names = ContextAssembler._stable_unique_names(
                [getattr(tool, "name", "") for tool in tools]
            )
            context_sources.append(
                ContextSource(
                    kind="skill",
                    name="skill_resolver",
                    active=True,
                    metadata={
                        "tool_count": len(tools),
                        "selected_tool_names": selected_tool_names,
                        "skill_count": len(selected_skill_names),
                        "selected_skill_names": selected_skill_names,
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
        page_data = page_context.get("page_data")
        raw_operations = (
            page_data.get("available_operations", [])
            if isinstance(page_data, dict)
            else []
        )
        operations = [
            operation
            for operation in raw_operations
            if isinstance(operation, dict) and operation.get("name")
        ]
        writable_ops = [
            operation
            for operation in operations
            if not bool(operation.get("readonly", False))
        ]
        metadata = {
            "page_key": page_key,
            "page_title": page_title or None,
            "operation_count": len(operations),
            "writable_operation_count": len(writable_ops),
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
        memory_recalled = bool(state.get("memory_recalled"))
        memory_recall_slice = dict(state.get("memory_recall_slice") or {})

        session_memory_enabled = bool(getattr(request, "memory_enabled", False))
        long_term_memory_enabled = bool(
            getattr(request, "long_term_memory_enabled", False)
        )
        if (
            not session_memory_enabled
            and not long_term_memory_enabled
            and not memory_recalled
        ):
            return CapabilityFragment()

        context_sources: list[ContextSource] = []
        capability_descriptors: list[CapabilityDescriptor] = []

        if session_memory_enabled:
            session_metadata = {
                "scene": getattr(request, "memory_scene", ""),
                "channel": getattr(request, "memory_channel", ""),
                "source": getattr(request, "memory_source", ""),
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
            context_sources.append(
                ContextSource(
                    kind="session_memory",
                    name="session_memory",
                    active=True,
                    metadata=session_metadata,
                )
            )

        if long_term_memory_enabled or memory_recalled:
            long_term_metadata = {
                "enabled": long_term_memory_enabled,
                "recalled": memory_recalled,
                "recall_count": int(memory_recall_slice.get("count", 0) or 0),
                "scope_type": memory_recall_slice.get("scope_type"),
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
                    active=bool(long_term_memory_enabled and memory_recalled),
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
        seen: set[tuple[str, str]] = set()
        descriptors: list[CapabilityDescriptor] = []
        for tool in tools:
            skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
            if not skill_name:
                continue
            source = str(getattr(tool, "source_package_name", "") or "").strip()
            source = f"skill_package:{source}" if source else "skill_resolver"
            key = (skill_name, source)
            if key in seen:
                continue
            seen.add(key)
            descriptors.append(
                CapabilityDescriptor(
                    name=skill_name,
                    kind="prompt_skill",
                    source=source,
                    description="Resolved from tool bindings.",
                    metadata={
                        "skill_id": getattr(tool, "source_skill_id", None),
                        "skill_type": getattr(tool, "source_skill_type", None),
                    },
                )
            )
        return descriptors


class LegacyContextAssemblerAdapter:
    """
    Compatibility adapter for legacy engine integration.
    旧引擎兼容适配器。
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
        return {
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "tool_consent_modes": dict(bundle.tool_consent_modes),
            "context_sources": context_sources,
            "capability_descriptor_count": len(bundle.capability_descriptors),
            "context_source_kinds": ContextAssembler._stable_unique_names(
                [source.get("kind") for source in context_sources]
            ),
        }


_DEFAULT_CONTEXT_ASSEMBLER: ContextAssembler | None = None


def get_context_assembler() -> ContextAssembler:
    global _DEFAULT_CONTEXT_ASSEMBLER
    if _DEFAULT_CONTEXT_ASSEMBLER is None:
        _DEFAULT_CONTEXT_ASSEMBLER = ContextAssembler()
    return _DEFAULT_CONTEXT_ASSEMBLER


__all__ = [
    "ContextAssembler",
    "ContextAssemblerState",
    "LegacyContextAssemblerAdapter",
    "get_context_assembler",
]
