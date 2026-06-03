"""
Agent Usage Statistics / 智能体用量统计

Tracks per-agent conversation counts and token consumption via Redis Hash,
支持总量和当日两个维度的智能体对话次数和 Token 消耗统计。
"""

from datetime import date
from typing import Any

from app.core.logging import LogManager
from app.core.redis import get_redis

logger = LogManager.get_logger("ai.agent_stats")

# Redis key prefix / Redis Key 前缀
_PREFIX = "ai:agent_stats"

# Lua script: atomic date-check + reset + increment
# Lua 脚本：原子化日期检查 + 重置 + 增量
# KEYS[1] = hash key, ARGV[1] = today (ISO), ARGV[2] = tokens
_RECORD_CHAT_LUA = """
local key = KEYS[1]
local today = ARGV[1]
local tokens = tonumber(ARGV[2])

local stored_date = redis.call('HGET', key, 'today_date')
if stored_date ~= today then
    redis.call('HSET', key, 'today_conversations', 0, 'today_tokens', 0, 'today_date', today)
end

redis.call('HINCRBY', key, 'total_conversations', 1)
redis.call('HINCRBY', key, 'total_tokens', tokens)
redis.call('HINCRBY', key, 'today_conversations', 1)
redis.call('HINCRBY', key, 'today_tokens', tokens)
return 1
"""


class AgentStatsManager:
    """
    Agent Usage Statistics Manager / 智能体用量统计管理器

    Each agent uses a Redis Hash to store statistics:
    每个智能体使用一个 Redis Hash 存储统计数据:
    - total_conversations: Cumulative conversation count / 累计对话次数
    - total_tokens: Cumulative token consumption / 累计 Token 消耗
    - today_conversations: Today's conversation count / 当日对话次数
    - today_tokens: Today's token consumption / 当日 Token 消耗
    - today_date: Date for auto-reset / 当日统计日期（用于自动重置）

    record_chat uses a Lua script for atomic date-check + reset + increment,
    preventing lost counts during date transitions under concurrency.
    record_chat 使用 Lua 脚本保证日期检查+重置+增量的原子性，
    避免并发请求在日期切换时丢失计数。

    Usage::

        await AgentStatsManager.record_chat(tenant_id=1, agent_id=42, tokens=350)
        stats = await AgentStatsManager.get_stats(tenant_id=1, agent_id=42)
    """

    @staticmethod
    def _key(tenant_id: int, agent_id: int) -> str:
        return f"{_PREFIX}:{tenant_id}:{agent_id}"

    @staticmethod
    async def record_chat(
        tenant_id: int,
        agent_id: int,
        tokens: int = 0,
    ) -> None:
        """
        Record a completed conversation (atomic operation).
        记录一次对话完成（原子操作）。

        Uses Lua script for atomic date-check, reset, and increment on Redis side,
        preventing lost counts during date transitions.
        使用 Lua 脚本在 Redis 端原子化执行日期检查、重置和增量，
        避免并发请求在日期切换时丢失计数。

        Args:
            tenant_id: Tenant ID / 企业 ID
            agent_id: Agent ID / 智能体 ID
            tokens: Tokens consumed in this conversation / 本次消耗的 Token 数量
        """
        redis = await get_redis()
        key = AgentStatsManager._key(tenant_id, agent_id)
        today = date.today().isoformat()

        await redis.eval(
            _RECORD_CHAT_LUA,
            1,
            key,
            today,
            str(tokens),
        )

    @staticmethod
    async def get_stats(
        tenant_id: int,
        agent_id: int,
    ) -> dict[str, Any]:
        """
        Get agent usage statistics.
        获取智能体用量统计。

        Args:
            tenant_id: Tenant ID / 企业 ID
            agent_id: Agent ID / 智能体 ID

        Returns:
            Statistics dictionary / 统计数据字典
        """
        redis = await get_redis()
        key = AgentStatsManager._key(tenant_id, agent_id)
        today = date.today().isoformat()

        raw = await redis.hgetall(key)
        if not raw:
            return {
                "total_conversations": 0,
                "total_tokens": 0,
                "today_conversations": 0,
                "today_tokens": 0,
                "date": today,
            }

        # If date mismatch, reset today's counts / 如果日期不一致，当日计数归零
        stored_date = raw.get("today_date", "")
        if stored_date != today:
            today_conv = 0
            today_tok = 0
        else:
            today_conv = int(raw.get("today_conversations", 0))
            today_tok = int(raw.get("today_tokens", 0))

        return {
            "total_conversations": int(raw.get("total_conversations", 0)),
            "total_tokens": int(raw.get("total_tokens", 0)),
            "today_conversations": today_conv,
            "today_tokens": today_tok,
            "date": today,
        }

    @staticmethod
    async def reset_daily_stats() -> int:
        """
        Reset daily stats for all agents (called by Celery Beat daily).
        重置所有智能体的当日统计（供 Celery Beat 每日调用）。

        Returns:
            Number of agents reset / 重置的智能体数量
        """
        redis = await get_redis()
        cursor: int = 0
        count = 0
        today = date.today().isoformat()

        while True:
            cursor, keys = await redis.scan(
                cursor=cursor,
                match=f"{_PREFIX}:*",
                count=200,
            )
            for key in keys:
                await redis.hset(
                    key,
                    mapping={
                        "today_conversations": 0,
                        "today_tokens": 0,
                        "today_date": today,
                    },
                )
                count += 1

            if cursor == 0:
                break

        logger.info("Daily stats reset: count={}", count)
        return count


__all__ = ["AgentStatsManager"]
