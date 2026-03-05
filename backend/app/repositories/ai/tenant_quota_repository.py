"""
租户 AI 配额配置 Repository
"""


from sqlalchemy import and_, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.models.ai import TenantQuota


class AdminTenantQuotaRepository(BaseRepository[TenantQuota]):
    """
    平台端 AI 配额配置 Repository（跨租户）

    用于平台管理员查看所有租户的配额配置
    """
    model = TenantQuota


class TenantQuotaRepository(TenantRepository[TenantQuota]):
    """
    租户 AI 配额配置 Repository
    """

    model = TenantQuota

    async def get_by_tenant_and_model(
        self,
        tenant_id: int,
        model_id: int | None = None,
        period: str = "monthly"
    ) -> TenantQuota | None:
        """
        获取租户对指定模型的配额配置

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID（None 表示全局配额）
            period: 周期（daily/monthly）

        Returns:
            TenantQuota 实例
        """
        stmt = select(TenantQuota).where(
            and_(
                TenantQuota.tenant_id == tenant_id,
                TenantQuota.model_id == model_id,
                TenantQuota.period == period,
                TenantQuota.is_deleted.is_(False),
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_quotas(
        self,
        tenant_id: int,
        period: str | None = None
    ) -> list[TenantQuota]:
        """
        获取租户所有激活的配额配置

        Args:
            tenant_id: 租户 ID
            period: 周期（daily/monthly），None 表示全部

        Returns:
            TenantQuota 列表
        """
        conditions = [
            TenantQuota.tenant_id == tenant_id,
            TenantQuota.is_active.is_(True),
            TenantQuota.is_deleted.is_(False),
        ]

        if period:
            conditions.append(TenantQuota.period == period)

        stmt = select(TenantQuota).where(
            and_(*conditions)
        ).order_by(TenantQuota.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


    async def get_active_quota(
        self,
        tenant_id: int,
        model_id: int,
    ) -> TenantQuota | None:
        """
        获取租户对指定模型的激活配额配置（按创建时间倒序取最新）

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID

        Returns:
            TenantQuota 实例或 None
        """
        stmt = select(TenantQuota).where(
            and_(
                TenantQuota.tenant_id == tenant_id,
                TenantQuota.model_id == model_id,
                TenantQuota.is_active.is_(True),
                TenantQuota.is_deleted.is_(False),
            )
        ).order_by(TenantQuota.created_at.desc())

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["TenantQuotaRepository", "AdminTenantQuotaRepository"]
