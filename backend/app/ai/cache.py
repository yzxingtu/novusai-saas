"""
AI Response Cache Service
AI 响应缓存服务

Redis-based AI response caching to improve speed and reduce costs.
Only caches non-streaming requests.
基于 Redis 实现 AI 响应的缓存，提高响应速度并降低成本。仅缓存非流式请求。
"""

import hashlib
import json
from typing import Any

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import LogManager
from app.core.redis import get_redis

logger = LogManager.get_logger("ai.cache")


class AIResponseCache:
    """
    AI Response Cache / AI 响应缓存

    Caches AI call responses with TTL and auto-expiry.
    Provides cache hit rate statistics.
    缓存 AI 调用响应，支持 TTL 和自动失效。提供缓存命中率统计功能。
    """

    CACHE_PREFIX = "ai:response:"
    STATS_KEY = "ai:cache:stats"

    @staticmethod
    def _get_default_ttl() -> int:
        """Get default cache TTL (from config) / 获取默认缓存 TTL（从配置读取）"""
        return settings.AI_CACHE_TTL

    @staticmethod
    def _generate_cache_key(
        provider_code: str,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int | None = None,
        tools: list | None = None,
    ) -> str:
        """
        Generate cache key.
        生成缓存键。

        key = hash(model_code + sorted(messages) + temperature + max_tokens)

        Args:
            provider_code: Provider code / 供应商代码
            model: Model name / 模型名称
            messages: Message list / 消息列表
            temperature: Temperature parameter / 温度参数
            max_tokens: Max tokens / 最大 tokens
            tools: Tool list / 工具列表

        Returns:
            Cache key / 缓存键
        """
        params = {
            "provider": provider_code,
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
        }

        params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        hash_value = hashlib.sha256(params_str.encode()).hexdigest()

        return f"{AIResponseCache.CACHE_PREFIX}{hash_value}"

    @staticmethod
    async def get(cache_key: str) -> dict | None:
        """
        Get cached response.
        获取缓存响应。

        Args:
            cache_key: Cache key / 缓存键

        Returns:
            Cached response data, or None if not found / 缓存的响应数据，如果不存在则返回 None
        """
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)

            if cached:
                try:
                    data = json.loads(cached)
                except (json.JSONDecodeError, ValueError):
                    # Cache data corrupt, delete and log warning (not counted as hit)
                    # 缓存数据损坏，删除并记录警告，不计入 hit 统计
                    logger.warning(
                        "Cache corrupt: key=%s", cache_key[:40],
                    )
                    await redis.delete(cache_key)
                    await AIResponseCache._record_hit(redis, hit=False)
                    return None

                # Record hit / 统计命中
                await AIResponseCache._record_hit(redis, hit=True)
                logger.info("Cache hit: key=%s", cache_key[:40])
                return data

            # Record miss / 统计未命中
            await AIResponseCache._record_hit(redis, hit=False)
            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Cache get failed: %s", str(e))
            return None

    @staticmethod
    async def set(
        cache_key: str,
        response_data: dict,
        ttl: int | None = None,
    ) -> None:
        """
        Set cached response.
        设置缓存响应。

        Args:
            cache_key: Cache key / 缓存键
            response_data: Response data (must be JSON-serializable) / 响应数据（必须 JSON 可序列化）
            ttl: Expiry time in seconds, default 1 hour / 过期时间(秒)，默认 1 小时
        """
        try:
            redis = await get_redis()
            ttl = ttl or AIResponseCache._get_default_ttl()

            await redis.setex(
                cache_key,
                ttl,
                json.dumps(response_data, ensure_ascii=False, default=str),
            )

            logger.info("Cache set: key=%s ttl=%d", cache_key[:40], ttl)

        except (RedisError, TypeError) as e:
            logger.error("Cache set failed: %s", str(e))

    @staticmethod
    async def delete(cache_key: str) -> None:
        """
        Delete cache entry.
        删除缓存。

        Args:
            cache_key: Cache key / 缓存键
        """
        try:
            redis = await get_redis()
            await redis.delete(cache_key)
            logger.info("Cache deleted: key=%s", cache_key[:40])

        except RedisError as e:
            logger.error("Cache delete failed: %s", str(e))

    @staticmethod
    async def clear_pattern(pattern: str) -> None:
        """
        Batch delete cache entries by pattern.
        批量删除缓存。

        Args:
            pattern: Match pattern (e.g. "openai:*") / 匹配模式（如 "openai:*"）
        """
        try:
            redis = await get_redis()
            keys = []
            async for key in redis.scan_iter(match=f"{AIResponseCache.CACHE_PREFIX}{pattern}"):
                keys.append(key)

            if keys:
                await redis.delete(*keys)
                logger.info("Cache cleared: pattern=%s count=%d", pattern, len(keys))

        except RedisError as e:
            logger.error("Cache clear failed: %s", str(e))

    @staticmethod
    async def clear_all() -> None:
        """Clear all AI response cache / 清除所有 AI 响应缓存"""
        await AIResponseCache.clear_pattern("*")

    # ========== Cache hit rate statistics / 缓存命中率统计 ==========

    @staticmethod
    async def _record_hit(redis: Any, hit: bool) -> None:
        """Record cache hit/miss / 记录缓存命中/未命中"""
        try:
            if hit:
                await redis.hincrby(AIResponseCache.STATS_KEY, "hits", 1)
            else:
                await redis.hincrby(AIResponseCache.STATS_KEY, "misses", 1)
        except RedisError:
            pass  # Stats failure doesn't affect main flow / 统计失败不影响主流程

    @staticmethod
    async def get_hit_rate() -> dict:
        """
        Get cache hit rate statistics.
        获取缓存命中率统计。

        Returns:
            {
                "hits": int,
                "misses": int,
                "total": int,
                "hit_rate": float  # 0.0 ~ 1.0
            }
        """
        try:
            redis = await get_redis()
            stats = await redis.hgetall(AIResponseCache.STATS_KEY)

            hits = int(stats.get("hits", 0) or 0)
            misses = int(stats.get("misses", 0) or 0)
            total = hits + misses
            hit_rate = hits / total if total > 0 else 0.0

            return {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate": round(hit_rate, 4),
            }
        except RedisError as e:
            logger.error("Cache get hit rate failed: %s", str(e))
            return {"hits": 0, "misses": 0, "total": 0, "hit_rate": 0.0}

    @staticmethod
    async def reset_stats() -> None:
        """Reset cache hit rate statistics / 重置缓存命中率统计"""
        try:
            redis = await get_redis()
            await redis.delete(AIResponseCache.STATS_KEY)
        except RedisError as e:
            logger.error("Cache reset stats failed: %s", str(e))


__all__ = ["AIResponseCache"]
