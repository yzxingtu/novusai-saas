"""
Agent concurrency limiter / 智能体并发控制器
"""

from importlib import import_module
import time
import uuid

from app.ai.agent_quota_exceptions import AgentConcurrencyExceeded
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.agent_quota")


class AgentConcurrencyLimiter:
    """
    Agent Concurrency Limiter / 智能体并发执行限制器

    Distributed semaphore via Redis Sorted Set (member=lock_token, score=expire_timestamp).
    Auto-cleans expired entries so abnormal releases won't cause permanent occupation.
    使用 Redis Sorted Set 实现分布式信号量，member=lock_token, score=expire_timestamp。
    自动清理过期项，确保异常未释放时不会永久占用。

    Usage::

        token = await AgentConcurrencyLimiter.acquire(
            tenant_id=1, agent_id=42, max_concurrent=5,
        )
        try:
            ...
        finally:
            await AgentConcurrencyLimiter.release(tenant_id=1, agent_id=42, lock_token=token)
    """

    PREFIX = "ai:agent_concurrency:"
    PREFIX_TENANT = "ai:agent_concurrency:tenant:"
    LOCK_TTL = 300  # 5 分钟自动过期 / 5-minute TTL auto-expiry

    # Lua script: atomic cleanup-expired → check-count → add-token
    # Lua 脚本：原子化 清理过期 → 检查计数 → 添加令牌
    # Returns -1 on success, >= 0 = current concurrency (exceeded, not added)
    # 返回 -1 表示成功添加，>= 0 表示当前并发数（超限未添加）
    _ACQUIRE_LUA = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
    local current = redis.call('ZCARD', KEYS[1])
    if current >= tonumber(ARGV[2]) then
        return current
    end
    redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
    return -1
    """

    @staticmethod
    async def _get_redis():
        quota_module = import_module("app.ai.agent_quota")
        return await getattr(quota_module, "get_redis")()

    @staticmethod
    def _key(tenant_id: int, agent_id: int) -> str:
        return f"{AgentConcurrencyLimiter.PREFIX}{tenant_id}:{agent_id}"

    @staticmethod
    def _tenant_key(tenant_id: int) -> str:
        return f"{AgentConcurrencyLimiter.PREFIX_TENANT}{tenant_id}"

    @staticmethod
    async def acquire(
        tenant_id: int,
        agent_id: int,
        max_concurrent: int = 10,
        tenant_max_concurrent: int = 0,
    ) -> str:
        """
        Acquire concurrency permit (atomic, prevents TOCTOU race).
        获取并发许可（原子操作，防止 TOCTOU 竞态）。

        Uses Redis Lua script for atomic cleanup → check → add.
        使用 Redis Lua 脚本确保 清理过期→检查计数→添加令牌 三步原子执行。

        Args:
            tenant_id: Tenant ID / 企业 ID
            agent_id: Agent ID / 智能体 ID
            max_concurrent: Per-agent max concurrency / 每智能体最大并发数
            tenant_max_concurrent: Tenant-wide max concurrency / 全企业最大并发数

        Returns:
            lock_token for release / lock_token 用于释放

        Raises:
            AgentConcurrencyExceeded: Concurrency exceeded / 并发超出
        """
        redis = await AgentConcurrencyLimiter._get_redis()
        now = time.time()
        expire_at = now + AgentConcurrencyLimiter.LOCK_TTL
        lock_token = uuid.uuid4().hex

        # Agent-level concurrency check (atomic) / 智能体级并发检查（原子操作）
        if max_concurrent > 0:
            agent_key = AgentConcurrencyLimiter._key(tenant_id, agent_id)
            result = await redis.eval(
                AgentConcurrencyLimiter._ACQUIRE_LUA,
                1,
                agent_key,
                str(now),
                str(max_concurrent),
                str(expire_at),
                lock_token,
            )
            if result >= 0:
                logger.warning(
                    "Agent concurrency exceeded: tenant={} agent={} current={} max={}",
                    tenant_id,
                    agent_id,
                    int(result),
                    max_concurrent,
                )
                raise AgentConcurrencyExceeded(
                    _("agent.error.concurrency_exceeded"),
                    retry_after=5,
                )

        # Tenant-level concurrency check (atomic) / 企业级并发检查（原子操作）
        if tenant_max_concurrent > 0:
            tenant_key = AgentConcurrencyLimiter._tenant_key(tenant_id)
            result = await redis.eval(
                AgentConcurrencyLimiter._ACQUIRE_LUA,
                1,
                tenant_key,
                str(now),
                str(tenant_max_concurrent),
                str(expire_at),
                lock_token,
            )
            if result >= 0:
                # Rollback agent-level / 回滚智能体级
                if max_concurrent > 0:
                    agent_key = AgentConcurrencyLimiter._key(tenant_id, agent_id)
                    await redis.zrem(agent_key, lock_token)
                raise AgentConcurrencyExceeded(
                    _("agent.error.tenant_concurrency_exceeded"),
                    retry_after=5,
                )

        return lock_token

    @staticmethod
    async def release(
        tenant_id: int,
        agent_id: int,
        lock_token: str,
    ) -> None:
        """
        Release concurrency permit.
        释放并发许可。

        Args:
            tenant_id: Tenant ID / 企业 ID
            agent_id: Agent ID / 智能体 ID
            lock_token: Token returned by acquire() / acquire() 返回的令牌
        """
        redis = await AgentConcurrencyLimiter._get_redis()
        agent_key = AgentConcurrencyLimiter._key(tenant_id, agent_id)
        tenant_key = AgentConcurrencyLimiter._tenant_key(tenant_id)
        await redis.zrem(agent_key, lock_token)
        await redis.zrem(tenant_key, lock_token)

    @staticmethod
    async def get_current(
        tenant_id: int,
        agent_id: int,
    ) -> int:
        """Get current concurrency count / 获取当前并发数"""
        redis = await AgentConcurrencyLimiter._get_redis()
        key = AgentConcurrencyLimiter._key(tenant_id, agent_id)
        now = time.time()
        await redis.zremrangebyscore(key, "-inf", now)
        return await redis.zcard(key)


__all__ = ["AgentConcurrencyLimiter"]
