"""
AI 表策略租户覆盖 Repository / AI Table Policy Override Repository
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.base_repository import TenantRepository
from app.models.ai.table_policy import AITablePolicyOverride


class AITablePolicyOverrideRepository(TenantRepository[AITablePolicyOverride]):
    """AI 表策略租户覆盖仓库"""

    model = AITablePolicyOverride

    async def get_by_policy_id(self, policy_id: int) -> AITablePolicyOverride | None:
        """按 policy_id + tenant_id 查找覆盖"""
        stmt = select(AITablePolicyOverride).where(
            AITablePolicyOverride.policy_id == policy_id,
            AITablePolicyOverride.tenant_id == self.tenant_id,
            AITablePolicyOverride.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_policy_and_tenant(
        self, policy_id: int, tenant_id: int,
    ) -> AITablePolicyOverride | None:
        """按 policy_id + tenant_id 查找覆盖（不依赖 self.tenant_id）"""
        stmt = select(AITablePolicyOverride).where(
            AITablePolicyOverride.policy_id == policy_id,
            AITablePolicyOverride.tenant_id == tenant_id,
            AITablePolicyOverride.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_for_tenant(self) -> list[AITablePolicyOverride]:
        """获取当前租户的所有覆盖"""
        stmt = select(AITablePolicyOverride).where(
            AITablePolicyOverride.tenant_id == self.tenant_id,
            AITablePolicyOverride.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["AITablePolicyOverrideRepository"]
