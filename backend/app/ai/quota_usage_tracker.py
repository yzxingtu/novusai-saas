"""
AI quota usage tracker / AI 配额使用量追踪器
"""

from datetime import date

from app.core.redis import get_redis
from app.enums.ai import QuotaPeriodEnum


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
    # KEYS[1] = usage_key, ARGV[1] = diff, ARGV[2] = expire_seconds
    # Returns adjusted value / 返回调整后的值
    _USAGE_ADJUST_LUA = """
    local ttl = redis.call('TTL', KEYS[1])
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    if ttl < 0 then
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
    end
    if new_val < 0 then
        if ttl >= 0 then
            redis.call('SET', KEYS[1], '0', 'KEEPTTL')
        else
            redis.call('SET', KEYS[1], '0', 'EX', tonumber(ARGV[2]))
        end
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
    async def _get_redis():
        return await get_redis()

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
        tenant_id: int, model_id: int, stat_date: date | None = None
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
        redis = await UsageTracker._get_redis()
        stat_date = stat_date or date.today()
        key = UsageTracker._get_key(
            UsageTracker.PREFIX_DAILY, tenant_id, model_id, stat_date.isoformat()
        )

        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def get_monthly_usage(
        tenant_id: int, model_id: int, year: int | None = None, month: int | None = None
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
        redis = await UsageTracker._get_redis()
        today = date.today()
        year = year or today.year
        month = month or today.month

        key = UsageTracker._get_key(
            UsageTracker.PREFIX_MONTHLY, tenant_id, model_id, f"{year}-{month:02d}"
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
        redis = await UsageTracker._get_redis()
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
        tenant_id: int, model_id: int, tokens: int, stat_date: date | None = None
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
        redis = await UsageTracker._get_redis()
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

        key, expire_seconds = resolved
        redis = await UsageTracker._get_redis()
        await redis.eval(
            UsageTracker._USAGE_ADJUST_LUA,
            1,
            key,
            str(diff),
            str(expire_seconds),
        )


__all__ = ["UsageTracker"]
