"""
Unified AI runtime inventory service / 统一 AI runtime 能力清单服务。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.runtime import (
    AIRuntimeInventoryService,
    ContextAssemblerState,
    get_context_assembler,
)
from app.ai.skills.resolver import SkillResolver, SkillResolveResult
from app.core.i18n import _
from app.core.logging import get_logger
from app.exceptions import NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.ai.model import AIModel
from app.models.ai.skill import Skill
from app.models.system.agent_assignment import SystemAgentAssignment
from app.services.ai.agent_kb_binding_service import AgentKBBindingService
from app.services.ai.model_capability_lookup import resolve_runtime_model_capabilities
from app.services.ai.runtime_inventory_service_support import (
    build_empty_manifest,
    shape_manifest_payload,
)

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
            return build_empty_manifest(
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
        return shape_manifest_payload(
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


__all__ = ["RuntimeInventoryService"]
