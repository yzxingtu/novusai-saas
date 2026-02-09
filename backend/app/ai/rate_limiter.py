"""
AI 调用速率限制服务

基于 Redis 滑动窗口算法实现速率限制，防止滥用。
RPM（每分钟请求数）使用 zcard 计数；
TPM（每分钟 Token 数）使用独立的 INCRBY 累加计数器。
"""

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

    @staticmethod
    async def check_rate_limit(
        tenant_id: int,
        model_id: int,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None
    ) -> bool:
        """
        检查速率限制

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            rpm_limit: RPM 限制(每分钟请求数)
            tpm_limit: TPM 限制(每分钟 Token 数)

        Returns:
            True 表示允许调用

        Raises:
            RateLimitExceeded: 超出速率限制
        """
        redis = await get_redis()
        current_time = int(time.time())

        # 检查 RPM 限制（使用 sorted set 滑动窗口）
        if rpm_limit:
            rpm_key = f"{RateLimiter.PREFIX_RPM}{tenant_id}:{model_id}"
            rpm_count = await RateLimiter._sliding_window_count(
                redis, rpm_key, current_time
            )

            if rpm_count >= rpm_limit:
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

        # 检查 TPM 限制（使用独立的累加计数器）
        if tpm_limit:
            tpm_count = await RateLimiter._get_tpm_usage(
                redis, tenant_id, model_id, current_time
            )

            if tpm_count >= tpm_limit:
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
    async def record_request(
        tenant_id: int,
        model_id: int,
        tokens: int = 0
    ):
        """
        记录调用

        Args:
            tenant_id: 租户 ID
            model_id: 模型 ID
            tokens: Token 数量
        """
        redis = await get_redis()
        current_time = int(time.time())

        # 记录 RPM（sorted set，member=timestamp，score=timestamp）
        rpm_key = f"{RateLimiter.PREFIX_RPM}{tenant_id}:{model_id}"
        await redis.zadd(rpm_key, {str(current_time): current_time})
        await redis.expire(rpm_key, RateLimiter.WINDOW_SIZE + 10)

        # 记录 TPM（使用分钟级别的 key 累加 token 数）
        if tokens > 0:
            # 以当前分钟为 key，INCRBY 累加 token 数
            minute_key = current_time // 60
            tpm_key = f"{RateLimiter.PREFIX_TPM}{tenant_id}:{model_id}:{minute_key}"
            await redis.incrby(tpm_key, tokens)
            await redis.expire(tpm_key, RateLimiter.WINDOW_SIZE + 10)

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
