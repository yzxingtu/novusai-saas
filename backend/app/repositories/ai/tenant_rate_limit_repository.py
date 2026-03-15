"""
企业 AI 模型速率限制 Repository / Tenant AI Rate Limit Repository
"""


from sqlalchemy import and_, select

from app.core.base_repository import TenantRepository
from app.models.ai import TenantModelRateLimit


class TenantModelRateLimitRepository(TenantRepository[TenantModelRateLimit]):
    """
    企业 AI 模型速率限制配置 Repository / Tenant AI model rate limit config repository.
    """

    model = TenantModelRateLimit

    async def get_by_tenant_and_model(
        self,
        tenant_id: int,
        model_id: int
    ) -> TenantModelRateLimit | None:
        """
        获取企业对指定模型的速率限制配置 / Get rate limit config for tenant and model.
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
    ) -> list[TenantModelRateLimit]:
        """
        获取企业所有激活的速率限制配置 / Get all active rate limit configs for tenant.
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
