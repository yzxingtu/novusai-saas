"""
AI call quota manager / AI 调用配额管理器
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quota_exceptions import QuotaExceeded
from app.ai.quota_models import QuotaCheckResult, QuotaMeteringItem
from app.ai.quota_usage_tracker import UsageTracker
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import QuotaTypeEnum
from app.models.ai.tenant_quota import TenantQuota
from app.repositories.ai.tenant_quota_repository import TenantQuotaRepository

logger = LogManager.get_logger("ai.quota")


class QuotaManager:
    """
    Quota Manager / 配额管理器

    Checks and enforces tenant quota limits.
    检查和执行企业配额限制。
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize quota manager.
        初始化配额管理器。

        Args:
            db: Database session / 数据库会话
        """
        self.db = db

    async def check_quota(
        self,
        tenant_id: int,
        model_id: int,
        estimated_tokens: int = 0,
        request_stat_date: date | None = None,
    ) -> QuotaCheckResult:
        """
        Check quota.
        检查配额。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            estimated_tokens: Estimated token count / 预估 Token 数量

        Raises:
            QuotaExceeded: Quota exceeded / 配额超出
        """
        stat_date = request_stat_date or date.today()
        quotas = await self._get_effective_quotas(tenant_id, model_id)
        if not quotas:
            return QuotaCheckResult()

        metering_items: list[QuotaMeteringItem] = []
        precharged_items: list[QuotaMeteringItem] = []
        try:
            for quota in quotas:
                tracking_model_id = self._resolve_tracking_model_id(quota)
                metering_item = QuotaMeteringItem(
                    quota_id=quota.id,
                    period=quota.period,
                    quota_type=quota.quota_type,
                    tracking_model_id=tracking_model_id,
                )

                if quota.quota_type == QuotaTypeEnum.HARD.value:
                    result = await UsageTracker.check_and_record_usage(
                        tenant_id=tenant_id,
                        model_id=tracking_model_id,
                        estimated_tokens=estimated_tokens,
                        limit=quota.limit,
                        period=quota.period,
                        stat_date=stat_date,
                    )
                    if result >= 0:
                        logger.warning(
                            "Quota exceeded: tenant={} model={} tracking_model={} current={} limit={} period={}",
                            tenant_id,
                            model_id,
                            tracking_model_id,
                            result,
                            quota.limit,
                            quota.period,
                        )
                        raise QuotaExceeded(
                            _("ai.error.quota_exceeded").format(
                                current=result + estimated_tokens,
                                limit=quota.limit,
                                period=quota.period,
                            )
                        )
                    precharged_items.append(metering_item)
                elif quota.quota_type == QuotaTypeEnum.SOFT.value:
                    current_usage = await self._get_usage(
                        tenant_id=tenant_id,
                        tracking_model_id=tracking_model_id,
                        period=quota.period,
                        stat_date=stat_date,
                    )
                    if current_usage + estimated_tokens > quota.limit:
                        logger.warning(
                            "Soft quota exceeded: tenant={} model={} tracking_model={} current={} limit={} period={}",
                            tenant_id,
                            model_id,
                            tracking_model_id,
                            current_usage,
                            quota.limit,
                            quota.period,
                        )
                        await self._notify_soft_quota_exceeded(
                            tenant_id=tenant_id,
                            tracking_model_id=tracking_model_id,
                            quota=quota,
                            current_usage=current_usage + estimated_tokens,
                            stat_date=stat_date,
                        )

                metering_items.append(metering_item)
        except Exception:
            if precharged_items:
                await self._rollback_precharged_items(
                    tenant_id=tenant_id,
                    estimated_tokens=estimated_tokens,
                    items=precharged_items,
                    stat_date=stat_date,
                )
            raise

        return QuotaCheckResult(items=tuple(metering_items))

    async def record_usage(
        self, tenant_id: int, model_id: int, tokens: int, stat_date: date | None = None
    ):
        """
        Record usage (for soft limit or no-quota scenarios).
        记录使用量（用于软限制或无配额场景）。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            tokens: Token count / Token 数量
            stat_date: Statistics date / 统计日期
        """
        await UsageTracker.record_usage(tenant_id, model_id, tokens, stat_date)

    async def adjust_usage(
        self,
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
        quota_result: QuotaCheckResult | None = None,
        stat_date: date | None = None,
    ) -> None:
        """
        Adjust usage after response: from estimated to actual.
        响应后调整使用量：从预估值调整为实际值。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            estimated_tokens: Estimated tokens (pre-deducted) / 预估 Token 数量（已预扣）
            actual_tokens: Actual token count / 实际 Token 数量
        """
        _ = model_id
        quota_result = quota_result or QuotaCheckResult()
        stat_date = stat_date or date.today()
        if not quota_result.items:
            return

        for item in quota_result.items:
            if item.quota_type == QuotaTypeEnum.HARD.value:
                await UsageTracker.adjust_usage_for_period(
                    tenant_id=tenant_id,
                    model_id=item.tracking_model_id,
                    estimated_tokens=estimated_tokens,
                    actual_tokens=actual_tokens,
                    period=item.period,
                    stat_date=stat_date,
                )
            elif item.quota_type == QuotaTypeEnum.SOFT.value:
                await UsageTracker.record_usage_for_period(
                    tenant_id=tenant_id,
                    model_id=item.tracking_model_id,
                    tokens=actual_tokens,
                    period=item.period,
                    stat_date=stat_date,
                )

    async def _get_effective_quotas(
        self,
        tenant_id: int,
        model_id: int,
    ) -> list[TenantQuota]:
        """Get runtime effective quotas / 获取运行时生效配额"""
        repo = TenantQuotaRepository(self.db, tenant_id)
        return await repo.get_effective_quotas(tenant_id, model_id)

    async def _get_usage(
        self,
        tenant_id: int,
        tracking_model_id: int,
        period: str,
        stat_date: date | None = None,
    ) -> int:
        """
        Get usage.
        获取使用量。

        Returns:
            Token usage / Token 使用量
        """
        return await UsageTracker.get_usage(
            tenant_id=tenant_id,
            model_id=tracking_model_id,
            period=period,
            stat_date=stat_date,
        )

    @staticmethod
    def _resolve_tracking_model_id(quota: TenantQuota) -> int:
        """Global quotas use model bucket 0 / 全局配额统一使用模型桶 0"""
        return quota.model_id if quota.model_id is not None else 0

    async def _notify_soft_quota_exceeded(
        self,
        tenant_id: int,
        tracking_model_id: int,
        quota: TenantQuota,
        current_usage: int,
        stat_date: date,
    ) -> None:
        """Send at most one soft-quota notification per day / 每天最多发送一次软配额通知"""
        try:
            from app.core.redis import cache_get, cache_set
            from app.models import TenantAdmin
            from app.services.common.notification_service import notify

            notify_key = (
                f"ai:quota_notified:{tenant_id}:{tracking_model_id}:"
                f"{quota.period}:{stat_date.isoformat()}"
            )
            if await cache_get(notify_key):
                return

            result = await self.db.execute(
                select(TenantAdmin.id).where(
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                    TenantAdmin.is_active.is_(True),
                )
            )
            admin_ids = [row[0] for row in result.all()]
            if not admin_ids:
                return

            await notify(
                self.db,
                template_code="ai.soft_quota_exceeded",
                recipients=[("tenant_admin", admin_id) for admin_id in admin_ids],
                data={
                    "current": current_usage,
                    "limit": quota.limit,
                    "period": quota.period,
                },
                tenant_id=tenant_id,
            )
            await cache_set(notify_key, True, ttl=86400)
        except Exception as exc:
            logger.warning(
                "Failed to send soft quota exceeded notification: tenant={} error={}",
                tenant_id,
                str(exc),
            )

    async def _rollback_precharged_items(
        self,
        tenant_id: int,
        estimated_tokens: int,
        items: list[QuotaMeteringItem],
        stat_date: date,
    ) -> None:
        """Rollback previously precharged hard-quota buckets / 回滚已预扣的硬配额桶"""
        if estimated_tokens <= 0:
            return

        for item in items:
            await UsageTracker.adjust_usage_for_period(
                tenant_id=tenant_id,
                model_id=item.tracking_model_id,
                estimated_tokens=estimated_tokens,
                actual_tokens=0,
                period=item.period,
                stat_date=stat_date,
            )


__all__ = ["QuotaManager"]
