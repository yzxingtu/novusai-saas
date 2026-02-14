"""
租户 AI 模型速率限制配置 Repository
"""

from typing import List
from sqlalchemy import select, and_

from app.models.ai import TenantModelRateLimit
from app.core.base_repository import TenantRepository


class TenantModelRateLimitRepository(TenantRepository[TenantModelRateLimit]):
    """
    租户 AI 模型速率限制配置 Repository
    """

    model = TenantModelRateLimit

    async def get_by_tenant_and_model(
        self,
        tenant_id: int,
        model_id: int
    ) -> TenantModelRateLimit | None:
        """
        获取租户对指定模型的速率限制配置
        """
        stmt = select(TenantModelRateLimit).where(
            and_(
                TenantModelRateLimit.tenant_id == tenant_id,
                TenantModelRateLimit.model_id == model_id,
                TenantModelRateLimit.is_deleted.is_(False),
            )
        )
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_limits(
        self,
        tenant_id: int,
        model_id: int | None = None
    ) -> List[TenantModelRateLimit]:
        """
        获取租户所有激活的速率限制配置
        """
        conditions = [
            TenantModelRateLimit.tenant_id == tenant_id,
            TenantModelRateLimit.is_active.is_(True),
            TenantModelRateLimit.is_deleted.is_(False),
        ]

        if model_id:
            conditions.append(TenantModelRateLimit.model_id == model_id)

        stmt = select(TenantModelRateLimit).where(
            and_(*conditions)
        ).order_by(TenantModelRateLimit.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


__all__ = ["TenantModelRateLimitRepository"]
