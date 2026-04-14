"""Agent quota manager facade."""

from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any

from app.ai.agent_quota_config import AgentQuotaConfig
from app.ai.agent_quota_manager_support import (
    adjust_usage as _adjust_usage_support,
)
from app.ai.agent_quota_manager_support import (
    check_conversation_limits as _check_conversation_limits_support,
)
from app.ai.agent_quota_manager_support import (
    check_quota as _check_quota_support,
)
from app.ai.agent_quota_manager_support import (
    check_user_quota as _check_user_quota_support,
)
from app.ai.agent_quota_manager_support import (
    get_daily_conversations as _get_daily_conversations_support,
)
from app.ai.agent_quota_manager_support import (
    get_daily_usage as _get_daily_usage_support,
)
from app.ai.agent_quota_manager_support import (
    get_monthly_usage as _get_monthly_usage_support,
)
from app.ai.agent_quota_manager_support import (
    get_usage_summary as _get_usage_summary_support,
)
from app.ai.agent_quota_manager_support import (
    record_conversation as _record_conversation_support,
)
from app.ai.agent_quota_manager_support import (
    record_usage as _record_usage_support,
)
from app.ai.agent_quota_manager_support import (
    record_user_usage as _record_user_usage_support,
)


class AgentQuotaManager:
    """Compatibility facade for agent quota checks and usage accounting."""

    PREFIX_DAILY = "ai:agent_quota:daily:"
    PREFIX_MONTHLY = "ai:agent_quota:monthly:"
    PREFIX_DAILY_CONV = "ai:agent_quota:daily_conv:"
    PREFIX_USER = "ai:agent_quota:user:"

    _ADJUST_LUA = """
    local ttl = redis.call('TTL', KEYS[1])
    local new_val = redis.call('INCRBY', KEYS[1], ARGV[1])
    if ttl < 0 then
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
    end
    if new_val < 0 then
        if ttl >= 0 then
            redis.call('SET', KEYS[1], '0', 'KEEPTTL')
        else
            redis.call('SET', KEYS[1], '0', 'EX', tonumber(ARGV[2]))
        end
        return 0
    end
    return new_val
    """

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
    async def _get_redis():
        quota_module = import_module("app.ai.agent_quota")
        return await quota_module.get_redis()

    @staticmethod
    async def _atomic_check_and_record(
        key: str,
        estimated_tokens: int,
        limit: int,
        expire_seconds: int,
    ) -> int:
        redis = await AgentQuotaManager._get_redis()
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
        return (
            f"{AgentQuotaManager.PREFIX_DAILY}"
            f"{tenant_id}:{agent_id}:{stat_date.isoformat()}"
        )

    @staticmethod
    def _monthly_key(tenant_id: int, agent_id: int, year: int, month: int) -> str:
        return f"{AgentQuotaManager.PREFIX_MONTHLY}{tenant_id}:{agent_id}:{year}-{month:02d}"

    @staticmethod
    def _daily_conv_key(tenant_id: int, agent_id: int, stat_date: date) -> str:
        return (
            f"{AgentQuotaManager.PREFIX_DAILY_CONV}"
            f"{tenant_id}:{agent_id}:{stat_date.isoformat()}"
        )

    @staticmethod
    def _user_daily_key(
        tenant_id: int,
        agent_id: int,
        user_id: int,
        stat_date: date,
    ) -> str:
        return (
            f"{AgentQuotaManager.PREFIX_USER}{tenant_id}:{agent_id}:{user_id}:daily:"
            f"{stat_date.isoformat()}"
        )

    @classmethod
    async def check_quota(
        cls,
        tenant_id: int,
        agent_id: int,
        config: AgentQuotaConfig,
        estimated_tokens: int = 0,
    ) -> bool:
        return await _check_quota_support(
            cls,
            tenant_id,
            agent_id,
            config,
            estimated_tokens,
        )

    @staticmethod
    async def _atomic_adjust(
        key: str,
        diff: int,
        *,
        expire_seconds: int,
    ) -> int:
        redis = await AgentQuotaManager._get_redis()
        result = await redis.eval(
            AgentQuotaManager._ADJUST_LUA,
            1,
            key,
            str(diff),
            str(expire_seconds),
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
        await _adjust_usage_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            estimated_tokens,
            actual_tokens,
            config,
        )

    @staticmethod
    async def record_usage(
        tenant_id: int,
        agent_id: int,
        tokens: int,
        stat_date: date | None = None,
    ) -> None:
        await _record_usage_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            tokens,
            stat_date,
        )

    @staticmethod
    async def check_user_quota(
        tenant_id: int,
        agent_id: int,
        user_id: int,
        config: AgentQuotaConfig,
    ) -> bool:
        return await _check_user_quota_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            user_id,
            config,
        )

    @staticmethod
    async def check_conversation_limits(
        config: AgentQuotaConfig,
        current_turns: int = 0,
        current_tokens: int = 0,
    ) -> bool:
        return await _check_conversation_limits_support(
            config,
            current_turns,
            current_tokens,
        )

    @staticmethod
    async def record_conversation(
        tenant_id: int,
        agent_id: int,
        user_id: int | None = None,
    ) -> None:
        await _record_conversation_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            user_id,
        )

    @staticmethod
    async def record_user_usage(
        tenant_id: int,
        agent_id: int,
        user_id: int,
        tokens: int,
    ) -> None:
        await _record_user_usage_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            user_id,
            tokens,
        )

    @staticmethod
    async def get_daily_conversations(
        tenant_id: int,
        agent_id: int,
        stat_date: date | None = None,
    ) -> int:
        return await _get_daily_conversations_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            stat_date,
        )

    @staticmethod
    async def get_daily_usage(
        tenant_id: int,
        agent_id: int,
        stat_date: date | None = None,
    ) -> int:
        return await _get_daily_usage_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            stat_date,
        )

    @staticmethod
    async def get_monthly_usage(
        tenant_id: int,
        agent_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> int:
        return await _get_monthly_usage_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            year,
            month,
        )

    @staticmethod
    async def get_usage_summary(
        tenant_id: int,
        agent_id: int,
        config: AgentQuotaConfig | None = None,
    ) -> dict[str, Any]:
        return await _get_usage_summary_support(
            AgentQuotaManager,
            tenant_id,
            agent_id,
            config,
        )


__all__ = ["AgentQuotaManager"]
