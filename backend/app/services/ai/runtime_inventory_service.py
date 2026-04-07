"""
Unified AI runtime inventory service / 统一 AI runtime 能力清单服务。
"""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.runtime import AIRuntimeInventoryService, ContextAssemblerState, get_context_assembler
from app.ai.skills.resolver import SkillResolveResult, SkillResolver
from app.ai.tools.types import ToolDefinition
from app.core.i18n import _
from app.core.logging import get_logger
from app.exceptions import NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.ai.model import AIModel
from app.models.ai.provider import AIProvider
from app.models.ai.skill import Skill
from app.models.system.agent_assignment import SystemAgentAssignment
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.model_capability_lookup import resolve_runtime_model_capabilities

logger = get_logger(__name__)


class RuntimeInventoryService:
    """Build an API/CLI ready runtime capability manifest."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._context_assembler = get_context_assembler()

    async def build_manifest(
        self,
        *,
        scope: Any = "runtime",
        tenant_id: int | None = None,
        agent_id: int | None = None,
        agent_code: str | None = None,
    ) -> dict[str, Any]:
        return await self.get_manifest(
            scope=scope,
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=agent_code,
        )

    async def get_manifest(
        self,
        *,
        scope: Any = "runtime",
        tenant_id: int | None = None,
        agent_id: int | None = None,
        agent_code: str | None = None,
    ) -> dict[str, Any]:
        scope_label = self._normalize_scope_label(scope)
        agent = await self._resolve_agent(
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=agent_code,
        )
        if agent is None:
            return self._build_empty_manifest(
                scope=scope_label,
                tenant_id=tenant_id,
                agent_code=agent_code,
            )

        kb_bindings = await self._load_kb_bindings(
            tenant_id=tenant_id,
            agent_id=agent.id,
        )
        runtime_caps = await resolve_runtime_model_capabilities(model=agent.model)
        skill_result = await self._load_skill_result(agent.id)

        request = SimpleNamespace(
            tenant_id=tenant_id,
            user_id=None,
            memory_enabled=bool(getattr(agent, "memory_enabled", False)),
            long_term_memory_enabled=False,
            memory_scene="conversation",
            memory_channel="session",
            memory_source="conversation",
            page_context=None,
        )
        kb_ids = [
            int(binding["knowledge_base_id"])
            for binding in kb_bindings
            if binding.get("knowledge_base_id") is not None
            and not bool(binding.get("platform_suppressed"))
            and bool(binding.get("enabled", True))
        ]
        requested_kb_ids = [
            int(binding["knowledge_base_id"])
            for binding in kb_bindings
            if binding.get("knowledge_base_id") is not None
        ]
        dropped_kb_ids = [
            int(binding["knowledge_base_id"])
            for binding in kb_bindings
            if binding.get("knowledge_base_id") is not None
            and bool(binding.get("platform_suppressed"))
        ]
        state = ContextAssemblerState(
            knowledge_base_ids=kb_ids,
            requested_knowledge_base_ids=requested_kb_ids,
            dropped_knowledge_base_ids=dropped_kb_ids,
            rag_sources=[],
            rag_source_kinds=["bound_knowledge_base"] if kb_ids else [],
            memory_recalled=False,
            memory_recall_slice={},
            runtime_model_capabilities=runtime_caps,
        )
        bundle = await self._context_assembler.assemble_bundle(
            agent=agent,
            request=request,
            skill_result=skill_result,
            state=state,
            intent_plan=None,
        )
        manifest = AIRuntimeInventoryService.build_manifest(
            agent=agent,
            request=request,
            bundle=bundle,
            state=state,
            capability_injection_decision={
                "decision": "runtime_inventory_snapshot",
                "scope": scope_label,
                "all_shortcircuit": False,
            },
        )
        return self._shape_manifest_payload(
            scope=scope_label,
            tenant_id=tenant_id,
            agent=agent,
            manifest=manifest,
            kb_bindings=kb_bindings,
            skill_result=skill_result,
            tools=bundle.tools,
        )

    @staticmethod
    def _normalize_scope_label(scope: Any) -> str:
        if isinstance(scope, str):
            text = scope.strip()
            return text or "runtime"
        scope_name = type(scope).__name__.lower()
        if "runtimecliscope" in scope_name:
            return "cli"
        return "runtime"

    async def _resolve_agent(
        self,
        *,
        tenant_id: int | None,
        agent_id: int | None,
        agent_code: str | None,
    ) -> Agent | None:
        if agent_id is not None:
            agent = await self._load_agent_by_id(int(agent_id))
            if agent is None:
                raise NotFoundException(message=_("agent.error.not_found"))
            return agent

        normalized_code = str(agent_code or "").strip()
        if not normalized_code:
            return None

        assignment_agent = await self._resolve_agent_by_feature_code(
            tenant_id=tenant_id,
            feature_code=normalized_code,
        )
        if assignment_agent is not None:
            return assignment_agent

        stmt: Select[tuple[Agent]] = self._agent_query().where(
            Agent.name == normalized_code,
            Agent.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt.limit(1))
        agent = result.scalar_one_or_none()
        if agent is not None:
            return agent

        raise NotFoundException(message=_("agent.error.not_found"))

    async def _resolve_agent_by_feature_code(
        self,
        *,
        tenant_id: int | None,
        feature_code: str,
    ) -> Agent | None:
        stmt = (
            select(SystemAgentAssignment.agent_id)
            .where(
                SystemAgentAssignment.feature_code == feature_code,
                SystemAgentAssignment.is_deleted.is_(False),
                SystemAgentAssignment.is_active.is_(True),
                SystemAgentAssignment.agent_id.isnot(None),
            )
            .order_by(SystemAgentAssignment.tenant_id.is_(None))
        )
        if tenant_id is None:
            stmt = stmt.where(SystemAgentAssignment.tenant_id.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    SystemAgentAssignment.tenant_id == tenant_id,
                    SystemAgentAssignment.tenant_id.is_(None),
                )
            )
        result = await self.db.execute(stmt.limit(1))
        agent_id = result.scalar_one_or_none()
        if agent_id is None:
            return None
        return await self._load_agent_by_id(int(agent_id))

    def _agent_query(self) -> Select[tuple[Agent]]:
        return select(Agent).options(
            selectinload(Agent.model).selectinload(AIModel.provider),
        )

    async def _load_agent_by_id(self, agent_id: int) -> Agent | None:
        result = await self.db.execute(
            self._agent_query().where(
                Agent.id == agent_id,
                Agent.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _load_skill_result(self, agent_id: int) -> SkillResolveResult:
        stmt = (
            select(AgentSkillGrant)
            .options(
                selectinload(AgentSkillGrant.skill).selectinload(Skill.package)
            )
            .where(
                AgentSkillGrant.agent_id == agent_id,
                AgentSkillGrant.is_deleted.is_(False),
                AgentSkillGrant.enabled.is_(True),
            )
            .order_by(AgentSkillGrant.sort_order, AgentSkillGrant.id)
        )
        result = await self.db.execute(stmt)
        grants = list(result.scalars().all())

        skills: list[Skill] = []
        overrides: dict[int, dict[str, Any]] = {}
        for grant in grants:
            skill = grant.skill
            if skill is None or bool(getattr(skill, "is_deleted", False)):
                continue
            skills.append(skill)
            if isinstance(grant.config_override, dict) and skill.id is not None:
                overrides[int(skill.id)] = dict(grant.config_override)

        if not skills:
            return SkillResolveResult()
        return await SkillResolver(self.db).resolve(
            skills,
            config_overrides=overrides,
        )

    async def _load_kb_bindings(
        self,
        *,
        tenant_id: int | None,
        agent_id: int,
    ) -> list[dict[str, Any]]:
        service = AgentKBBindingService(self.db, tenant_id)
        return await service.get_agent_kb_bindings_with_metadata(
            agent_id,
            merge_platform_bindings=tenant_id is not None,
        )

    @staticmethod
    def _provider_payload(provider: AIProvider | None) -> dict[str, Any]:
        if provider is None:
            return {
                "id": None,
                "code": None,
                "name": None,
                "type": None,
                "status": "unavailable",
                "reason": "provider_not_selected",
            }
        status = "available" if bool(provider.is_active) else "degraded"
        return {
            "id": provider.id,
            "code": provider.code,
            "name": provider.name,
            "type": provider.type,
            "status": status,
            "reason": None if status == "available" else "provider_inactive",
        }

    @staticmethod
    def _model_payload(
        model: AIModel | None,
        runtime_caps: dict[str, Any],
    ) -> dict[str, Any]:
        if model is None:
            return {
                "id": None,
                "code": None,
                "name": None,
                "type": None,
                "status": "unavailable",
                "reason": "model_not_selected",
            }
        status = "available" if bool(model.is_active) else "degraded"
        payload = {
            "id": model.id,
            "code": model.code,
            "name": model.name,
            "type": model.type,
            "status": status,
            "reason": None if status == "available" else "model_inactive",
            "context_window": model.context_window,
            "max_output_tokens": model.max_output_tokens,
        }
        for key in (
            "supports_function_calling",
            "supports_streaming",
            "supports_vision",
            "supports_audio",
            "supports_video",
        ):
            if key in runtime_caps:
                payload[key] = runtime_caps[key]
        return payload

    @staticmethod
    def _build_knowledge_base_items(
        kb_bindings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for binding in kb_bindings:
            kb_id = binding.get("knowledge_base_id")
            if kb_id is None:
                continue
            suppressed = bool(binding.get("platform_suppressed"))
            enabled = bool(binding.get("enabled", True))
            if suppressed:
                status = "degraded"
                reason = "platform_binding_suppressed"
            elif enabled:
                status = "available"
                reason = None
            else:
                status = "unavailable"
                reason = "binding_disabled"
            items.append(
                {
                    "name": str(binding.get("kb_name") or f"knowledge_base:{kb_id}"),
                    "kind": "context_provider",
                    "status": status,
                    "reason": reason,
                    "metadata": {
                        "knowledge_base_id": int(kb_id),
                        "binding_scope": binding.get("binding_scope"),
                        "scope": binding.get("kb_scope"),
                        "document_count": int(binding.get("kb_document_count") or 0),
                        "owner_tenant_id": binding.get("kb_owner_tenant_id"),
                        "owner_tenant_name": binding.get("kb_owner_tenant_name"),
                    },
                    "source": "agent_kb_binding",
                }
            )
        if items:
            return items
        return [
            {
                "name": "knowledge_base",
                "kind": "context_provider",
                "status": "unavailable",
                "reason": "no_effective_knowledge_base_binding",
                "metadata": {},
                "source": "agent_kb_binding",
            }
        ]

    @staticmethod
    def _build_extension_items(
        *,
        tools: list[ToolDefinition],
        skill_result: SkillResolveResult,
    ) -> list[dict[str, Any]]:
        extensions: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "tool_names": [],
                "skill_names": [],
                "package_names": [],
            }
        )

        for tool in tools:
            plugin_name = str(getattr(tool, "source_plugin", "") or "").strip()
            if not plugin_name:
                continue
            bucket = extensions[plugin_name]
            tool_name = str(getattr(tool, "name", "") or "").strip()
            if tool_name and tool_name not in bucket["tool_names"]:
                bucket["tool_names"].append(tool_name)
            package_name = str(getattr(tool, "source_package_name", "") or "").strip()
            if package_name and package_name not in bucket["package_names"]:
                bucket["package_names"].append(package_name)
            skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
            if skill_name and skill_name not in bucket["skill_names"]:
                bucket["skill_names"].append(skill_name)

        for descriptor in skill_result.capability_descriptors or []:
            metadata = dict(descriptor.metadata or {})
            plugin_name = str(metadata.get("source_plugin") or "").strip()
            if not plugin_name:
                continue
            bucket = extensions[plugin_name]
            skill_name = str(descriptor.name or "").strip()
            if skill_name and skill_name not in bucket["skill_names"]:
                bucket["skill_names"].append(skill_name)
            package_name = str(metadata.get("package_name") or "").strip()
            if package_name and package_name not in bucket["package_names"]:
                bucket["package_names"].append(package_name)

        return [
            {
                "name": plugin_name,
                "kind": "extension",
                "status": "available",
                "reason": None,
                "metadata": {
                    "tool_names": sorted(bucket["tool_names"]),
                    "skill_names": sorted(bucket["skill_names"]),
                    "package_names": sorted(bucket["package_names"]),
                },
                "source": "plugin_runtime",
            }
            for plugin_name, bucket in sorted(extensions.items())
        ]

    def _shape_manifest_payload(
        self,
        *,
        scope: str,
        tenant_id: int | None,
        agent: Agent,
        manifest: Any,
        kb_bindings: list[dict[str, Any]],
        skill_result: SkillResolveResult,
        tools: list[ToolDefinition],
    ) -> dict[str, Any]:
        payload = manifest.to_dict()
        runtime_caps = dict(payload.get("runtime_model_capabilities") or {})
        provider = getattr(getattr(agent, "model", None), "provider", None)
        payload["scope"] = scope
        payload["tenant_id"] = tenant_id
        payload["provider"] = self._provider_payload(provider)
        payload["model"] = self._model_payload(getattr(agent, "model", None), runtime_caps)
        payload["knowledge_bases"] = self._build_knowledge_base_items(kb_bindings)
        payload["extensions"] = self._build_extension_items(
            tools=tools,
            skill_result=skill_result,
        )

        summary = AIRuntimeInventoryService.build_compact_summary(manifest)
        summary.update(
            {
                "tool_count": len(payload.get("tools") or []),
                "skill_count": len(payload.get("skills") or []),
                "knowledge_base_count": len(
                    [
                        item
                        for item in (payload.get("knowledge_bases") or [])
                        if item.get("status") == "available"
                    ]
                ),
                "knowledge_base_names": [
                    item.get("name")
                    for item in (payload.get("knowledge_bases") or [])
                    if item.get("status") == "available"
                ],
                "extension_names": [
                    item.get("name")
                    for item in (payload.get("extensions") or [])
                ],
                "disabled_capability_names": [
                    item.get("name")
                    for item in (payload.get("disabled_capabilities") or [])
                ],
                "page_context_available": any(
                    item.get("status") == "available"
                    for item in (payload.get("page_context") or [])
                ),
                "web_research_status": next(
                    (
                        str(item.get("status"))
                        for item in (payload.get("web_research") or [])
                        if str(item.get("name") or "").strip() == "web_research"
                    ),
                    "unavailable",
                ),
                "agent_name": str(getattr(agent, "name", "") or "").strip() or None,
                "agent_owner_tenant_id": getattr(agent, "owner_tenant_id", None),
                "manifest_version": payload.get("manifest_version"),
            }
        )
        payload["summary"] = summary
        payload.setdefault("boundaries", {})
        payload["boundaries"]["scope_context"] = scope
        return payload

    @staticmethod
    def _build_empty_manifest(
        *,
        scope: str,
        tenant_id: int | None,
        agent_code: str | None,
    ) -> dict[str, Any]:
        return {
            "scope": scope,
            "tenant_id": tenant_id,
            "agent_id": None,
            "provider": {
                "id": None,
                "code": None,
                "name": None,
                "type": None,
                "status": "unavailable",
                "reason": "agent_not_selected",
            },
            "model": {
                "id": None,
                "code": None,
                "name": None,
                "type": None,
                "status": "unavailable",
                "reason": "agent_not_selected",
            },
            "runtime_model_capabilities": {},
            "tools": [],
            "skills": [],
            "knowledge_bases": [
                {
                    "name": "knowledge_base",
                    "kind": "context_provider",
                    "status": "unavailable",
                    "reason": "agent_not_selected",
                    "metadata": {},
                    "source": "agent_kb_binding",
                }
            ],
            "memory": [
                {
                    "name": "memory",
                    "kind": "context_provider",
                    "status": "unavailable",
                    "reason": "agent_not_selected",
                    "metadata": {},
                    "source": "request.flags",
                }
            ],
            "page_context": [
                {
                    "name": "page_context",
                    "kind": "context_provider",
                    "status": "unavailable",
                    "reason": "page_context_not_attached",
                    "metadata": {},
                    "source": "request.page_context",
                }
            ],
            "web_research": [
                {
                    "name": "web_research",
                    "kind": "execution_tool",
                    "status": "unavailable",
                    "reason": "agent_not_selected",
                    "metadata": {},
                    "source": "tool_registry",
                }
            ],
            "extensions": [],
            "disabled_capabilities": [
                {
                    "name": "agent_resolution",
                    "kind": "context_provider",
                    "status": "degraded",
                    "reason": "agent_not_selected",
                    "metadata": {"agent_code": agent_code},
                    "source": "runtime_inventory",
                }
            ],
            "boundaries": {
                "scope_context": scope,
                "write_operations_require_confirmation": True,
            },
            "sources": [],
            "manifest_version": "runtime-capability-manifest/v1",
            "summary": {
                "selected_skill_names": [],
                "context_line": "",
                "context_source_kinds": [],
                "tool_families": [],
                "page_operation_names": [],
                "page_context_attached": False,
                "web_research_pair_complete": False,
                "continuation_capable_families": [],
                "knowledge_base_hint": False,
                "page_context_hint": False,
                "memory_hint": False,
                "provider": None,
                "model": None,
                "tool_count": 0,
                "skill_count": 0,
                "knowledge_base_count": 0,
                "knowledge_base_names": [],
                "extension_names": [],
                "disabled_capability_names": ["agent_resolution"],
                "page_context_available": False,
                "web_research_status": "unavailable",
                "agent_name": None,
                "manifest_version": "runtime-capability-manifest/v1",
            },
        }


__all__ = ["RuntimeInventoryService"]
