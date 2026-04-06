"""
Runtime capability manifest builder / 运行时能力清单构建器

Provides a single normalized capability view for the current turn.
为当前回合提供单一归一化能力视图。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai.runtime.context_assembler import ContextAssemblerState
from app.ai.runtime.types import CapabilityBundle

RuntimeCapabilityStatus = Literal["available", "degraded", "unavailable"]


@dataclass
class RuntimeCapabilityItem:
    name: str
    kind: str
    status: RuntimeCapabilityStatus
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "reason": self.reason,
            "metadata": dict(self.metadata or {}),
            "source": self.source,
        }


@dataclass
class RuntimeCapabilityManifest:
    scope: str
    tenant_id: int | None
    agent_id: int | None
    provider: str | None
    model: str | None
    runtime_model_capabilities: dict[str, Any] = field(default_factory=dict)
    tools: list[RuntimeCapabilityItem] = field(default_factory=list)
    skills: list[RuntimeCapabilityItem] = field(default_factory=list)
    knowledge_bases: list[RuntimeCapabilityItem] = field(default_factory=list)
    memory: list[RuntimeCapabilityItem] = field(default_factory=list)
    page_context: list[RuntimeCapabilityItem] = field(default_factory=list)
    web_research: list[RuntimeCapabilityItem] = field(default_factory=list)
    extensions: list[RuntimeCapabilityItem] = field(default_factory=list)
    disabled_capabilities: list[RuntimeCapabilityItem] = field(default_factory=list)
    boundaries: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    manifest_version: str = "runtime-capability-manifest/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "provider": self.provider,
            "model": self.model,
            "runtime_model_capabilities": dict(self.runtime_model_capabilities or {}),
            "tools": [item.to_dict() for item in self.tools],
            "skills": [item.to_dict() for item in self.skills],
            "knowledge_bases": [item.to_dict() for item in self.knowledge_bases],
            "memory": [item.to_dict() for item in self.memory],
            "page_context": [item.to_dict() for item in self.page_context],
            "web_research": [item.to_dict() for item in self.web_research],
            "extensions": [item.to_dict() for item in self.extensions],
            "disabled_capabilities": [
                item.to_dict() for item in self.disabled_capabilities
            ],
            "boundaries": dict(self.boundaries or {}),
            "sources": [dict(source or {}) for source in self.sources],
            "manifest_version": self.manifest_version,
        }


class AIRuntimeInventoryService:
    """
    Build normalized runtime manifest and compact summary.
    构建归一化运行时清单和紧凑摘要。
    """

    @staticmethod
    def _stable_unique(values: list[Any]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @classmethod
    def _collect_context_sources(cls, bundle: CapabilityBundle) -> list[dict[str, Any]]:
        return [
            {
                "kind": str(source.kind or "").strip(),
                "name": str(source.name or "").strip(),
                "active": bool(source.active),
                "metadata": dict(source.metadata or {}),
            }
            for source in (bundle.context_sources or [])
            if str(source.kind or "").strip()
        ]

    @staticmethod
    def _resolve_provider_model(agent: Any) -> tuple[str | None, str | None]:
        model_obj = getattr(agent, "model", None)
        provider_obj = getattr(model_obj, "provider", None)
        provider = (
            str(getattr(provider_obj, "code", "") or "").strip()
            or str(getattr(provider_obj, "name", "") or "").strip()
            or None
        )
        model = (
            str(getattr(model_obj, "model", "") or "").strip()
            or str(getattr(model_obj, "code", "") or "").strip()
            or str(getattr(model_obj, "name", "") or "").strip()
            or None
        )
        return provider, model

    @classmethod
    def build_manifest(
        cls,
        *,
        agent: Any,
        request: Any,
        bundle: CapabilityBundle,
        state: ContextAssemblerState,
        capability_injection_decision: dict[str, Any] | None = None,
    ) -> RuntimeCapabilityManifest:
        provider, model = cls._resolve_provider_model(agent)
        context_sources = cls._collect_context_sources(bundle)
        source_kinds = cls._stable_unique(
            [source.get("kind") for source in context_sources if source.get("active")]
        )
        selected_tools = cls._stable_unique(list(bundle.selected_tool_names or []))
        selected_skills = cls._stable_unique(list(bundle.selected_skill_names or []))

        tool_items = [
            RuntimeCapabilityItem(
                name=tool_name,
                kind="execution_tool",
                status="available",
                source="skill_resolver",
                metadata={
                    "consent_mode": str(
                        (bundle.tool_consent_modes or {}).get(tool_name, "auto")
                    )
                },
            )
            for tool_name in selected_tools
        ]

        skill_items = [
            RuntimeCapabilityItem(
                name=skill_name,
                kind="prompt_skill",
                status="available",
                source="skill_resolver",
            )
            for skill_name in selected_skills
        ]

        kb_ids = list(state.knowledge_base_ids or [])
        requested_kb_ids = list(state.requested_knowledge_base_ids or [])
        dropped_kb_ids = list(state.dropped_knowledge_base_ids or [])
        kb_status: RuntimeCapabilityStatus = "available" if kb_ids else "unavailable"
        kb_reason = None if kb_ids else "no_effective_knowledge_base_binding"
        kb_metadata = {
            "knowledge_base_ids": kb_ids,
            "requested_knowledge_base_ids": requested_kb_ids,
            "dropped_knowledge_base_ids": dropped_kb_ids,
            "rag_source_kinds": list(state.rag_source_kinds or []),
            "rag_source_count": len(state.rag_sources or []),
        }
        knowledge_items = [
            RuntimeCapabilityItem(
                name="knowledge_base",
                kind="context_provider",
                status=kb_status,
                reason=kb_reason,
                metadata=kb_metadata,
                source="agent.rag_config",
            )
        ]

        memory_enabled = bool(getattr(request, "memory_enabled", False))
        long_term_memory_enabled = bool(getattr(request, "long_term_memory_enabled", False))
        memory_status: RuntimeCapabilityStatus
        memory_reason: str | None = None
        if memory_enabled or long_term_memory_enabled:
            memory_status = "available"
        elif bool(state.memory_recalled):
            memory_status = "degraded"
            memory_reason = "memory_recalled_without_runtime_flags"
        else:
            memory_status = "unavailable"
            memory_reason = "memory_disabled"
        memory_items = [
            RuntimeCapabilityItem(
                name="memory",
                kind="context_provider",
                status=memory_status,
                reason=memory_reason,
                metadata={
                    "session_memory_enabled": memory_enabled,
                    "long_term_memory_enabled": long_term_memory_enabled,
                    "memory_recalled": bool(state.memory_recalled),
                    "memory_recall_slice": dict(state.memory_recall_slice or {}),
                },
                source="request.flags",
            )
        ]

        page_items = [
            RuntimeCapabilityItem(
                name=str(source.get("name") or "page_context"),
                kind="context_provider",
                status="available" if source.get("active") else "degraded",
                reason=None if source.get("active") else "inactive_page_context_source",
                metadata=dict(source.get("metadata") or {}),
                source="request.page_context",
            )
            for source in context_sources
            if source.get("kind") == "page_context"
        ]
        if not page_items:
            page_items = [
                RuntimeCapabilityItem(
                    name="page_context",
                    kind="context_provider",
                    status="unavailable",
                    reason="page_context_not_attached",
                    source="request.page_context",
                )
            ]

        has_web_search = "web_search" in selected_tools
        has_fetch_url = "fetch_url" in selected_tools
        research_status: RuntimeCapabilityStatus
        research_reason: str | None = None
        if has_web_search and has_fetch_url:
            research_status = "available"
        elif has_web_search or has_fetch_url:
            research_status = "degraded"
            research_reason = "incomplete_research_tool_pair"
        else:
            research_status = "unavailable"
            research_reason = "web_research_tools_unavailable"
        web_research_items = [
            RuntimeCapabilityItem(
                name="web_research",
                kind="execution_tool",
                status=research_status,
                reason=research_reason,
                metadata={
                    "has_web_search": has_web_search,
                    "has_fetch_url": has_fetch_url,
                },
                source="tool_registry",
            )
        ]

        disabled_items: list[RuntimeCapabilityItem] = []
        if dropped_kb_ids:
            disabled_items.append(
                RuntimeCapabilityItem(
                    name="knowledge_base",
                    kind="context_provider",
                    status="degraded",
                    reason="knowledge_base_binding_restriction",
                    metadata={"dropped_knowledge_base_ids": dropped_kb_ids},
                    source="agent_binding_guard",
                )
            )
        if research_status != "available":
            disabled_items.append(
                RuntimeCapabilityItem(
                    name="web_research",
                    kind="execution_tool",
                    status=research_status,
                    reason=research_reason,
                    metadata=web_research_items[0].metadata,
                    source="tool_registry",
                )
            )

        boundaries = {
            "capability_injection_decision": dict(capability_injection_decision or {}),
            "all_shortcircuit": bool(
                (capability_injection_decision or {}).get("all_shortcircuit", False)
            ),
            "write_operations_require_confirmation": True,
            "scope": "turn_runtime",
        }

        return RuntimeCapabilityManifest(
            scope="turn",
            tenant_id=getattr(request, "tenant_id", None),
            agent_id=getattr(agent, "id", None),
            provider=provider,
            model=model,
            runtime_model_capabilities=dict(state.runtime_model_capabilities or {}),
            tools=tool_items,
            skills=skill_items,
            knowledge_bases=knowledge_items,
            memory=memory_items,
            page_context=page_items,
            web_research=web_research_items,
            extensions=[],
            disabled_capabilities=disabled_items,
            boundaries=boundaries,
            sources=context_sources,
        )

    @classmethod
    def build_compact_summary(
        cls,
        manifest: RuntimeCapabilityManifest,
        *,
        include_knowledge_base_hint: bool = True,
        include_page_context_hint: bool = True,
        include_memory_hint: bool = True,
    ) -> dict[str, Any]:
        selected_skill_names = cls._stable_unique(
            [item.name for item in manifest.skills if item.status == "available"]
        )
        active_context_sources = [
            source
            for source in (manifest.sources or [])
            if bool(source.get("active", True))
        ]
        context_source_kinds = cls._stable_unique(
            [source.get("kind") for source in active_context_sources]
        )
        context_line = ", ".join(
            (
                f"{str(source.get('kind') or '').strip()}:{str(source.get('name') or '').strip()}"
                if str(source.get("name") or "").strip()
                and str(source.get("name") or "").strip()
                != str(source.get("kind") or "").strip()
                else str(source.get("kind") or "").strip()
            )
            for source in active_context_sources
            if str(source.get("kind") or "").strip()
        )
        return {
            "selected_skill_names": selected_skill_names,
            "context_line": context_line,
            "context_source_kinds": context_source_kinds,
            "knowledge_base_hint": bool(
                include_knowledge_base_hint and "knowledge_base" in context_source_kinds
            ),
            "page_context_hint": bool(
                include_page_context_hint and "page_context" in context_source_kinds
            ),
            "memory_hint": bool(
                include_memory_hint
                and (
                    "session_memory" in context_source_kinds
                    or "long_term_memory" in context_source_kinds
                )
            ),
            "provider": manifest.provider,
            "model": manifest.model,
            "manifest_version": manifest.manifest_version,
        }


__all__ = [
    "AIRuntimeInventoryService",
    "RuntimeCapabilityItem",
    "RuntimeCapabilityManifest",
    "RuntimeCapabilityStatus",
]
