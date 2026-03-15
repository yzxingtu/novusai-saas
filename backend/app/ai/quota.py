"""
AI Call Quota Management Service / AI 调用配额管理服务

Manages tenant Token quota, monthly budget, and usage tracking.
管理企业的 Token 配额、月度预算和使用量追踪。
"""

from datetime import date

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
        today = date.today()

        if period == QuotaPeriodEnum.DAILY.value:
            key = UsageTracker._get_key(
                UsageTracker.PREFIX_DAILY, tenant_id, model_id, today.isoformat()
            )
            expire_seconds = 86400 * 2
        elif period == QuotaPeriodEnum.MONTHLY.value:
            key = UsageTracker._get_key(
                UsageTracker.PREFIX_MONTHLY, tenant_id, model_id,
                f"{today.year}-{today.month:02d}"
            )
            expire_seconds = 86400 * 35
        else:
            return -1

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
        redis = await get_redis()
        stat_date = stat_date or date.today()

        # Record daily usage / 记录每日使用量
        daily_key = UsageTracker._get_key(
            UsageTracker.PREFIX_DAILY,
            tenant_id,
            model_id,
            stat_date.isoformat()
        )
        await redis.incrby(daily_key, tokens)
        await redis.expire(daily_key, 86400 * 2)  # Keep 2 days / 保留 2 天

        # Record monthly usage / 记录每月使用量
        monthly_key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY,
            tenant_id,
            model_id,
            f"{stat_date.year}-{stat_date.month:02d}"
        )
        await redis.incrby(monthly_key, tokens)
        await redis.expire(monthly_key, 86400 * 35)  # Keep 35 days / 保留 35 天

    @staticmethod
    async def adjust_usage(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
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
        diff = actual_tokens - estimated_tokens
        if diff == 0:
            return

        redis = await get_redis()
        today = date.today()

        daily_key = UsageTracker._get_key(
            UsageTracker.PREFIX_DAILY, tenant_id, model_id, today.isoformat()
        )
        monthly_key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY, tenant_id, model_id,
            f"{today.year}-{today.month:02d}"
        )

        # Atomic adjust: INCRBY + floor-at-zero guard (eliminates TOCTOU race)
        # 原子调整：INCRBY + 不低于 0 保护（消除 TOCTOU 竞态）
        for key in (daily_key, monthly_key):
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
        from app.services.ai.metering_service import MeteringService

        self.db = db
        self.metering = MeteringService(db)

    async def check_quota(
        self,
        tenant_id: int,
        model_id: int,
        estimated_tokens: int = 0
    ) -> bool:
        """
        Check quota.
        检查配额。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            estimated_tokens: Estimated token count / 预估 Token 数量

        Returns:
            True if call is allowed / True 表示允许调用

        Raises:
            QuotaExceeded: Quota exceeded / 配额超出
        """
        # Get tenant quota config / 获取企业配额配置
        quota = await self._get_tenant_quota(tenant_id, model_id)

        if not quota or not quota.is_active:
            # No quota configured or quota inactive, allow call
            # 没有配置配额或配额未激活，允许调用
            return True

        # Check hard limit (atomic pre-deduct, eliminates TOCTOU race)
        # 检查硬限制（原子预扣减，消除 TOCTOU 竞态）
        if quota.quota_type == QuotaTypeEnum.HARD.value:
            result = await UsageTracker.check_and_record_usage(
                tenant_id=tenant_id,
                model_id=model_id,
                estimated_tokens=estimated_tokens,
                limit=quota.limit,
                period=quota.period,
            )
            if result >= 0:
                logger.warning(
                    "Quota exceeded: tenant=%s model=%s current=%s limit=%s period=%s",
                    tenant_id, model_id, result, quota.limit, quota.period,
                )
                raise QuotaExceeded(
                    _("ai.error.quota_exceeded").format(
                        current=result + estimated_tokens,
                        limit=quota.limit,
                        period=quota.period
                    )
                )

        # Check soft limit - record but allow overuse / 检查软限制 - 记录但允许超额
        elif quota.quota_type == QuotaTypeEnum.SOFT.value:
            current_usage = await self._get_usage(
                tenant_id,
                model_id,
                quota.period
            )

            if current_usage + estimated_tokens > quota.limit:
                logger.warning(
                    "Soft quota exceeded: tenant=%s model=%s current=%s limit=%s period=%s",
                    tenant_id, model_id, current_usage, quota.limit, quota.period,
                )
                # Soft limit allows overuse, but logs warning
                # 软限制允许超额，但记录警告
                # TODO: 发送通知给企业

        return True

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
        await UsageTracker.adjust_usage(
            tenant_id, model_id, estimated_tokens, actual_tokens
        )

    async def _get_tenant_quota(
        self,
        tenant_id: int,
        model_id: int
    ) -> TenantQuota | None:
        """
        Get tenant quota config.
        获取企业配额配置。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID

        Returns:
            TenantQuota instance / TenantQuota 实例
        """
        repo = TenantQuotaRepository(self.db, tenant_id)
        return await repo.get_active_quota(tenant_id, model_id)

    async def _get_usage(
        self,
        tenant_id: int,
        model_id: int,
        period: str
    ) -> int:
        """
        Get usage.
        获取使用量。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            period: Period (daily/monthly) / 周期

        Returns:
            Token usage / Token 使用量
        """
        today = date.today()

        if period == QuotaPeriodEnum.DAILY.value:
            return await UsageTracker.get_daily_usage(tenant_id, model_id, today)
        elif period == QuotaPeriodEnum.MONTHLY.value:
            return await UsageTracker.get_monthly_usage(
                tenant_id,
                model_id,
                today.year,
                today.month
            )
        else:
            return 0


__all__ = [
    "UsageTracker",
    "QuotaManager",
    "QuotaExceeded",
]
