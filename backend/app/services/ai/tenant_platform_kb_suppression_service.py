"""
企业停用平台知识库 Service / Tenant platform KB suppression for RAG opt-out
"""

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_kb_binding_repository import AgentKBBindingRepository
from app.repositories.ai.agent_repository import AgentRepository
from app.repositories.ai.tenant_agent_platform_kb_suppression_repository import (
    TenantAgentPlatformKbSuppressionRepository,
)

logger = LogManager.get_logger("ai")


class TenantPlatformKbSuppressionService:
    """本企业对平台智能体全局知识库的 RAG 停用 / Per-tenant opt-out from platform KB."""

    def __init__(self, db, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        self.repo = TenantAgentPlatformKbSuppressionRepository(db, tenant_id)
        self.agent_repo = AgentRepository(db, tenant_id)
        # 全局绑定查询不依赖 tenant 过滤 / Global binding lookup uses raw db
        self._global_binding_repo = AgentKBBindingRepository(db, tenant_id)

    async def list_suppressed_kb_ids(self, agent_id: int) -> set[int]:
        return await self.repo.list_active_kb_ids(agent_id)

    async def _ensure_platform_agent_accessible(self, agent_id: int):
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.owner_tenant_id is not None:
            raise BusinessException(
                message=_("agent_kb_binding.error.platform_suppress_platform_agent_only")
            )
        if agent.scope == ResourceScopeEnum.ADMIN_ONLY.value:
            raise BusinessException(
                message=_("agent_kb_binding.error.platform_suppress_platform_agent_only")
            )
        return agent

    async def suppress(self, agent_id: int, knowledge_base_id: int) -> dict:
        """
        本企业停用某平台全局知识库（RAG 不再使用）/ Suppress platform KB for this tenant.
        """
        await self._ensure_platform_agent_accessible(agent_id)
        if not await self._global_binding_repo.has_platform_global_binding(
            agent_id, knowledge_base_id
        ):
            raise BusinessException(
                message=_("agent_kb_binding.error.platform_suppress_not_global_binding")
            )

        existing = await self.repo.get_any_row(agent_id, knowledge_base_id)
        if existing:
            if not existing.is_deleted:
                return {"id": existing.id, "knowledge_base_id": knowledge_base_id}
            existing.restore()
            await self.db.flush()
            await self.db.refresh(existing)
            logger.info(
                "Restored platform KB suppression tenant={} agent={} kb={}",
                self.tenant_id, agent_id, knowledge_base_id,
            )
            return {"id": existing.id, "knowledge_base_id": knowledge_base_id}

        row = await self.repo.create({
            "agent_id": agent_id,
            "knowledge_base_id": knowledge_base_id,
        })
        await self.db.flush()
        logger.info(
            "Platform KB suppressed tenant={} agent={} kb={}",
            self.tenant_id, agent_id, knowledge_base_id,
        )
        return {"id": row.id, "knowledge_base_id": knowledge_base_id}

    async def unsuppress(self, agent_id: int, knowledge_base_id: int) -> None:
        """取消停用（重新参与 RAG）/ Remove suppression."""
        await self._ensure_platform_agent_accessible(agent_id)
        row = await self.repo.get_active_row(agent_id, knowledge_base_id)
        if not row:
            raise NotFoundException(
                message=_("agent_kb_binding.error.platform_suppression_not_found")
            )
        row.soft_delete(level="tenant")
        await self.db.flush()
        logger.info(
            "Platform KB unsuppressed tenant={} agent={} kb={}",
            self.tenant_id, agent_id, knowledge_base_id,
        )


async def load_suppressed_platform_kb_ids(
    db,
    tenant_id: int,
    agent_id: int,
) -> set[int]:
    """供 RAG 使用：查询停用集合 / For RAG injector."""
    repo = TenantAgentPlatformKbSuppressionRepository(db, tenant_id)
    return await repo.list_active_kb_ids(agent_id)


__all__ = [
    "TenantPlatformKbSuppressionService",
    "load_suppressed_platform_kb_ids",
]
