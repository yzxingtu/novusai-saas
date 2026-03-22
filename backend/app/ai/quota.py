"""
AI Call Quota Management Service / AI 调用配额管理服务

Manages tenant Token quota, monthly budget, and usage tracking.
管理企业的 Token 配额、月度预算和使用量追踪。
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.enums.ai import QuotaPeriodEnum, QuotaTypeEnum
from app.exceptions.base import BusinessException
from app.models.ai.tenant_quota import TenantQuota
from app.repositories.ai.tenant_quota_repository import TenantQuotaRepository

logger = LogManager.get_logger("ai.quota")


class QuotaExceeded(BusinessException):
    """Quota exceeded exception / 配额超出异常"""

    code = 4291
    status_code = 429
    default_message = "ai.error.quota_exceeded_default"


@dataclass(frozen=True)
class QuotaMeteringItem:
    """
    Quota metering context item / 配额计量上下文项

    Captures which quota rule was applied at request-check time so response-time
    adjustment can update the same Redis bucket deterministically.
    捕获请求检查阶段实际命中的配额规则，确保响应阶段回写到同一 Redis bucket。
    """

    quota_id: int
    period: str
    quota_type: str
    tracking_model_id: int


@dataclass(frozen=True)
class QuotaCheckResult:
    """
    Quota check result / 配额检查结果

    Stores all effective quota rules applied to the request.
    存储本次请求命中的所有生效配额规则。
    """

    items: tuple[QuotaMeteringItem, ...] = ()


class UsageTracker:
    """
    Usage Tracker / 使用量追踪器

    Real-time Token usage tracking via Redis to prevent overuse.
    使用 Redis 实时追踪 Token 使用量，防止超额。
    """

    PREFIX_DAILY = "ai:usage:daily:"
    PREFIX_MONTHLY = "ai:usage:monthly:"

    # Lua script: atomically adjust usage (INCRBY + floor-at-zero guard)
    # Lua 脚本：原子调整用量（INCRBY + 不低于 0 保护）
    # KEYS[1] = usage_key, ARGV[1] = diff
    # Returns adjusted value / 返回调整后的值
    _USAGE_ADJUST_LUA = """
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    if new_val < 0 then
        redis.call('SET', KEYS[1], '0', 'KEEPTTL')
        return 0
    end
    return new_val
    """

    # Lua script: atomic pre-deduct + check
    # Lua 脚本：原子预扣减+检查
    # Returns -1 on success (pre-deducted), >= 0 = current usage (exceeded, rolled back)
    # 返回 -1 表示成功（已预扣），>= 0 表示当前用量（超限，已回滚）
    _QUOTA_CHECK_AND_RECORD_LUA = """
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    if new_val > tonumber(ARGV[2]) then
        redis.call('DECRBY', KEYS[1], ARGV[1])
        return new_val - tonumber(ARGV[1])
    end
    return -1
    """

    @staticmethod
    def _get_key(prefix: str, tenant_id: int, model_id: int, date_key: str) -> str:
        """Generate Redis key / 生成 Redis 键"""
        return f"{prefix}{tenant_id}:{model_id}:{date_key}"

    @staticmethod
    def _resolve_period_key(
        tenant_id: int,
        model_id: int,
        period: str,
        stat_date: date | None = None,
    ) -> tuple[str, int] | None:
        """Resolve Redis key + TTL by period / 按周期解析 Redis key 与 TTL"""
        stat_date = stat_date or date.today()
        if period == QuotaPeriodEnum.DAILY.value:
            return (
                UsageTracker._get_key(
                    UsageTracker.PREFIX_DAILY,
                    tenant_id,
                    model_id,
                    stat_date.isoformat(),
                ),
                86400 * 2,
            )
        if period == QuotaPeriodEnum.MONTHLY.value:
            return (
                UsageTracker._get_key(
                    UsageTracker.PREFIX_MONTHLY,
                    tenant_id,
                    model_id,
                    f"{stat_date.year}-{stat_date.month:02d}",
                ),
                86400 * 35,
            )
        return None

    @staticmethod
    async def get_daily_usage(
        tenant_id: int,
        model_id: int,
        stat_date: date | None = None
    ) -> int:
        """
        Get daily token usage.
        获取当日 Token 使用量。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            stat_date: Statistics date, defaults to today / 统计日期，默认今天

        Returns:
            Token usage / Token 使用量
        """
        redis = await get_redis()
        stat_date = stat_date or date.today()
        key = UsageTracker._get_key(UsageTracker.PREFIX_DAILY, tenant_id, model_id, stat_date.isoformat())

        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def get_monthly_usage(
        tenant_id: int,
        model_id: int,
        year: int | None = None,
        month: int | None = None
    ) -> int:
        """
        Get monthly token usage.
        获取当月 Token 使用量。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            year: Year, defaults to current / 年份，默认当前年
            month: Month, defaults to current / 月份，默认当前月

        Returns:
            Token usage / Token 使用量
        """
        redis = await get_redis()
        today = date.today()
        year = year or today.year
        month = month or today.month

        key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY,
            tenant_id,
            model_id,
            f"{year}-{month:02d}"
        )

        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def check_and_record_usage(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        limit: int,
        period: str,
        stat_date: date | None = None,
    ) -> int:
        """
        Atomically check + pre-deduct usage (eliminates TOCTOU race).
        原子检查+预扣减使用量（消除 TOCTOU 竞态）。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            estimated_tokens: Estimated token count / 预估 Token 数量
            limit: Quota limit / 配额上限
            period: Period (daily/monthly) / 周期

        Returns:
            -1 on success (pre-deducted), >= 0 = current usage (exceeded, rolled back)
            -1 表示成功（已预扣），>= 0 表示当前用量（超限，已回滚）
        """
        redis = await get_redis()
        resolved = UsageTracker._resolve_period_key(
            tenant_id=tenant_id,
            model_id=model_id,
            period=period,
            stat_date=stat_date,
        )
        if resolved is None:
            return -1
        key, expire_seconds = resolved

        result = await redis.eval(
            UsageTracker._QUOTA_CHECK_AND_RECORD_LUA,
            1,
            key,
            str(estimated_tokens),
            str(limit),
            str(expire_seconds),
        )
        return int(result)

    @staticmethod
    async def record_usage(
        tenant_id: int,
        model_id: int,
        tokens: int,
        stat_date: date | None = None
    ):
        """
        Record token usage.
        记录 Token 使用量。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            tokens: Token count / Token 数量
            stat_date: Statistics date / 统计日期
        """
        await UsageTracker.record_usage_for_period(
            tenant_id=tenant_id,
            model_id=model_id,
            tokens=tokens,
            period=QuotaPeriodEnum.DAILY.value,
            stat_date=stat_date,
        )
        await UsageTracker.record_usage_for_period(
            tenant_id=tenant_id,
            model_id=model_id,
            tokens=tokens,
            period=QuotaPeriodEnum.MONTHLY.value,
            stat_date=stat_date,
        )

    @staticmethod
    async def adjust_usage(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
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
        await UsageTracker.adjust_usage_for_period(
            tenant_id=tenant_id,
            model_id=model_id,
            estimated_tokens=estimated_tokens,
            actual_tokens=actual_tokens,
            period=QuotaPeriodEnum.DAILY.value,
            stat_date=stat_date,
        )
        await UsageTracker.adjust_usage_for_period(
            tenant_id=tenant_id,
            model_id=model_id,
            estimated_tokens=estimated_tokens,
            actual_tokens=actual_tokens,
            period=QuotaPeriodEnum.MONTHLY.value,
            stat_date=stat_date,
        )

    @staticmethod
    async def get_usage(
        tenant_id: int,
        model_id: int,
        period: str,
        stat_date: date | None = None,
    ) -> int:
        """Get usage by period / 按周期获取使用量"""
        stat_date = stat_date or date.today()
        if period == QuotaPeriodEnum.DAILY.value:
            return await UsageTracker.get_daily_usage(tenant_id, model_id, stat_date)
        if period == QuotaPeriodEnum.MONTHLY.value:
            return await UsageTracker.get_monthly_usage(
                tenant_id,
                model_id,
                stat_date.year,
                stat_date.month,
            )
        return 0

    @staticmethod
    async def record_usage_for_period(
        tenant_id: int,
        model_id: int,
        tokens: int,
        period: str,
        stat_date: date | None = None,
    ) -> None:
        """Record usage for a single period / 记录单一周期使用量"""
        if tokens == 0:
            return
        resolved = UsageTracker._resolve_period_key(
            tenant_id=tenant_id,
            model_id=model_id,
            period=period,
            stat_date=stat_date,
        )
        if resolved is None:
            return

        key, expire_seconds = resolved
        redis = await get_redis()
        await redis.incrby(key, tokens)
        await redis.expire(key, expire_seconds)

    @staticmethod
    async def adjust_usage_for_period(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
        period: str,
        stat_date: date | None = None,
    ) -> None:
        """Adjust usage for a single period / 调整单一周期使用量"""
        diff = actual_tokens - estimated_tokens
        if diff == 0:
            return

        resolved = UsageTracker._resolve_period_key(
            tenant_id=tenant_id,
            model_id=model_id,
            period=period,
            stat_date=stat_date,
        )
        if resolved is None:
            return

        key, _expire_seconds = resolved
        redis = await get_redis()
        await redis.eval(
            UsageTracker._USAGE_ADJUST_LUA,
            1,
            key,
            str(diff),
        )


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
        self,
        tenant_id: int,
        model_id: int,
        tokens: int,
        stat_date: date | None = None
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


__all__ = [
    "QuotaCheckResult",
    "QuotaMeteringItem",
    "UsageTracker",
    "QuotaManager",
    "QuotaExceeded",
]
