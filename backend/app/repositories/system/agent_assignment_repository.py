"""
系统智能体绑定仓储 / System Agent Assignment Repository

提供系统智能体绑定的数据访问操作
Provides system agent assignment data access operations.
"""

from sqlalchemy import select

from app.core.base_repository import BaseRepository
from app.models.system.agent_assignment import SystemAgentAssignment


class AgentAssignmentRepository(BaseRepository[SystemAgentAssignment]):
    """
    系统智能体绑定仓储
    """

    model = SystemAgentAssignment

    _scope_fields = {
        "admin": {
            "id", "feature_code", "feature_name", "tenant_id", "agent_id",
            "is_active", "created_at", "updated_at",
        },
    }

    # ==================== 全局默认查询 (tenant_id IS NULL) ====================

    async def get_by_feature_code(self, feature_code: str) -> SystemAgentAssignment | None:
        """按功能代码获取全局默认绑定"""
        stmt = (
            select(self.model)
            .where(self.model.feature_code == feature_code)
            .where(self.model.tenant_id.is_(None))
            .where(self.model.is_deleted.is_(False))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_feature_code(self, feature_code: str) -> SystemAgentAssignment | None:
        """获取启用的全局默认绑定"""
        stmt = (
            select(self.model)
            .where(self.model.feature_code == feature_code)
            .where(self.model.tenant_id.is_(None))
            .where(self.model.is_active.is_(True))
            .where(self.model.is_deleted.is_(False))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_global(self) -> list[SystemAgentAssignment]:
        """获取所有全局默认绑定"""
        stmt = (
            select(self.model)
            .where(self.model.tenant_id.is_(None))
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.feature_code)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ==================== 企业覆盖查询 ====================

    async def get_tenant_override(
        self, feature_code: str, tenant_id: int
    ) -> SystemAgentAssignment | None:
        """获取企业覆盖绑定"""
        stmt = (
            select(self.model)
            .where(self.model.feature_code == feature_code)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.is_deleted.is_(False))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_for_tenant(self, tenant_id: int) -> list[SystemAgentAssignment]:
        """获取企业的所有覆盖绑定"""
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .where(self.model.is_deleted.is_(False))
            .order_by(self.model.feature_code)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve_for_tenant(
        self, feature_code: str, tenant_id: int
    ) -> SystemAgentAssignment | None:
        """
        企业 resolve：先查企业覆盖，未找到则 fallback 到全局默认。

        当企业覆盖存在时直接返回（无论 is_active），让调用方根据
        is_active 决定行为。只有覆盖不存在时才 fallback 到全局默认。
        """
        override = await self.get_tenant_override(feature_code, tenant_id)
        if override:
            return override
        return await self.get_active_by_feature_code(feature_code)


__all__ = ["AgentAssignmentRepository"]
