"""
内置定时任务

系统内置的周期性维护任务
"""

from datetime import datetime, timedelta

from app.core.database import sync_session_factory
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
        logger.info(f"Cleaned {cleaned} expired captcha keys")
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning(f"Captcha cleanup skipped: {e}")
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
        session.execute("SELECT 1")
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

    logger.info(f"Health check: db={results['db']}, redis={results['redis']}")
    return results


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
        logger.info(f"Soft-deleted {result} expired task logs (>30 days)")
        return {"deleted": result}
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Task log cleanup failed: {e}")
        return {"deleted": 0, "error": str(e)}
    finally:
        if session:
            session.close()
