"""
WebSocket 平台配置读取 / WebSocket platform config reader.

Reads WS and notification config from system_configs table, uses Redis cache to reduce DB queries.
Called by hot paths like Namespace on_connect, NotificationService, etc.
从 system_configs 表读取 WS 和通知相关配置，使用 Redis 缓存减少 DB 查询。
Namespace on_connect、NotificationService 等热路径调用此模块获取配置值。
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import LogManager
from app.core.redis import get_redis_client

logger = LogManager.get_logger("app")

# Redis cache key prefix and TTL / Redis 缓存 key 前缀和 TTL
_CACHE_PREFIX = "ws_cfg:"
_CACHE_TTL = 120  # seconds (config changes take up to 2 min to take effect) / 秒（配置变更最多 2 分钟生效）

# Config defaults (consistent with configs/definitions/platform/websocket.py) / 配置项默认值（与 configs/definitions/platform/websocket.py 保持一致）
_DEFAULTS: dict[str, Any] = {
    "ws_enabled": True,
    "ws_ping_interval": 25,
    "ws_ping_timeout": 20,
    "ws_max_connections_per_user": 5,
    "notification_enabled": True,
    "notification_retention_days": 90,
    "notification_max_per_user": 500,
}


async def get_ws_config(key: str) -> Any:
    """
    Get WS/notification config value (Redis cache → DB → default).
    获取 WS/通知配置值（Redis 缓存 → DB → 默认值）。

    Args:
        key: Config key (e.g. 'ws_enabled', 'ws_max_connections_per_user') /
            配置项 key（如 'ws_enabled'、'ws_max_connections_per_user'）

    Returns:
        Config value (deserialized) / 配置值（已反序列化）
    """
    default = _DEFAULTS.get(key)

    # 1. Try Redis cache / 尝试 Redis 缓存
    try:
        redis = get_redis_client()
        cached = await redis.get(f"{_CACHE_PREFIX}{key}")
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass

    # 2. Read from DB / 从 DB 读取
    try:
        from app.configs.service import ConfigService
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            service = ConfigService(db)
            value = await service.get_platform_config(key)

        if value is not None:
            # Write to cache / 写入缓存
            try:
                redis = get_redis_client()
                await redis.set(
                    f"{_CACHE_PREFIX}{key}",
                    json.dumps(value),
                    ex=_CACHE_TTL,
                )
            except Exception:
                pass
            return value
    except Exception as e:
        logger.warning("ws_config read failed for key=%s: %s", key, e)

    return default


async def get_ws_configs(*keys: str) -> dict[str, Any]:
    """
    Batch get multiple WS/notification config values.
    批量获取多个 WS/通知配置值。

    Args:
        *keys: Config key list / 配置项 key 列表

    Returns:
        {key: value, ...}
    """
    result = {}
    # Batch read from Redis / 批量从 Redis 读取
    uncached_keys: list[str] = []
    try:
        redis = get_redis_client()
        for key in keys:
            cached = await redis.get(f"{_CACHE_PREFIX}{key}")
            if cached is not None:
                result[key] = json.loads(cached)
            else:
                uncached_keys.append(key)
    except Exception:
        uncached_keys = list(keys)

    # Read uncached from DB / 未命中的从 DB 读取
    if uncached_keys:
        try:
            from app.configs.service import ConfigService
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                service = ConfigService(db)
                for key in uncached_keys:
                    value = await service.get_platform_config(key)
                    if value is not None:
                        result[key] = value
                        # Write to cache / 写入缓存
                        try:
                            redis = get_redis_client()
                            await redis.set(
                                f"{_CACHE_PREFIX}{key}",
                                json.dumps(value),
                                ex=_CACHE_TTL,
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("ws_config batch read failed: %s", e)

    # Fill in defaults / 补充默认值
    for key in keys:
        if key not in result:
            result[key] = _DEFAULTS.get(key)

    return result


async def invalidate_ws_config_cache() -> None:
    """
    Clear WS config cache (called after config save) / 清除 WS 配置缓存（配置保存后调用）
    """
    try:
        redis = get_redis_client()
        for key in _DEFAULTS:
            await redis.delete(f"{_CACHE_PREFIX}{key}")
    except Exception:
        pass


__all__ = [
    "get_ws_config",
    "get_ws_configs",
    "invalidate_ws_config_cache",
]
