"""
Agent-level Quota & Concurrency Control
智能体级配额与并发控制

Provides per-agent Token quota and concurrency limits on top of tenant-level quota.
Redis-based for low latency and high concurrency safety.
在租户级配额之上，提供按智能体粒度的 Token 配额和并发执行数限制。
基于 Redis 实现，低延迟、高并发安全。
"""

import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.ai.events.bus import get_event_bus
from app.ai.events.types import QuotaExceeded as QuotaExceededEvent
from app.ai.events.types import QuotaWarning
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.exceptions.base import BusinessException

logger = LogManager.get_logger("ai.agent_quota")


# ============================================
# Exceptions / 异常
# ============================================

class AgentQuotaExceeded(BusinessException):
    """Agent quota exceeded exception / 智能体配额超出异常"""

    code = 4293
    status_code = 429
    default_message = "ai.error.quota_exceeded_default"

    def __init__(self, message: str, quota_type: str = "", current: int = 0, limit: int = 0):
        super().__init__(message=message)
        self.quota_type = quota_type
        self.current = current
        self.limit = limit


class AgentConcurrencyExceeded(BusinessException):
    """Agent concurrency exceeded exception / 智能体并发超出异常"""

    code = 4294
    status_code = 429
    default_message = "ai.agent.concurrency_exceeded"

    def __init__(self, message: str, retry_after: int = 5):
        super().__init__(message=message)
        self.retry_after = retry_after


# ============================================
# Quota Configuration / 配额配置
# ============================================

@dataclass
class AgentQuotaConfig:
    """
    Agent Quota Configuration / 智能体配额配置

    Attributes:
        daily_token_limit: Daily token cap (0 = unlimited) / 每日 Token 上限（0 = 不限制）
        monthly_token_limit: Monthly token cap (0 = unlimited) / 每月 Token 上限（0 = 不限制）
        conversations_per_day: Max daily conversations (0 = unlimited) / 每日最大对话数（0 = 不限制）
        max_turns_per_conversation: Max turns per conversation (0 = unlimited) / 单次对话最大轮次（0 = 不限制）
        max_tokens_per_conversation: Max tokens per conversation (0 = unlimited) / 单次对话最大 Token（0 = 不限制）
        user_conversations_per_day: Per-user daily conversation cap (0 = unlimited) / 每用户每日对话上限（0 = 不限制）
        user_tokens_per_day: Per-user daily token cap (0 = unlimited) / 每用户每日 Token 上限（0 = 不限制）
        max_concurrent: Max concurrent executions (0 = unlimited) / 最大并发执行数（0 = 不限制）
        tenant_max_concurrent: Tenant-wide max concurrency (0 = unlimited) / 全租户最大并发（0 = 不限制）
        warning_threshold: Warning threshold percentage (0-100) / 预警阈值百分比（0-100）
    """

    daily_token_limit: int = 0
    monthly_token_limit: int = 0
    conversations_per_day: int = 0
    max_turns_per_conversation: int = 50
    max_tokens_per_conversation: int = 0
    user_conversations_per_day: int = 0
    user_tokens_per_day: int = 0
    max_concurrent: int = 10
    tenant_max_concurrent: int = 50
    warning_threshold: int = 80

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AgentQuotaConfig":
        """Build config from Agent.quota_config JSON field / 从 Agent.quota_config JSON 字段构建配置"""
        if not data:
            return cls()
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields and v is not None}
        return cls(**filtered)


# ============================================
# Quota Manager / 配额管理器
# ============================================

class AgentQuotaManager:
    """
    Agent Quota Manager / 智能体配额管理器

    Tracks per-agent Token usage via Redis, supporting daily and monthly quota checks.
    基于 Redis 追踪每个智能体的 Token 使用量，支持每日和每月两个维度的配额检查。

    Usage::

        manager = AgentQuotaManager()
        await manager.check_quota(tenant_id=1, agent_id=42, estimated_tokens=500)
        await manager.record_usage(tenant_id=1, agent_id=42, tokens=350)
    """

    PREFIX_DAILY = "ai:agent_quota:daily:"
    PREFIX_MONTHLY = "ai:agent_quota:monthly:"
    PREFIX_DAILY_CONV = "ai:agent_quota:daily_conv:"
    PREFIX_USER = "ai:agent_quota:user:"

    # Lua script: atomically adjust usage (INCRBY + floor-at-zero guard)
    # Lua 脚本：原子调整用量（INCRBY + 不低于 0 保护）
    # KEYS[1] = key, ARGV[1] = diff
    _ADJUST_LUA = """
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    if new_val < 0 then
        redis.call('SET', KEYS[1], '0', 'KEEPTTL')
        return 0
    end
    return new_val
    """

    # Lua script: atomic pre-deduct + check (same pattern as UsageTracker)
    # Lua 脚本：原子预扣减+检查（与 UsageTracker 同模式）
    # KEYS[1] = key, ARGV[1] = estimated_tokens, ARGV[2] = limit, ARGV[3] = expire_seconds
    # Returns -1 on success (pre-deducted), >= 0 = current usage (exceeded, rolled back)
    # 返回 -1 表示成功（已预扣），>= 0 表示当前用量（超限，已回滚）
    _CHECK_AND_RECORD_LUA = """
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
    if new_val > tonumber(ARGV[2]) then
        redis.call('DECRBY', KEYS[1], ARGV[1])
        return new_val - tonumber(ARGV[1])
    end
    return -1
    """

    @staticmethod
    async def _atomic_check_and_record(
        key: str,
        estimated_tokens: int,
        limit: int,
        expire_seconds: int,
    ) -> int:
        """
        Atomically check + pre-deduct token usage.
        原子检查+预扣减 Token 使用量。

        Returns:
            -1 on success (pre-deducted), >= 0 = current usage (exceeded, rolled back)
            -1 表示成功（已预扣），>= 0 表示当前用量（超限，已回滚）
        """
        redis = await get_redis()
        result = await redis.eval(
            AgentQuotaManager._CHECK_AND_RECORD_LUA,
            1,
            key,
            str(estimated_tokens),
            str(limit),
            str(expire_seconds),
        )
        return int(result)

    @staticmethod
    def _daily_key(tenant_id: int, agent_id: int, stat_date: date) -> str:
        return f"{AgentQuotaManager.PREFIX_DAILY}{tenant_id}:{agent_id}:{stat_date.isoformat()}"

    @staticmethod
    def _monthly_key(tenant_id: int, agent_id: int, year: int, month: int) -> str:
        return f"{AgentQuotaManager.PREFIX_MONTHLY}{tenant_id}:{agent_id}:{year}-{month:02d}"

    @staticmethod
    def _daily_conv_key(tenant_id: int, agent_id: int, stat_date: date) -> str:
        return f"{AgentQuotaManager.PREFIX_DAILY_CONV}{tenant_id}:{agent_id}:{stat_date.isoformat()}"

    @staticmethod
    def _user_daily_key(tenant_id: int, agent_id: int, user_id: int, stat_date: date) -> str:
        return f"{AgentQuotaManager.PREFIX_USER}{tenant_id}:{agent_id}:{user_id}:daily:{stat_date.isoformat()}"

    @staticmethod
    async def check_quota(
        tenant_id: int,
        agent_id: int,
        config: AgentQuotaConfig,
        estimated_tokens: int = 0,
    ) -> bool:
        """
        Check agent quota.
        检查智能体配额。

        Args:
            tenant_id: Tenant ID / 租户 ID
            agent_id: Agent ID / 智能体 ID
            config: Quota config / 配额配置
            estimated_tokens: Estimated token count / 预估 Token 数量

        Returns:
            True if allowed / True 表示允许

        Raises:
            AgentQuotaExceeded: Quota exceeded / 配额超出
        """
        today = date.today()
        event_bus = get_event_bus()

        # Daily quota check (atomic pre-deduct, prevents TOCTOU race)
        # 日配额检查（原子预扣减，防止 TOCTOU 竞态）
        if config.daily_token_limit > 0 and estimated_tokens > 0:
            daily_key = AgentQuotaManager._daily_key(tenant_id, agent_id, today)
            result = await AgentQuotaManager._atomic_check_and_record(
                key=daily_key,
                estimated_tokens=estimated_tokens,
                limit=config.daily_token_limit,
                expire_seconds=86400 * 2,
            )

            if result >= 0:
                # Exceeded: result is current usage after rollback
                # 超限：result 是回滚后的当前用量
                logger.warning(
                    "Agent daily quota exceeded: tenant=%d agent=%d usage=%d limit=%d",
                    tenant_id,
                    agent_id,
                    result + estimated_tokens,
                    config.daily_token_limit,
                )
                await event_bus.publish(QuotaExceededEvent(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    quota_type="daily",
                ))
                raise AgentQuotaExceeded(
                    _("agent.error.daily_quota_exceeded"),
                    quota_type="daily_tokens",
                    current=result + estimated_tokens,
                    limit=config.daily_token_limit,
                )

            # Warning check (after successful pre-deduction)
            # 预警检查（在预扣成功后）
            if config.warning_threshold > 0:
                daily_usage = await AgentQuotaManager.get_daily_usage(
                    tenant_id, agent_id, today,
                )
                usage_pct = (daily_usage / config.daily_token_limit) * 100
                if usage_pct >= config.warning_threshold:
                    await event_bus.publish(QuotaWarning(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        usage_percent=usage_pct,
                        threshold=config.warning_threshold,
                    ))

        # Daily conversation count check / 日对话数检查
        if config.conversations_per_day > 0:
            conv_count = await AgentQuotaManager.get_daily_conversations(
                tenant_id, agent_id, today,
            )
            if conv_count >= config.conversations_per_day:
                raise AgentQuotaExceeded(
                    _("agent.error.daily_conversation_quota_exceeded"),
                    quota_type="daily_conversations",
                    current=conv_count,
                    limit=config.conversations_per_day,
                )

        # Monthly quota check (atomic pre-deduct) / 月配额检查（原子预扣减）
        if config.monthly_token_limit > 0 and estimated_tokens > 0:
            monthly_key = AgentQuotaManager._monthly_key(
                tenant_id, agent_id, today.year, today.month,
            )
            result = await AgentQuotaManager._atomic_check_and_record(
                key=monthly_key,
                estimated_tokens=estimated_tokens,
                limit=config.monthly_token_limit,
                expire_seconds=86400 * 35,
            )

            if result >= 0:
                logger.warning(
                    "Agent monthly quota exceeded: tenant=%d agent=%d usage=%d limit=%d",
                    tenant_id,
                    agent_id,
                    result + estimated_tokens,
                    config.monthly_token_limit,
                )
                await event_bus.publish(QuotaExceededEvent(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    quota_type="monthly",
                ))
                # Rollback daily pre-deduction (atomic, prevents negative)
                # 回滚日配额预扣减（原子操作，防止值为负）
                if config.daily_token_limit > 0:
                    await AgentQuotaManager._atomic_adjust(
                        AgentQuotaManager._daily_key(tenant_id, agent_id, today),
                        -estimated_tokens,
                    )

                raise AgentQuotaExceeded(
                    _("agent.error.monthly_quota_exceeded"),
                    quota_type="monthly_tokens",
                    current=result + estimated_tokens,
                    limit=config.monthly_token_limit,
                )

            # Warning check / 预警检查
            if config.warning_threshold > 0:
                monthly_usage = await AgentQuotaManager.get_monthly_usage(
                    tenant_id, agent_id, today.year, today.month,
                )
                usage_pct = (monthly_usage / config.monthly_token_limit) * 100
                if usage_pct >= config.warning_threshold:
                    await event_bus.publish(QuotaWarning(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        usage_percent=usage_pct,
                        threshold=config.warning_threshold,
                    ))

        return True

    @staticmethod
    async def _atomic_adjust(key: str, diff: int) -> int:
        """
        Atomically adjust usage (INCRBY + floor-at-zero guard).
        原子调整用量（INCRBY + 不低于 0 保护）。

        Args:
            key: Redis key / Redis 键
            diff: Adjustment amount (positive or negative) / 调整量（可正可负）

        Returns:
            Adjusted value / 调整后的值
        """
        redis = await get_redis()
        result = await redis.eval(
            AgentQuotaManager._ADJUST_LUA,
            1,
            key,
            str(diff),
        )
        return int(result)

    @staticmethod
    async def adjust_usage(
        tenant_id: int,
        agent_id: int,
        estimated_tokens: int,
        actual_tokens: int,
        config: AgentQuotaConfig | None = None,
    ) -> None:
        """
        Adjust quota usage after response: from estimated to actual.
        响应后调整配额用量：从预估值调整为实际值。

        Args:
            tenant_id: Tenant ID / 租户 ID
            agent_id: Agent ID / 智能体 ID
            estimated_tokens: Estimated tokens (pre-deducted) / 预估 Token 数量（已预扣）
            actual_tokens: Actual token count / 实际 Token 数量
            config: Quota config (optional, to determine which dimensions to adjust) / 配额配置（可选，用于判断哪些维度需要调整）
        """
        diff = actual_tokens - estimated_tokens
        if diff == 0:
            return

        today = date.today()

        # Adjust daily quota / 调整日配额
        if not config or config.daily_token_limit > 0:
            daily_key = AgentQuotaManager._daily_key(tenant_id, agent_id, today)
            await AgentQuotaManager._atomic_adjust(daily_key, diff)

        # Adjust monthly quota / 调整月配额
        if not config or config.monthly_token_limit > 0:
            monthly_key = AgentQuotaManager._monthly_key(
                tenant_id, agent_id, today.year, today.month,
            )
            await AgentQuotaManager._atomic_adjust(monthly_key, diff)

    @staticmethod
    async def record_usage(
        tenant_id: int,
        agent_id: int,
        tokens: int,
        stat_date: date | None = None,
    ) -> None:
        """
        Record agent token usage.
        记录智能体 Token 使用量。

        Args:
            tenant_id: Tenant ID / 租户 ID
            agent_id: Agent ID / 智能体 ID
            tokens: Token count / Token 数量
            stat_date: Statistics date / 统计日期
        """
        redis = await get_redis()
        stat_date = stat_date or date.today()

        # Daily / 每日
        daily_key = AgentQuotaManager._daily_key(tenant_id, agent_id, stat_date)
        await redis.incrby(daily_key, tokens)
        await redis.expire(daily_key, 86400 * 2)

        # Monthly / 每月
        monthly_key = AgentQuotaManager._monthly_key(
            tenant_id, agent_id, stat_date.year, stat_date.month,
        )
        await redis.incrby(monthly_key, tokens)
        await redis.expire(monthly_key, 86400 * 35)

    @staticmethod
    async def check_user_quota(
        tenant_id: int,
        agent_id: int,
        user_id: int,
        config: AgentQuotaConfig,
    ) -> bool:
        """
        Check user-level quota.
        检查用户级配额。

        Raises:
            AgentQuotaExceeded: User-level quota exceeded / 用户级配额超出
        """
        if not user_id:
            return True

        today = date.today()
        redis = await get_redis()
        key = AgentQuotaManager._user_daily_key(tenant_id, agent_id, user_id, today)

        if config.user_conversations_per_day > 0:
            conv_val = await redis.hget(key, "conversations")
            conv_count = int(conv_val) if conv_val else 0
            if conv_count >= config.user_conversations_per_day:
                raise AgentQuotaExceeded(
                    _("agent.error.user_daily_conversation_exceeded"),
                    quota_type="user_daily_conversations",
                    current=conv_count,
                    limit=config.user_conversations_per_day,
                )

        if config.user_tokens_per_day > 0:
            token_val = await redis.hget(key, "tokens")
            token_count = int(token_val) if token_val else 0
            if token_count >= config.user_tokens_per_day:
                raise AgentQuotaExceeded(
                    _("agent.error.user_daily_token_exceeded"),
                    quota_type="user_daily_tokens",
                    current=token_count,
                    limit=config.user_tokens_per_day,
                )

        return True

    @staticmethod
    async def check_conversation_limits(
        config: AgentQuotaConfig,
        current_turns: int = 0,
        current_tokens: int = 0,
    ) -> bool:
        """
        Check per-conversation limits.
        检查单次对话限制。

        Raises:
            AgentQuotaExceeded: Conversation-level limit exceeded / 对话级限制超出
        """
        if config.max_turns_per_conversation > 0 and current_turns >= config.max_turns_per_conversation:
            raise AgentQuotaExceeded(
                _("agent.error.conversation_turns_exceeded"),
                quota_type="conversation_turns",
                current=current_turns,
                limit=config.max_turns_per_conversation,
            )

        if config.max_tokens_per_conversation > 0 and current_tokens >= config.max_tokens_per_conversation:
            raise AgentQuotaExceeded(
                _("agent.error.conversation_tokens_exceeded"),
                quota_type="conversation_tokens",
                current=current_tokens,
                limit=config.max_tokens_per_conversation,
            )

        return True

    @staticmethod
    async def record_conversation(
        tenant_id: int,
        agent_id: int,
        user_id: int | None = None,
    ) -> None:
        """Record new conversation (agent-level + user-level) / 记录新对话（智能体级 + 用户级）"""
        redis = await get_redis()
        today = date.today()

        # Agent-level daily conversation count / 智能体级日对话数
        conv_key = AgentQuotaManager._daily_conv_key(tenant_id, agent_id, today)
        await redis.incr(conv_key)
        await redis.expire(conv_key, 86400 * 2)

        # User-level daily conversation count / 用户级日对话数
        if user_id:
            user_key = AgentQuotaManager._user_daily_key(tenant_id, agent_id, user_id, today)
            await redis.hincrby(user_key, "conversations", 1)
            await redis.expire(user_key, 86400 * 2)

    @staticmethod
    async def record_user_usage(
        tenant_id: int,
        agent_id: int,
        user_id: int,
        tokens: int,
    ) -> None:
        """Record user-level token usage / 记录用户级 Token 使用量"""
        if not user_id or tokens <= 0:
            return
        redis = await get_redis()
        today = date.today()
        key = AgentQuotaManager._user_daily_key(tenant_id, agent_id, user_id, today)
        await redis.hincrby(key, "tokens", tokens)
        await redis.expire(key, 86400 * 2)

    @staticmethod
    async def get_daily_conversations(
        tenant_id: int,
        agent_id: int,
        stat_date: date | None = None,
    ) -> int:
        """Get agent's daily conversation count / 获取智能体当日对话数"""
        redis = await get_redis()
        stat_date = stat_date or date.today()
        key = AgentQuotaManager._daily_conv_key(tenant_id, agent_id, stat_date)
        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def get_daily_usage(
        tenant_id: int,
        agent_id: int,
        stat_date: date | None = None,
    ) -> int:
        """Get agent's daily token usage / 获取智能体当日 Token 使用量"""
        redis = await get_redis()
        stat_date = stat_date or date.today()
        key = AgentQuotaManager._daily_key(tenant_id, agent_id, stat_date)
        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def get_monthly_usage(
        tenant_id: int,
        agent_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> int:
        """Get agent's monthly token usage / 获取智能体当月 Token 使用量"""
        redis = await get_redis()
        today = date.today()
        year = year or today.year
        month = month or today.month
        key = AgentQuotaManager._monthly_key(tenant_id, agent_id, year, month)
        value = await redis.get(key)
        return int(value) if value else 0

    @staticmethod
    async def get_usage_summary(
        tenant_id: int,
        agent_id: int,
        config: AgentQuotaConfig | None = None,
    ) -> dict[str, Any]:
        """Get usage summary (with quota limits) / 获取使用量摘要（含配额上限）"""
        today = date.today()
        daily_tokens = await AgentQuotaManager.get_daily_usage(tenant_id, agent_id, today)
        monthly_tokens = await AgentQuotaManager.get_monthly_usage(
            tenant_id, agent_id, today.year, today.month,
        )
        daily_conversations = await AgentQuotaManager.get_daily_conversations(
            tenant_id, agent_id, today,
        )
        current_concurrent = await AgentConcurrencyLimiter.get_current(
            tenant_id, agent_id,
        )

        result: dict[str, Any] = {
            "daily_tokens": daily_tokens,
            "monthly_tokens": monthly_tokens,
            "daily_conversations": daily_conversations,
            "current_concurrent": current_concurrent,
            "date": today.isoformat(),
            "month": f"{today.year}-{today.month:02d}",
        }

        if config:
            result["limits"] = {
                "daily_token_limit": config.daily_token_limit,
                "monthly_token_limit": config.monthly_token_limit,
                "conversations_per_day": config.conversations_per_day,
                "max_concurrent": config.max_concurrent,
            }

        return result


# ============================================
# Concurrency Limiter / 并发控制器
# ============================================

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
    LOCK_TTL = 300  # 5 分钟自动过期

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
            tenant_id: Tenant ID / 租户 ID
            agent_id: Agent ID / 智能体 ID
            max_concurrent: Per-agent max concurrency / 每智能体最大并发数
            tenant_max_concurrent: Tenant-wide max concurrency / 全租户最大并发数

        Returns:
            lock_token for release / lock_token 用于释放

        Raises:
            AgentConcurrencyExceeded: Concurrency exceeded / 并发超出
        """
        redis = await get_redis()
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
                    "Agent concurrency exceeded: tenant=%d agent=%d current=%d max=%d",
                    tenant_id, agent_id, int(result), max_concurrent,
                )
                raise AgentConcurrencyExceeded(
                    _("agent.error.concurrency_exceeded"), retry_after=5,
                )

        # Tenant-level concurrency check (atomic) / 租户级并发检查（原子操作）
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
                    _("agent.error.tenant_concurrency_exceeded"), retry_after=5,
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
            tenant_id: Tenant ID / 租户 ID
            agent_id: Agent ID / 智能体 ID
            lock_token: Token returned by acquire() / acquire() 返回的令牌
        """
        redis = await get_redis()
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
        redis = await get_redis()
        key = AgentConcurrencyLimiter._key(tenant_id, agent_id)
        now = time.time()
        await redis.zremrangebyscore(key, "-inf", now)
        return await redis.zcard(key)


__all__ = [
    "AgentQuotaConfig",
    "AgentQuotaManager",
    "AgentQuotaExceeded",
    "AgentConcurrencyLimiter",
    "AgentConcurrencyExceeded",
]
