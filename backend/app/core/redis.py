"""
Redis 服务管理模块 / Redis Service Management Module

提供 Redis 连接池管理、全局客户端实例、缓存工具函数和依赖注入支持
Provides Redis connection pool management, global client instance, cache utility functions and DI support.
"""

import json
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app")


class RedisManager:
    """
    Redis 连接管理器 / Redis Connection Manager

    管理连接池的生命周期，提供全局 Redis 客户端实例
    Manages connection pool lifecycle and provides global Redis client instance.
    """

    _pool: ConnectionPool | None = None
    _client: Redis | None = None

    @classmethod
    async def init(cls) -> None:
        if cls._pool is not None:
            return

        cls._pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        cls._client = Redis(connection_pool=cls._pool)

        await cls._client.ping()
        logger.info(
            f"Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        )

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
        if cls._pool is not None:
            await cls._pool.aclose()
            cls._pool = None
        logger.info("Redis connections closed")

    @classmethod
    def get_client(cls) -> Redis:
        if cls._client is None:
            raise RuntimeError("Redis not initialized. Call RedisManager.init() first.")
        return cls._client

    @classmethod
    async def health_check(cls) -> bool:
        try:
            if cls._client is None:
                return False
            return await cls._client.ping()
        except Exception:
            return False


async def get_redis() -> Redis:
    return RedisManager.get_client()


def get_redis_client() -> Redis:
    return RedisManager.get_client()


# ========================================
# 缓存工具函数 / Cache Utility Functions
# ========================================


async def cache_get(key: str) -> Any | None:
    client = get_redis_client()
    value = await client.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def cache_set(key: str, value: Any, ttl: int | None = None) -> bool:
    client = get_redis_client()
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    if ttl is not None:
        return await client.setex(key, ttl, serialized)
    return await client.set(key, serialized)


async def cache_delete(key: str) -> int:
    client = get_redis_client()
    return await client.delete(key)


async def cache_exists(key: str) -> bool:
    client = get_redis_client()
    return bool(await client.exists(key))
