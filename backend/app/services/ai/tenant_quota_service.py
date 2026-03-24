"""
企业 AI 配额配置 Service / Tenant AI Quota Service
"""

from datetime import date
from typing import Any

from app.ai.quota import UsageTracker
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import QuotaPeriodEnum, QuotaTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import TenantQuota
from app.repositories.ai.tenant_quota_repository import TenantQuotaRepository

logger = LogManager.get_logger("ai.quota_service")


class TenantQuotaService(TenantService[TenantQuota, TenantQuotaRepository]):
    """
    企业 AI 配额配置 Service / Tenant AI quota service.
    """

    model = TenantQuota
    repository_class = TenantQuotaRepository

    async def get_quota(
        self,
        model_id: int | None = None,
        period: str = QuotaPeriodEnum.MONTHLY.value
    ) -> TenantQuota | None:
        """
        获取企业配额配置 / Get tenant quota config.

        Args:
            model_id: 模型 ID（None 表示全局配额）
            period: 周期（daily/monthly）

        Returns:
            TenantQuota 实例
        """
        return await self.repo.get_by_tenant_and_model(
            self.tenant_id, model_id, period
        )

    async def get_quota_with_usage(
        self,
        model_id: int | None = None,
        period: str = QuotaPeriodEnum.MONTHLY.value
    ) -> dict[str, Any] | None:
        """
        获取配额配置及当前使用量 / Get quota config and current usage.

        Args:
            model_id: 模型 ID（None 表示全局配额）
            period: 周期

        Returns:
            包含配额和使用量的字典
        """
        quota = await self.get_quota(model_id, period)

        if not quota:
            return None

        usage = await UsageTracker.get_usage(
            tenant_id=self.tenant_id,
            model_id=model_id or 0,
            period=period,
        )

        # 计算使用百分比 / Compute usage percent
        usage_percent = (usage / quota.limit * 100) if quota.limit > 0 else 0

        # 判断是否达到预警阈值 / Check warning threshold reached
        warning_threshold = quota.warning_threshold or 80
        is_exceeded = usage_percent >= 100
        is_warning = usage_percent >= warning_threshold and not is_exceeded

        return {
            "quota": quota,
            "usage": usage,
            "limit": quota.limit,
            "usage_percent": round(usage_percent, 2),
            "is_warning": is_warning,
            "is_exceeded": is_exceeded,
            "remaining": max(0, quota.limit - usage),
        }

    async def get_all_quotas_with_usage(
        self,
        period: str | None = None
    ) -> list[dict[str, Any]]:
        """
        获取企业所有配额配置及使用量 / Get all tenant quotas with usage.

        Args:
            period: 周期（None 表示全部）

        Returns:
            配额及使用量列表
        """
        quotas = await self.repo.get_active_quotas(self.tenant_id, period)

        result = []
        for quota in quotas:
            quota_with_usage = await self.get_quota_with_usage(
                quota.model_id, quota.period
            )
            if quota_with_usage:
                result.append(quota_with_usage)

        return result

    async def check_quota_warning(
        self,
        model_id: int | None = None,
        period: str = QuotaPeriodEnum.MONTHLY.value
    ) -> dict[str, Any]:
        """
        检查配额预警状态 / Check quota warning status.

        Args:
            model_id: 模型 ID
            period: 周期

        Returns:
            预警状态信息
        """
        quota_with_usage = await self.get_quota_with_usage(model_id, period)

        if not quota_with_usage:
            return {"has_warning": False}

        return {
            "has_warning": quota_with_usage["is_warning"],
            "is_exceeded": quota_with_usage["is_exceeded"],
            "usage_percent": quota_with_usage["usage_percent"],
            "warning_threshold": quota_with_usage["quota"].warning_threshold or 80,
            "quota_type": quota_with_usage["quota"].quota_type,
        }

    async def get_active_quotas(
        self,
        period: str | None = None,
    ) -> list[TenantQuota]:
        """
        获取企业活跃配额列表 / Get active quota list for tenant.

        Args:
            period: 周期过滤（可选）

        Returns:
            TenantQuota 列表
        """
        return await self.repo.get_active_quotas(
            tenant_id=self.tenant_id,
            period=period,
        )

    async def create_quota(
        self,
        model_id: int | None,
        period: str,
        limit: int,
        quota_type: str = QuotaTypeEnum.SOFT.value,
        warning_threshold: int | None = None,
        description: str | None = None
    ) -> TenantQuota:
        """
        创建配额配置 / Create quota config.

        Args:
            model_id: 模型 ID
            period: 周期
            limit: 限制
            quota_type: 配额类型
            warning_threshold: 预警阈值
            description: 描述

        Returns:
            创建的 TenantQuota 实例
        """
        data = {
            "model_id": model_id,
            "period": period,
            "limit": limit,
            "quota_type": quota_type,
            "warning_threshold": warning_threshold or 80,
            "description": description,
        }

        quota = await self.create(data)

        logger.info(
            "Quota created: tenant_id={} model_id={} period={} limit={}",
            self.tenant_id, model_id, period, limit,
        )

        return quota

    async def _before_create(self, data: dict[str, Any]) -> None:
        await super()._before_create(data)
        is_active = data.get("is_active", True)
        if not is_active:
            return

        model_id = data.get("model_id")
        period = str(data.get("period", QuotaPeriodEnum.MONTHLY.value))
        has_conflict = await self.repo.has_active_conflict(
            tenant_id=self.tenant_id,
            model_id=model_id,
            period=period,
        )
        if has_conflict:
            raise BusinessException(message=_("ai.error.quota_duplicate_active"))

    async def _before_update(self, id: int, data: dict[str, Any]) -> None:
        await super()._before_update(id, data)
        current = await self.repo.get_by_id(id)
        if current is None:
            raise NotFoundException(message=_("ai.error.quota_not_found"))

        next_active = bool(data.get("is_active", current.is_active))
        if not next_active:
            return

        next_model_id = data.get("model_id", current.model_id)
        next_period = str(data.get("period", current.period))
        has_conflict = await self.repo.has_active_conflict(
            tenant_id=self.tenant_id,
            model_id=next_model_id,
            period=next_period,
            exclude_id=id,
        )
        if has_conflict:
            raise BusinessException(message=_("ai.error.quota_duplicate_active"))


__all__ = ["TenantQuotaService"]
