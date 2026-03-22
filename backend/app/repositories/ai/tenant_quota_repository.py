"""
企业 AI 配额 Repository / Tenant AI Quota Repository
"""


from sqlalchemy import and_, or_, select

from app.core.base_repository import BaseRepository, TenantRepository
from app.enums.ai import QuotaPeriodEnum
from app.models.ai import TenantQuota


class AdminTenantQuotaRepository(BaseRepository[TenantQuota]):
    """
    平台端 AI 配额配置 Repository（跨企业）/ Platform AI quota config repository (cross-tenant).

    用于平台管理员查看所有企业的配额配置
    """
    model = TenantQuota


class TenantQuotaRepository(TenantRepository[TenantQuota]):
    """
    企业 AI 配额配置 Repository / Tenant AI quota config repository.
    """

    model = TenantQuota

    async def get_by_tenant_and_model(
        self,
        tenant_id: int,
        model_id: int | None = None,
        period: str = "monthly"
    ) -> TenantQuota | None:
        """
        获取企业对指定模型的配额配置 / Get tenant quota config for model.

        Args:
            tenant_id: 企业 ID
            model_id: 模型 ID（None 表示全局配额）
            period: 周期（daily/monthly）

        Returns:
            TenantQuota 实例
        """
        conditions = [
            TenantQuota.tenant_id == tenant_id,
            TenantQuota.period == period,
            TenantQuota.is_deleted.is_(False),
        ]
        if model_id is None:
            conditions.append(TenantQuota.model_id.is_(None))
        else:
            conditions.append(TenantQuota.model_id == model_id)

        stmt = select(TenantQuota).where(
            and_(*conditions)
        ).order_by(TenantQuota.created_at.desc())

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_active_quotas(
        self,
        tenant_id: int,
        period: str | None = None
    ) -> list[TenantQuota]:
        """
        获取企业所有激活的配额配置 / Get all active quota configs for tenant.

        Args:
            tenant_id: 企业 ID
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
        获取企业对指定模型的激活配额配置（按创建时间倒序取最新）/ Get active quota config for tenant+model (latest by created_at).

        Args:
            tenant_id: 企业 ID
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
        return result.scalars().first()

    async def get_effective_quotas(
        self,
        tenant_id: int,
        model_id: int,
    ) -> list[TenantQuota]:
        """
        获取运行时生效配额（按周期分别选择：模型专属优先，否则回退到全局）/
        Get runtime effective quotas by period (model-specific first, otherwise global fallback).
        """
        stmt = select(TenantQuota).where(
            and_(
                TenantQuota.tenant_id == tenant_id,
                TenantQuota.is_active.is_(True),
                TenantQuota.is_deleted.is_(False),
                or_(
                    TenantQuota.model_id == model_id,
                    TenantQuota.model_id.is_(None),
                ),
            )
        ).order_by(TenantQuota.created_at.desc())

        result = await self.db.execute(stmt)
        quotas = list(result.scalars().all())

        specific: dict[str, TenantQuota] = {}
        global_rules: dict[str, TenantQuota] = {}

        for quota in quotas:
            target = specific if quota.model_id == model_id else global_rules
            target.setdefault(quota.period, quota)

        effective: list[TenantQuota] = []
        for period in (
            QuotaPeriodEnum.DAILY.value,
            QuotaPeriodEnum.MONTHLY.value,
        ):
            quota = specific.get(period) or global_rules.get(period)
            if quota is not None:
                effective.append(quota)

        return effective

    async def get_latest_active_scope_quota(
        self,
        tenant_id: int,
        model_id: int | None,
        period: str,
    ) -> TenantQuota | None:
        """
        获取同 scope + period 下最新激活规则 / Get latest active rule in the same scope + period.
        """
        conditions = [
            TenantQuota.tenant_id == tenant_id,
            TenantQuota.period == period,
            TenantQuota.is_active.is_(True),
            TenantQuota.is_deleted.is_(False),
        ]
        if model_id is None:
            conditions.append(TenantQuota.model_id.is_(None))
        else:
            conditions.append(TenantQuota.model_id == model_id)

        stmt = select(TenantQuota).where(and_(*conditions)).order_by(
            TenantQuota.created_at.desc()
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def has_active_conflict(
        self,
        tenant_id: int,
        model_id: int | None,
        period: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查同 tenant + scope + period 是否已有其他激活规则 /
        Check whether another active rule already exists in the same tenant + scope + period.
        """
        conditions = [
            TenantQuota.tenant_id == tenant_id,
            TenantQuota.period == period,
            TenantQuota.is_active.is_(True),
            TenantQuota.is_deleted.is_(False),
        ]
        if model_id is None:
            conditions.append(TenantQuota.model_id.is_(None))
        else:
            conditions.append(TenantQuota.model_id == model_id)
        if exclude_id is not None:
            conditions.append(TenantQuota.id != exclude_id)

        stmt = select(TenantQuota.id).where(and_(*conditions)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = ["TenantQuotaRepository", "AdminTenantQuotaRepository"]
