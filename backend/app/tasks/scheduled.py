"""
内置定时任务

系统内置的周期性维护任务
"""

from datetime import datetime, timedelta

from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import RedisManager
from app.tasks.base import register_task, BaseTask

logger = LogManager.get_logger("task")


@register_task(
    queue="scheduled",
    description="清理过期验证码缓存",
    max_retries=1,
)
def clean_expired_captchas(self: BaseTask) -> dict:
    from app.core.redis import get_redis_client
    import asyncio

    async def _clean() -> int:
        client = get_redis_client()
        cursor = 0
        cleaned = 0
        while True:
            cursor, keys = await client.scan(
                cursor=cursor,
                match="captcha:*",
                count=100,
            )
            if keys:
                ttls = [await client.ttl(key) for key in keys]
                expired_keys = [k for k, t in zip(keys, ttls) if t == -1]
                if expired_keys:
                    cleaned += await client.delete(*expired_keys)
            if cursor == 0:
                break
        return cleaned

    try:
        loop = asyncio.new_event_loop()
        cleaned = loop.run_until_complete(_clean())
        loop.close()
        logger.info(_("task.log.captcha_cleaned"), count=cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning(_("task.log.captcha_cleanup_skipped"), error=str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="系统健康检查（Redis/DB 连接状态）",
    max_retries=1,
)
def system_health_check(self: BaseTask) -> dict:
    import asyncio

    results: dict = {
        "timestamp": datetime.utcnow().isoformat(),
        "db": "unknown",
        "redis": "unknown",
    }

    session = None
    try:
        session = sync_session_factory()
        from sqlalchemy import text
        session.execute(text("SELECT 1"))
        results["db"] = "connected"
    except Exception as e:
        results["db"] = f"error: {e}"
    finally:
        if session:
            session.close()

    async def _check_redis() -> bool:
        return await RedisManager.health_check()

    try:
        loop = asyncio.new_event_loop()
        redis_ok = loop.run_until_complete(_check_redis())
        loop.close()
        results["redis"] = "connected" if redis_ok else "disconnected"
    except Exception as e:
        results["redis"] = f"error: {e}"

    logger.info(_("task.log.health_check_result"), db=results["db"], redis=results["redis"])
    return results


@register_task(
    queue="scheduled",
    description="重置智能体每日配额（清理无 TTL 的 Redis key）",
    max_retries=1,
)
def reset_agent_daily_quotas(self: BaseTask) -> dict:
    import asyncio

    async def _reset() -> int:
        from app.core.redis import get_redis_client
        client = get_redis_client()
        cleaned = 0
        patterns = [
            "ai:agent_quota:daily:*",
            "ai:agent_quota:daily_conv:*",
            "ai:agent_quota:user:*",
        ]
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = await client.scan(
                    cursor=cursor, match=pattern, count=200,
                )
                if keys:
                    ttls = [await client.ttl(key) for key in keys]
                    no_ttl = [k for k, t in zip(keys, ttls) if t == -1]
                    if no_ttl:
                        cleaned += await client.delete(*no_ttl)
                if cursor == 0:
                    break
        return cleaned

    try:
        loop = asyncio.new_event_loop()
        cleaned = loop.run_until_complete(_reset())
        loop.close()
        logger.info(_("task.log.quota_reset"), count=cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning(_("task.log.quota_reset_skipped"), error=str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="重置智能体每日统计（Redis 当日计数归零）",
    max_retries=1,
)
def reset_agent_daily_stats(self: BaseTask) -> dict:
    import asyncio

    async def _reset() -> int:
        from app.ai.agent_stats import AgentStatsManager
        return await AgentStatsManager.reset_daily_stats()

    try:
        loop = asyncio.new_event_loop()
        count = loop.run_until_complete(_reset())
        loop.close()
        logger.info(_("task.log.stats_reset"), count=count)
        return {"reset_count": count}
    except Exception as e:
        logger.warning(_("task.log.stats_reset_skipped"), error=str(e))
        return {"reset_count": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="清理过期任务日志（保留30天）",
    max_retries=1,
)
def clean_expired_task_logs(self: BaseTask) -> dict:
    session = None
    try:
        from app.models.system.task_log import TaskLog

        session = sync_session_factory()
        cutoff = datetime.utcnow() - timedelta(days=30)
        result = (
            session.query(TaskLog)
            .filter(TaskLog.created_at < cutoff)
            .update({"is_deleted": True})
        )
        session.commit()
        logger.info(_("task.log.task_log_cleaned"), count=result)
        return {"deleted": result}
    except Exception as e:
        if session:
            session.rollback()
        logger.error(_("task.log.task_log_cleanup_failed"), error=str(e))
        return {"deleted": 0, "error": str(e)}
    finally:
        if session:
            session.close()
