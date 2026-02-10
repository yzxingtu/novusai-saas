"""
AI 调用速率限制服务

基于 Redis 滑动窗口算法实现速率限制，防止滥用。
RPM（每分钟请求数）使用 zcard 计数；
TPM（每分钟 Token 数）使用独立的 INCRBY 累加计数器。
"""

import os
import time
from typing import Optional

from app.core.redis import get_redis
from app.core.logging import LogManager
from app.core.i18n import _


logger = LogManager.get_logger("ai.rate_limiter")


class RateLimitExceeded(Exception):
    """速率限制超出异常"""
    pass


class RateLimiter:
    """
    速率限制器

    RPM: 使用 sorted set 滑动窗口，zcard 计数请求次数
    TPM: 使用独立的 string key + INCRBY 累加 token 数
    """

    PREFIX_RPM = "ai:rate_limit:rpm:"
    PREFIX_TPM = "ai:rate_limit:tpm:"
    WINDOW_SIZE = 60  # 窗口大小: 60 秒

    # Lua 脚本：RPM 原子检查+记录
    # 返回 -1 表示成功记录，>= 0 表示当前 RPM 数（超限未记录）
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

    # Lua 脚本：TPM 原子预扣减+检查
    # 返回 -1 表示成功预扣，>= 0 表示当前 TPM 总量（超限未扣减）
    _TPM_CHECK_AND_RECORD_LUA = """
    local cur = redis.call('GET', KEYS[1])
    local prev = redis.call('GET', KEYS[2])
    local total = (tonumber(cur) or 0) + (tonumber(prev) or 0)
    if total + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
        return total
    end
    redis.call('INCRBY', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    return -1
    """

    @staticmethod
    async def check_and_record(
        tenant_id: int,
        model_id: int,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
        estimated_tokens: int = 0,
    ) -> bool:
        """
        原子性检查并记录速率限制（消除 TOCTOU 竞态）

        RPM: Lua 脚本原子执行 清理过期→计数→添加
        TPM: Lua 脚本原子执行 预扣减→检查超限

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            rpm_limit: RPM 限制(每分钟请求数)
            tpm_limit: TPM 限制(每分钟 Token 数)
            estimated_tokens: 预估 Token 数量

        Returns:
            True 表示允许调用（已原子记录）

        Raises:
            RateLimitExceeded: 超出速率限制
        """
        redis = await get_redis()
        current_time = int(time.time())
        expire_seconds = RateLimiter.WINDOW_SIZE + 10

        # RPM 原子检查+记录
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
                    _("ai.log.rpm_limit_exceeded"),
                    tenant_id=tenant_id,
                    model_id=model_id,
                    count=rpm_count,
                    limit=rpm_limit,
                )
                raise RateLimitExceeded(
                    _("ai.error.rpm_limit_exceeded").format(
                        count=rpm_count, limit=rpm_limit
                    )
                )

        # TPM 原子预扣减+检查
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
                    _("ai.log.tpm_limit_exceeded"),
                    tenant_id=tenant_id,
                    model_id=model_id,
                    count=tpm_count,
                    limit=tpm_limit,
                )
                raise RateLimitExceeded(
                    _("ai.error.tpm_limit_exceeded").format(
                        count=tpm_count, limit=tpm_limit
                    )
                )

        return True

    @staticmethod
    async def adjust_tpm_after_response(
        tenant_id: int,
        model_id: int,
        estimated_tokens: int,
        actual_tokens: int,
    ) -> None:
        """
        响应后调整 TPM：从预估值调整为实际值

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            estimated_tokens: 预估 Token 数量（已预扣）
            actual_tokens: 实际 Token 数量
        """
        diff = actual_tokens - estimated_tokens
        if diff == 0:
            return
        redis = await get_redis()
        current_time = int(time.time())
        minute_key = current_time // 60
        tpm_key = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{minute_key}"
        if diff > 0:
            await redis.incrby(tpm_key, diff)
        else:
            # DECRBY 回滚，但不低于 0
            current_val = await redis.get(tpm_key)
            if current_val:
                new_val = max(0, int(current_val) + diff)
                await redis.set(tpm_key, new_val, keepttl=True)

    @staticmethod
    async def _sliding_window_count(
        redis,
        key: str,
        current_time: int
    ) -> int:
        """
        计算 RPM 滑动窗口内的请求数

        Args:
            redis: Redis 客户端
            key: sorted set 键
            current_time: 当前时间戳

        Returns:
            窗口内的请求数
        """
        # 删除窗口外的旧数据
        window_start = current_time - RateLimiter.WINDOW_SIZE
        await redis.zremrangebyscore(key, 0, window_start)

        # 获取当前窗口内的条目数
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
        获取 TPM 滑动窗口内的 Token 总和

        使用最近 2 个分钟 key 的值之和，覆盖 60 秒窗口。

        Args:
            redis: Redis 客户端
            tenant_id: 租户 ID
            model_id: 模型 ID
            current_time: 当前时间戳

        Returns:
            窗口内的 Token 总数
        """
        current_minute = current_time // 60
        prev_minute = current_minute - 1

        # 读取当前分钟和上一分钟的累加值
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
    async def get_current_usage(
        tenant_id: int,
        model_id: int
    ) -> dict:
        """
        获取当前使用量

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID

        Returns:
            使用量字典 {rpm: int, tpm: int}
        """
        redis = await get_redis()
        current_time = int(time.time())

        rpm_key = f"{RateLimiter.PREFIX_RPM}{tenant_id}:{model_id}"
        rpm = await RateLimiter._sliding_window_count(redis, rpm_key, current_time)
        tpm = await RateLimiter._get_tpm_usage(redis, tenant_id, model_id, current_time)

        return {"rpm": rpm, "tpm": tpm}


__all__ = [
    "RateLimiter",
    "RateLimitExceeded",
]
