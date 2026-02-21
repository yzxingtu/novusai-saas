"""在线状态管理

使用 Redis Hash + 原子 Lua 脚本存储用户在线状态，支持多设备连接计数。
集成到 Socket.IO namespace 的 connect/disconnect 事件中。
"""

from __future__ import annotations

from typing import Any

from app.core.logging import LogManager
from app.core.redis import get_redis_client

logger = LogManager.get_logger("app")

PRESENCE_KEY_PREFIX = "presence:"

# Presence Hash TTL（秒）— 防止 worker 崩溃后 stale 数据永久残留
PRESENCE_TTL = 86400  # 24 小时

# Lua: 原子递增连接数并刷新 Hash TTL，返回新值
_LUA_INCR = """
local cur = redis.call('HINCRBY', KEYS[1], ARGV[1], 1)
redis.call('EXPIRE', KEYS[1], ARGV[2])
return cur
"""

# Lua: 原子递减连接数，归零时自动删除 field，返回新值
_LUA_DECR = """
local cur = redis.call('HINCRBY', KEYS[1], ARGV[1], -1)
if cur <= 0 then
    redis.call('HDEL', KEYS[1], ARGV[1])
    return 0
end
return cur
"""


def _presence_key(user_type: str, tenant_id: int | None = None) -> str:
    """
    构建 Redis Hash key

    Args:
        user_type: admin / tenant_admin / tenant_user
        tenant_id: 租户 ID（admin 端为 None）

    Returns:
        Redis key，如 presence:admin 或 presence:tenant_admin:5
    """
    if user_type == "admin":
        return f"{PRESENCE_KEY_PREFIX}admin"
    if tenant_id is not None:
        return f"{PRESENCE_KEY_PREFIX}{user_type}:{tenant_id}"
    return f"{PRESENCE_KEY_PREFIX}{user_type}"


# Lua: 原子递增计数并在首次创建时设置 TTL，避免 INCR/EXPIRE 分离导致 key 永不过期
_LUA_RATE = """
local count = redis.call('INCR', KEYS[1])
if redis.call('TTL', KEYS[1]) == -1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


async def check_connect_rate(user_type: str, user_id: int, window: int = 60, max_connects: int = 20) -> bool:
    """
    检查连接频率限制（原子操作）

    Args:
        user_type: 用户类型
        user_id: 用户 ID
        window: 时间窗口（秒）
        max_connects: 窗口内最大连接次数

    Returns:
        True=允许连接, False=被限流
    """
    redis = get_redis_client()
    key = f"sio_rate:{user_type}:{user_id}"
    count = await redis.eval(_LUA_RATE, 1, key, str(window))
    if count > max_connects:
        logger.warning(
            "SIO rate limit exceeded: %s user_id=%d count=%d",
            user_type, user_id, count,
        )
        return False
    return True


class PresenceManager:
    """
    在线状态管理器

    Redis Hash 存储结构（简化为纯数字，不再用 JSON）：
    - presence:admin → { "5": "2", "8": "1" }
    - presence:tenant_admin:1 → { "12": "1" }
    - presence:tenant_user:1 → { "100": "1" }

    所有写操作通过 Lua 脚本保证原子性，避免竞态条件。
    """

    @staticmethod
    async def set_online(
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> int:
        """
        标记用户上线（原子递增连接数）

        Returns:
            更新后的连接数
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        connections = await redis.eval(_LUA_INCR, 1, key, str(user_id), str(PRESENCE_TTL))

        logger.debug(
            "Presence set_online: %s user_id=%d tenant_id=%s connections=%d",
            user_type, user_id, tenant_id, connections,
        )
        return int(connections)

    @staticmethod
    async def set_offline(
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> int:
        """
        标记用户下线（原子递减连接数，归零自动删除）

        Returns:
            更新后的连接数（0 表示完全离线）
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        connections = await redis.eval(_LUA_DECR, 1, key, str(user_id))

        logger.debug(
            "Presence set_offline: %s user_id=%d tenant_id=%s connections=%d",
            user_type, user_id, tenant_id, connections,
        )
        return int(connections)

    @staticmethod
    async def get_online_ids(
        user_type: str,
        tenant_id: int | None = None,
    ) -> list[int]:
        """
        获取在线用户 ID 列表
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        fields = await redis.hkeys(key)
        return [int(f) for f in fields if f.isdigit()]

    @staticmethod
    async def get_online_details(
        user_type: str,
        tenant_id: int | None = None,
    ) -> dict[int, dict[str, Any]]:
        """
        获取在线用户详细信息

        Returns:
            { user_id: {"connections": N}, ... }
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        raw_data = await redis.hgetall(key)

        result: dict[int, dict[str, Any]] = {}
        for field, value in raw_data.items():
            try:
                uid = int(field)
                connections = int(value)
                result[uid] = {"connections": connections}
            except (ValueError, TypeError):
                continue
        return result

    @staticmethod
    async def is_online(
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> bool:
        """
        检查用户是否在线
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        return bool(await redis.hexists(key, str(user_id)))

    @staticmethod
    async def get_user_connection_count(
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> int:
        """
        获取用户连接数（0 表示离线）
        """
        redis = get_redis_client()
        key = _presence_key(user_type, tenant_id)
        raw = await redis.hget(key, str(user_id))
        if not raw:
            return 0
        try:
            return max(int(raw), 0)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    async def clear_all() -> int:
        """
        清空所有在线状态数据（服务器启动时调用）

        Returns:
            清除的 key 数量
        """
        redis = get_redis_client()
        cursor = "0"
        deleted = 0
        while True:
            cursor, keys = await redis.scan(
                cursor=cursor,
                match=f"{PRESENCE_KEY_PREFIX}*",
                count=100,
            )
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == 0 or cursor == "0" or cursor == b"0":
                break

        if deleted > 0:
            logger.info("Presence cleared on startup: %d keys removed", deleted)
        return deleted


__all__ = ["PresenceManager"]
