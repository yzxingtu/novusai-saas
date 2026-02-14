"""
AI 表策略租户覆盖 Repository
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.table_policy import AITablePolicyOverride
from app.core.base_repository import TenantRepository


class AITablePolicyOverrideRepository(TenantRepository[AITablePolicyOverride]):
    """AI 表策略租户覆盖仓库"""

    model = AITablePolicyOverride

    async def get_by_policy_id(self, policy_id: int) -> AITablePolicyOverride | None:
        """按 policy_id + tenant_id 查找覆盖"""
        stmt = self._base_query().where(
            AITablePolicyOverride.policy_id == policy_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_for_tenant(self) -> list[AITablePolicyOverride]:
        """获取当前租户的所有覆盖"""
        stmt = self._base_query()
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["AITablePolicyOverrideRepository"]
