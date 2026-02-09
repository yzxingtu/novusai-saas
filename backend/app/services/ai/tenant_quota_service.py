"""
租户 AI 配额配置 Service
"""

from typing import Optional, List, Dict, Any
from datetime import date

from app.repositories.ai.tenant_quota_repository import TenantQuotaRepository
from app.models.ai import TenantQuota
from app.core.base_service import TenantService
from app.core.i18n import _
from app.ai.quota import UsageTracker
from app.core.logging import LogManager


logger = LogManager.get_logger("ai.quota_service")


class TenantQuotaService(TenantService[TenantQuota, TenantQuotaRepository]):
    """
    租户 AI 配额配置 Service
    """

    model = TenantQuota
    repository_class = TenantQuotaRepository

    async def get_quota(
        self,
        model_id: Optional[int] = None,
        period: str = "monthly"
    ) -> Optional[TenantQuota]:
        """
        获取租户配额配置

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
        model_id: Optional[int] = None,
        period: str = "monthly"
    ) -> Optional[Dict[str, Any]]:
        """
        获取配额配置及当前使用量

        Args:
            model_id: 模型 ID（None 表示全局配额）
            period: 周期

        Returns:
            包含配额和使用量的字典
        """
        quota = await self.get_quota(model_id, period)

        if not quota:
            return None

        # 获取当前使用量
        if period == "daily":
            usage = await UsageTracker.get_daily_usage(self.tenant_id, model_id or 0)
        else:
            today = date.today()
            usage = await UsageTracker.get_monthly_usage(
                self.tenant_id, model_id or 0, today.year, today.month
            )

        # 计算使用百分比
        usage_percent = (usage / quota.limit * 100) if quota.limit > 0 else 0

        # 判断是否达到预警阈值
        warning_threshold = quota.warning_threshold or 80
        is_warning = usage_percent >= warning_threshold
        is_exceeded = usage_percent >= 100

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
        period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取租户所有配额配置及使用量

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
        model_id: Optional[int] = None,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """
        检查配额预警状态

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

    async def create_quota(
        self,
        model_id: Optional[int],
        period: str,
        limit: int,
        quota_type: str = "soft",
        warning_threshold: Optional[int] = None,
        description: Optional[str] = None
    ) -> TenantQuota:
        """
        创建配额配置

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
            _("ai.log.quota_created"),
            tenant_id=self.tenant_id,
            model_id=model_id,
            period=period,
            limit=limit,
        )

        return quota


__all__ = ["TenantQuotaService"]
