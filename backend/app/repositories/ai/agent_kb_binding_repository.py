"""
智能体知识库绑定 Repository / Agent KB Binding Repository
"""

from sqlalchemy import and_, delete, or_, select

from app.core.base_repository import TenantRepository
from app.models.ai.agent_kb_binding import AgentKnowledgeBaseBinding


class AgentKBBindingRepository(TenantRepository[AgentKnowledgeBaseBinding]):
    """
    智能体知识库绑定 Repository / Agent-KB binding repository.

    - tenant 场景: tenant_id = 指定企业 / tenant: tenant_id = given tenant
    - admin/global 场景: tenant_id IS NULL / admin/global: tenant_id IS NULL
    """

    model = AgentKnowledgeBaseBinding

    def __init__(self, db, tenant_id: int | None):
        super().__init__(db, tenant_id)  # type: ignore[arg-type]

    def _tenant_filter(self):
        """构建 tenant_id 过滤条件（支持 NULL）。/ Build tenant_id filter (supports NULL)."""
        if self.tenant_id is None:
            return AgentKnowledgeBaseBinding.tenant_id.is_(None)
        return AgentKnowledgeBaseBinding.tenant_id == self.tenant_id

    async def get_by_agent_id(self, agent_id: int) -> list[AgentKnowledgeBaseBinding]:
        """
        获取指定智能体的所有知识库绑定（按 sort_order 排序） / Get all KB bindings for an agent (ordered by sort_order).
        """
        stmt = (
            select(AgentKnowledgeBaseBinding)
            .where(
                and_(
                    AgentKnowledgeBaseBinding.agent_id == agent_id,
                    self._tenant_filter(),
                    AgentKnowledgeBaseBinding.is_deleted.is_(False),
                )
            )
            .order_by(AgentKnowledgeBaseBinding.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def has_platform_global_binding(
        self, agent_id: int, knowledge_base_id: int
    ) -> bool:
        """是否存在平台全局绑定（tenant_id IS NULL）/ Platform-global binding exists."""
        stmt = (
            select(AgentKnowledgeBaseBinding.id)
            .where(
                and_(
                    AgentKnowledgeBaseBinding.agent_id == agent_id,
                    AgentKnowledgeBaseBinding.knowledge_base_id == knowledge_base_id,
                    AgentKnowledgeBaseBinding.tenant_id.is_(None),
                    AgentKnowledgeBaseBinding.is_deleted.is_(False),
                )
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_binding_any(
        self, agent_id: int, knowledge_base_id: int
    ) -> AgentKnowledgeBaseBinding | None:
        """
        任意 tenant 范围下是否存在 agent–KB 绑定（用于唯一性校验）/ Any-scope agent–KB binding lookup.
        """
        stmt = select(AgentKnowledgeBaseBinding).where(
            and_(
                AgentKnowledgeBaseBinding.agent_id == agent_id,
                AgentKnowledgeBaseBinding.knowledge_base_id == knowledge_base_id,
                AgentKnowledgeBaseBinding.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_merged_platform_and_tenant(
        self, agent_id: int, tenant_id: int
    ) -> list[AgentKnowledgeBaseBinding]:
        """
        平台全局绑定（tenant_id IS NULL）+ 指定企业的叠加绑定 / Platform + tenant overlay bindings.
        """
        stmt = (
            select(AgentKnowledgeBaseBinding)
            .where(
                and_(
                    AgentKnowledgeBaseBinding.agent_id == agent_id,
                    AgentKnowledgeBaseBinding.is_deleted.is_(False),
                    or_(
                        AgentKnowledgeBaseBinding.tenant_id.is_(None),
                        AgentKnowledgeBaseBinding.tenant_id == tenant_id,
                    ),
                )
            )
            .order_by(AgentKnowledgeBaseBinding.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_binding(
        self, agent_id: int, knowledge_base_id: int
    ) -> AgentKnowledgeBaseBinding | None:
        """
        获取指定 agent-kb 绑定 / Get the given agent-kb binding.
        """
        stmt = select(AgentKnowledgeBaseBinding).where(
            and_(
                AgentKnowledgeBaseBinding.agent_id == agent_id,
                AgentKnowledgeBaseBinding.knowledge_base_id == knowledge_base_id,
                self._tenant_filter(),
                AgentKnowledgeBaseBinding.is_deleted.is_(False),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_agent_id(self, agent_id: int) -> int:
        """
        删除指定智能体的所有知识库绑定（物理删除） / Delete all KB bindings for an agent (hard delete).
        """
        stmt = (
            delete(AgentKnowledgeBaseBinding)
            .where(
                and_(
                    AgentKnowledgeBaseBinding.agent_id == agent_id,
                    self._tenant_filter(),
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount


__all__ = ["AgentKBBindingRepository"]
