"""
企业 AI 模型速率限制 Repository / Tenant AI Rate Limit Repository
"""


from sqlalchemy import and_, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.models.ai import TenantModelRateLimit


class AdminTenantModelRateLimitRepository(BaseRepository[TenantModelRateLimit]):
    """
    平台端企业模型速率限制 Repository（跨企业）/
    Platform tenant model rate-limit repository (cross-tenant).
    """

    model = TenantModelRateLimit


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
        ).order_by(TenantModelRateLimit.created_at.desc())

        result = await self.db.execute(stmt)
        return result.scalars().first()

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

    async def get_latest_active_limit(
        self,
        tenant_id: int,
        model_id: int,
    ) -> TenantModelRateLimit | None:
        """
        获取同 tenant + model 下最新激活限速规则 /
        Get latest active rate-limit rule for the same tenant + model.
        """
        stmt = select(TenantModelRateLimit).where(
            and_(
                TenantModelRateLimit.tenant_id == tenant_id,
                TenantModelRateLimit.model_id == model_id,
                TenantModelRateLimit.is_active.is_(True),
                TenantModelRateLimit.is_deleted.is_(False),
            )
        ).order_by(TenantModelRateLimit.created_at.desc())

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def has_active_conflict(
        self,
        tenant_id: int,
        model_id: int,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查同 tenant + model 是否已有其他激活限速规则 /
        Check whether another active rate-limit rule exists for the same tenant + model.
        """
        conditions = [
            TenantModelRateLimit.tenant_id == tenant_id,
            TenantModelRateLimit.model_id == model_id,
            TenantModelRateLimit.is_active.is_(True),
            TenantModelRateLimit.is_deleted.is_(False),
        ]
        if exclude_id is not None:
            conditions.append(TenantModelRateLimit.id != exclude_id)

        stmt = select(TenantModelRateLimit.id).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = [
    "TenantModelRateLimitRepository",
    "AdminTenantModelRateLimitRepository",
]
