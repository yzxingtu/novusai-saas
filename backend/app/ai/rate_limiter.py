"""
AI Call Rate Limiting Service / AI 调用速率限制服务

Redis-based sliding window rate limiting to prevent abuse.
RPM (requests per minute) uses sorted set + zcard counting;
TPM (tokens per minute) uses independent INCRBY accumulation counters.
基于 Redis 滑动窗口算法实现速率限制，防止滥用。
RPM（每分钟请求数）使用 zcard 计数；
TPM（每分钟 Token 数）使用独立的 INCRBY 累加计数器。
"""

import os
import time
from dataclasses import dataclass

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.exceptions.base import BusinessException

logger = LogManager.get_logger("ai.rate_limiter")


@dataclass(frozen=True)
class RateLimitReservation:
    """Tracks the exact RPM/TPM keys touched during request precharge."""

    rpm_key: str | None = None
    rpm_member: str | None = None
    tpm_key: str | None = None


class RateLimitExceeded(BusinessException):
    """Rate limit exceeded exception / 速率限制超出异常"""

    code = 4292
    status_code = 429
    default_message = "ai.rate_limited"


class RateLimiter:
    """
    Rate Limiter / 速率限制器

    RPM: Sorted set sliding window, zcard counts request count.
    TPM: Independent string key + INCRBY accumulates token count.
    RPM: 使用 sorted set 滑动窗口，zcard 计数请求次数。
    TPM: 使用独立的 string key + INCRBY 累加 token 数。
    """

    PREFIX_RPM = "ai:rate_limit:rpm:"
    PREFIX_TPM = "ai:rate_limit:tpm:"
    WINDOW_SIZE = 60  # Window size: 60 seconds / 窗口大小: 60 秒

    # Lua script: RPM atomic check + record / Lua 脚本：RPM 原子检查+记录
    # Returns -1 on success, >= 0 = current RPM count (exceeded, not recorded) / 返回 -1 表示成功记录，>= 0 表示当前 RPM 数（超限未记录）
    _RPM_CHECK_AND_RECORD_LUA = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
    local count = redis.call('ZCARD', KEYS[1])
    if count >= tonumber(ARGV[2]) then
        return count
    end
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]))
    return -1
    """

    # Lua script: TPM atomic pre-deduct + check / Lua 脚本：TPM 原子预扣减+检查
    # Returns -1 on success, >= 0 = would-be TPM total if recorded (exceeded, not deducted)
    # 返回 -1 表示成功预扣，>= 0 表示若本次写入后将达到的 TPM 总量（超限未扣减）
    _TPM_CHECK_AND_RECORD_LUA = """
    local cur = redis.call('GET', KEYS[1])
    local prev = redis.call('GET', KEYS[2])
    local total = (tonumber(cur) or 0) + (tonumber(prev) or 0)
    if total + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
        return total + tonumber(ARGV[1])
    end
    redis.call('INCRBY', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    return -1
    """

    # Lua script: atomically adjust TPM (INCRBY + floor-at-zero guard) / Lua 脚本：原子调整 TPM（INCRBY + 不低于 0 保护）
    # KEYS[1] = tpm_key, ARGV[1] = diff
    # Returns adjusted value / 返回调整后的值
    _TPM_ADJUST_LUA = """
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    if new_val < 0 then
        redis.call('SET', KEYS[1], '0', 'KEEPTTL')
        return 0
    end
    return new_val
    """

    @staticmethod
    async def check_and_record(
        tenant_id: int,
        model_id: int,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        estimated_tokens: int = 0,
        current_time: int | None = None,
    ) -> RateLimitReservation:
        """
        Atomically check and record rate limit (eliminates TOCTOU race).
        原子性检查并记录速率限制（消除 TOCTOU 竞态）。

        RPM: Lua script atomically executes cleanup-expired → count → add.
        TPM: Lua script atomically executes pre-deduct → check-exceeded.
        RPM: Lua 脚本原子执行 清理过期→计数→添加。
        TPM: Lua 脚本原子执行 预扣减→检查超限。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            rpm_limit: RPM limit (requests per minute) / RPM 限制(每分钟请求数)
            tpm_limit: TPM limit (tokens per minute) / TPM 限制(每分钟 Token 数)
            estimated_tokens: Estimated token count / 预估 Token 数量

        Returns:
            True if call is allowed (atomically recorded) / True 表示允许调用（已原子记录）

        Raises:
            RateLimitExceeded: Rate limit exceeded / 超出速率限制
        """
        redis = await get_redis()
        current_time = current_time or int(time.time())
        expire_seconds = RateLimiter.WINDOW_SIZE + 10

        rpm_key: str | None = None
        rpm_member: str | None = None
        tpm_key: str | None = None

        # RPM atomic check + record / RPM 原子检查+记录
        if rpm_limit:
            rpm_key = f"{RateLimiter.PREFIX_RPM}{tenant_id}:{model_id}"
            window_start = current_time - RateLimiter.WINDOW_SIZE
            unique_member = f"{current_time}:{os.urandom(4).hex()}"

            result = await redis.eval(
                RateLimiter._RPM_CHECK_AND_RECORD_LUA,
                1,
                rpm_key,
                str(window_start),
                str(rpm_limit),
                str(current_time),
                unique_member,
                str(expire_seconds),
            )
            if result >= 0:
                rpm_count = int(result)
                logger.warning(
                    "RPM limit exceeded: tenant={} model={} count={} limit={}",
                    tenant_id,
                    model_id,
                    rpm_count,
                    rpm_limit,
                )
                raise RateLimitExceeded(
                    _("ai.error.rpm_limit_exceeded").format(
                        count=rpm_count, limit=rpm_limit
                    )
                )
            rpm_member = unique_member

        # TPM atomic pre-deduct + check / TPM 原子预扣减+检查
        if tpm_limit and estimated_tokens > 0:
            minute_key = current_time // 60
            prev_minute = minute_key - 1
            key_current = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{minute_key}"
            key_prev = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{prev_minute}"

            result = await redis.eval(
                RateLimiter._TPM_CHECK_AND_RECORD_LUA,
                2,
                key_current,
                key_prev,
                str(estimated_tokens),
                str(tpm_limit),
                str(expire_seconds),
            )
            if result >= 0:
                tpm_count = int(result)
                logger.warning(
                    "TPM limit exceeded: tenant={} model={} count={} limit={}",
                    tenant_id,
                    model_id,
                    tpm_count,
                    tpm_limit,
                )
                raise RateLimitExceeded(
                    _("ai.error.tpm_limit_exceeded").format(
                        count=tpm_count, limit=tpm_limit
                    )
                )
            tpm_key = key_current

        return RateLimitReservation(
            rpm_key=rpm_key,
            rpm_member=rpm_member,
            tpm_key=tpm_key,
        )

    @staticmethod
    async def rollback_precharge(
        *,
        reservation: RateLimitReservation | None,
        estimated_tokens: int,
    ) -> None:
        """Rollback RPM/TPM precharge when a later gate rejects the request."""
        if reservation is None:
            return

        redis = await get_redis()
        if reservation.rpm_key and reservation.rpm_member:
            await redis.zrem(reservation.rpm_key, reservation.rpm_member)
        if reservation.tpm_key and estimated_tokens > 0:
            await redis.eval(
                RateLimiter._TPM_ADJUST_LUA,
                1,
                reservation.tpm_key,
                str(-estimated_tokens),
            )

    @staticmethod
    async def adjust_tpm_after_response(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
        request_minute_key: int | None = None,
    ) -> None:
        """
        Adjust TPM after response: from estimated to actual.
        响应后调整 TPM：从预估值调整为实际值。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            estimated_tokens: Estimated tokens (pre-deducted) / 预估 Token 数量（已预扣）
            actual_tokens: Actual token count / 实际 Token 数量
            request_minute_key: Minute key at request time (int(start_time)//60),
                avoids adjusting wrong key across minute boundary. Defaults to current time.
                请求时的分钟 key（int(start_time)//60），
                避免跨分钟边界时调整到错误的 key。缺省时使用当前时间。
        """
        diff = actual_tokens - estimated_tokens
        if diff == 0:
            return
        redis = await get_redis()
        minute_key = (
            request_minute_key
            if request_minute_key is not None
            else int(time.time()) // 60
        )
        tpm_key = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{minute_key}"
        # Atomic adjust: INCRBY + floor-at-zero guard (eliminates TOCTOU race) / 原子调整：INCRBY + 不低于 0 保护（消除 TOCTOU 竞态）
        await redis.eval(
            RateLimiter._TPM_ADJUST_LUA,
            1,
            tpm_key,
            str(diff),
        )

    @staticmethod
    async def _sliding_window_count(redis, key: str, current_time: int) -> int:
        """
        Calculate request count within RPM sliding window.
        计算 RPM 滑动窗口内的请求数。

        Args:
            redis: Redis client / Redis 客户端
            key: Sorted set key / sorted set 键
            current_time: Current timestamp / 当前时间戳

        Returns:
            Request count within window / 窗口内的请求数
        """
        # Remove expired entries outside window / 删除窗口外的旧数据
        window_start = current_time - RateLimiter.WINDOW_SIZE
        await redis.zremrangebyscore(key, 0, window_start)

        # Get entry count within current window / 获取当前窗口内的条目数
        count = await redis.zcard(key)

        return count

    @staticmethod
    async def _get_tpm_usage(
        redis,
        tenant_id: int,
        model_id: int,
        current_time: int,
    ) -> int:
        """
        Get total token count within TPM sliding window.
        获取 TPM 滑动窗口内的 Token 总和。

        Uses sum of last 2 minute keys to cover a 60-second window.
        使用最近 2 个分钟 key 的值之和，覆盖 60 秒窗口。

        Args:
            redis: Redis client / Redis 客户端
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID
            current_time: Current timestamp / 当前时间戳

        Returns:
            Total tokens within window / 窗口内的 Token 总数
        """
        current_minute = current_time // 60
        prev_minute = current_minute - 1

        # Read accumulated values for current and previous minute / 读取当前分钟和上一分钟的累加值
        key_current = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{current_minute}"
        key_prev = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{prev_minute}"

        val_current = await redis.get(key_current)
        val_prev = await redis.get(key_prev)

        total = 0
        if val_current:
            total += int(val_current)
        if val_prev:
            total += int(val_prev)

        return total

    @staticmethod
    async def get_current_usage(tenant_id: int, model_id: int) -> dict:
        """
        Get current usage.
        获取当前使用量。

        Args:
            tenant_id: Tenant ID / 企业 ID
            model_id: Model ID / 模型 ID

        Returns:
            Usage dict {rpm: int, tpm: int} / 使用量字典 {rpm: int, tpm: int}
        """
        redis = await get_redis()
        current_time = int(time.time())

        rpm_key = f"{RateLimiter.PREFIX_RPM}{tenant_id}:{model_id}"
        rpm = await RateLimiter._sliding_window_count(redis, rpm_key, current_time)
        tpm = await RateLimiter._get_tpm_usage(redis, tenant_id, model_id, current_time)

        return {"rpm": rpm, "tpm": tpm}


__all__ = [
    "RateLimitReservation",
    "RateLimiter",
    "RateLimitExceeded",
]
