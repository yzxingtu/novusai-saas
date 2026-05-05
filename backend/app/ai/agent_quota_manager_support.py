"""Support helpers for the agent quota manager facade."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ai.agent_quota_concurrency import AgentConcurrencyLimiter
from app.ai.agent_quota_config import AgentQuotaConfig
from app.ai.agent_quota_exceptions import AgentQuotaExceeded
from app.ai.events.bus import get_event_bus
from app.ai.events.types import QuotaExceeded as QuotaExceededEvent
from app.ai.events.types import QuotaWarning
from app.core.i18n import _
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.agent_quota")


async def check_quota(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    config: AgentQuotaConfig,
    estimated_tokens: int = 0,
) -> bool:
    today = date.today()
    event_bus = get_event_bus()

    if config.daily_token_limit > 0 and estimated_tokens > 0:
        result = await manager_cls._atomic_check_and_record(
            key=manager_cls._daily_key(tenant_id, agent_id, today),
            estimated_tokens=estimated_tokens,
            limit=config.daily_token_limit,
            expire_seconds=86400 * 2,
        )
        if result >= 0:
            logger.warning(
                "Agent daily quota exceeded: tenant={} agent={} usage={} limit={}",
                tenant_id,
                agent_id,
                result + estimated_tokens,
                config.daily_token_limit,
            )
            await event_bus.publish(
                QuotaExceededEvent(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    quota_type="daily",
                )
            )
            raise AgentQuotaExceeded(
                _("agent.error.daily_quota_exceeded"),
                quota_type="daily_tokens",
                current=result + estimated_tokens,
                limit=config.daily_token_limit,
            )

        await _publish_warning_if_needed(
            manager_cls=manager_cls,
            event_bus=event_bus,
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=config.daily_token_limit,
            threshold=config.warning_threshold,
            usage_getter=get_daily_usage,
            usage_args=(today,),
        )

    if config.conversations_per_day > 0:
        conv_count = await get_daily_conversations(
            manager_cls, tenant_id, agent_id, today
        )
        if conv_count >= config.conversations_per_day:
            raise AgentQuotaExceeded(
                _("agent.error.daily_conversation_quota_exceeded"),
                quota_type="daily_conversations",
                current=conv_count,
                limit=config.conversations_per_day,
            )

    if config.monthly_token_limit > 0 and estimated_tokens > 0:
        result = await manager_cls._atomic_check_and_record(
            key=manager_cls._monthly_key(tenant_id, agent_id, today.year, today.month),
            estimated_tokens=estimated_tokens,
            limit=config.monthly_token_limit,
            expire_seconds=86400 * 35,
        )
        if result >= 0:
            logger.warning(
                "Agent monthly quota exceeded: tenant={} agent={} usage={} limit={}",
                tenant_id,
                agent_id,
                result + estimated_tokens,
                config.monthly_token_limit,
            )
            await event_bus.publish(
                QuotaExceededEvent(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    quota_type="monthly",
                )
            )
            if config.daily_token_limit > 0:
                await manager_cls._atomic_adjust(
                    manager_cls._daily_key(tenant_id, agent_id, today),
                    -estimated_tokens,
                    expire_seconds=86400 * 2,
                )
            raise AgentQuotaExceeded(
                _("agent.error.monthly_quota_exceeded"),
                quota_type="monthly_tokens",
                current=result + estimated_tokens,
                limit=config.monthly_token_limit,
            )

        await _publish_warning_if_needed(
            manager_cls=manager_cls,
            event_bus=event_bus,
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=config.monthly_token_limit,
            threshold=config.warning_threshold,
            usage_getter=get_monthly_usage,
            usage_args=(today.year, today.month),
        )

    return True


async def _publish_warning_if_needed(
    *,
    manager_cls,
    event_bus,
    tenant_id: int,
    agent_id: int,
    limit: int,
    threshold: int | float,
    usage_getter,
    usage_args: tuple[Any, ...],
) -> None:
    if limit <= 0 or threshold <= 0:
        return
    usage = await usage_getter(manager_cls, tenant_id, agent_id, *usage_args)
    usage_pct = (usage / limit) * 100
    if usage_pct < threshold:
        return
    await event_bus.publish(
        QuotaWarning(
            tenant_id=tenant_id,
            agent_id=agent_id,
            usage_percent=usage_pct,
            threshold=threshold,
        )
    )


async def adjust_usage(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    estimated_tokens: int,
    actual_tokens: int,
    config: AgentQuotaConfig | None = None,
) -> None:
    diff = actual_tokens - estimated_tokens
    if diff == 0:
        return

    today = date.today()
    if not config or config.daily_token_limit > 0:
        await manager_cls._atomic_adjust(
            manager_cls._daily_key(tenant_id, agent_id, today),
            diff,
            expire_seconds=86400 * 2,
        )
    if not config or config.monthly_token_limit > 0:
        await manager_cls._atomic_adjust(
            manager_cls._monthly_key(tenant_id, agent_id, today.year, today.month),
            diff,
            expire_seconds=86400 * 35,
        )


async def record_usage(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    tokens: int,
    stat_date: date | None = None,
) -> None:
    redis = await manager_cls._get_redis()
    stat_date = stat_date or date.today()

    daily_key = manager_cls._daily_key(tenant_id, agent_id, stat_date)
    await redis.incrby(daily_key, tokens)
    await redis.expire(daily_key, 86400 * 2)

    monthly_key = manager_cls._monthly_key(
        tenant_id,
        agent_id,
        stat_date.year,
        stat_date.month,
    )
    await redis.incrby(monthly_key, tokens)
    await redis.expire(monthly_key, 86400 * 35)


async def check_user_quota(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    user_id: int,
    config: AgentQuotaConfig,
) -> bool:
    if not user_id:
        return True

    today = date.today()
    redis = await manager_cls._get_redis()
    key = manager_cls._user_daily_key(tenant_id, agent_id, user_id, today)

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


async def check_conversation_limits(
    config: AgentQuotaConfig,
    current_turns: int = 0,
    current_tokens: int = 0,
) -> bool:
    if (
        config.max_turns_per_conversation > 0
        and current_turns >= config.max_turns_per_conversation
    ):
        raise AgentQuotaExceeded(
            _("agent.error.conversation_turns_exceeded"),
            quota_type="conversation_turns",
            current=current_turns,
            limit=config.max_turns_per_conversation,
        )
    if (
        config.max_tokens_per_conversation > 0
        and current_tokens >= config.max_tokens_per_conversation
    ):
        raise AgentQuotaExceeded(
            _("agent.error.conversation_tokens_exceeded"),
            quota_type="conversation_tokens",
            current=current_tokens,
            limit=config.max_tokens_per_conversation,
        )
    return True


async def record_conversation(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    user_id: int | None = None,
) -> None:
    redis = await manager_cls._get_redis()
    today = date.today()

    conv_key = manager_cls._daily_conv_key(tenant_id, agent_id, today)
    await redis.incr(conv_key)
    await redis.expire(conv_key, 86400 * 2)

    if not user_id:
        return
    user_key = manager_cls._user_daily_key(tenant_id, agent_id, user_id, today)
    await redis.hincrby(user_key, "conversations", 1)
    await redis.expire(user_key, 86400 * 2)


async def record_user_usage(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    user_id: int,
    tokens: int,
) -> None:
    if not user_id or tokens <= 0:
        return
    redis = await manager_cls._get_redis()
    today = date.today()
    key = manager_cls._user_daily_key(tenant_id, agent_id, user_id, today)
    await redis.hincrby(key, "tokens", tokens)
    await redis.expire(key, 86400 * 2)


async def get_daily_conversations(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    stat_date: date | None = None,
) -> int:
    redis = await manager_cls._get_redis()
    stat_date = stat_date or date.today()
    value = await redis.get(manager_cls._daily_conv_key(tenant_id, agent_id, stat_date))
    return int(value) if value else 0


async def get_daily_usage(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    stat_date: date | None = None,
) -> int:
    redis = await manager_cls._get_redis()
    stat_date = stat_date or date.today()
    value = await redis.get(manager_cls._daily_key(tenant_id, agent_id, stat_date))
    return int(value) if value else 0


async def get_monthly_usage(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    year: int | None = None,
    month: int | None = None,
) -> int:
    redis = await manager_cls._get_redis()
    today = date.today()
    year = year or today.year
    month = month or today.month
    value = await redis.get(manager_cls._monthly_key(tenant_id, agent_id, year, month))
    return int(value) if value else 0


async def get_usage_summary(
    manager_cls,
    tenant_id: int,
    agent_id: int,
    config: AgentQuotaConfig | None = None,
) -> dict[str, Any]:
    today = date.today()
    result: dict[str, Any] = {
        "daily_tokens": await get_daily_usage(manager_cls, tenant_id, agent_id, today),
        "monthly_tokens": await get_monthly_usage(
            manager_cls,
            tenant_id,
            agent_id,
            today.year,
            today.month,
        ),
        "daily_conversations": await get_daily_conversations(
            manager_cls,
            tenant_id,
            agent_id,
            today,
        ),
        "current_concurrent": await AgentConcurrencyLimiter.get_current(
            tenant_id,
            agent_id,
        ),
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
