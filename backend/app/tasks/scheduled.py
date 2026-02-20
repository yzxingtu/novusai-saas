"""
内置定时任务

系统内置的周期性维护任务
注意：Celery Worker 是独立的同步进程，不经过 FastAPI lifespan，
因此 RedisManager 不会被初始化。所有 Redis 操作必须使用同步 redis 客户端。
"""

from datetime import timedelta

import redis

from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import register_task, BaseTask
from app.core.base_model import utc_now

logger = LogManager.get_logger("task")


def _get_sync_redis() -> redis.Redis:
    """获取同步 Redis 客户端（Celery Worker 专用）"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@register_task(
    queue="scheduled",
    description="清理过期验证码缓存",
    max_retries=1,
)
def clean_expired_captchas(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        cleaned = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor,
                match="captcha:*",
                count=100,
            )
            if keys:
                ttls = [client.ttl(key) for key in keys]
                expired_keys = [k for k, t in zip(keys, ttls) if t == -1]
                if expired_keys:
                    cleaned += client.delete(*expired_keys)
            if cursor == 0:
                break
        logger.info("%s count=%d", _("task.log.captcha_cleaned"), cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("%s error=%s", _("task.log.captcha_cleanup_skipped"), str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="系统健康检查（Redis/DB 连接状态）",
    max_retries=1,
)
def system_health_check(self: BaseTask) -> dict:
    results: dict = {
        "timestamp": utc_now().isoformat(),
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

    try:
        client = _get_sync_redis()
        results["redis"] = "connected" if client.ping() else "disconnected"
    except Exception as e:
        results["redis"] = f"error: {e}"

    logger.info(f"Health check: db={results['db']}, redis={results['redis']}")
    return results


@register_task(
    queue="scheduled",
    description="重置智能体每日配额（清理无 TTL 的 Redis key）",
    max_retries=1,
)
def reset_agent_daily_quotas(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cleaned = 0
        patterns = [
            "ai:agent_quota:daily:*",
            "ai:agent_quota:daily_conv:*",
            "ai:agent_quota:user:*",
        ]
        for pattern in patterns:
            cursor: int | str = 0
            while True:
                cursor, keys = client.scan(
                    cursor=cursor, match=pattern, count=200,
                )
                if keys:
                    ttls = [client.ttl(key) for key in keys]
                    no_ttl = [k for k, t in zip(keys, ttls) if t == -1]
                    if no_ttl:
                        cleaned += client.delete(*no_ttl)
                if cursor == 0:
                    break
        logger.info("%s count=%d", _("task.log.quota_reset"), cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("%s error=%s", _("task.log.quota_reset_skipped"), str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="重置智能体每日统计（Redis 当日计数归零）",
    max_retries=1,
)
def reset_agent_daily_stats(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        reset_count = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor, match="ai:agent_stats:daily:*", count=200,
            )
            if keys:
                reset_count += client.delete(*keys)
            if cursor == 0:
                break
        logger.info("%s count=%d", _("task.log.stats_reset"), reset_count)
        return {"reset_count": reset_count}
    except Exception as e:
        logger.warning("%s error=%s", _("task.log.stats_reset_skipped"), str(e))
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
        cutoff = utc_now() - timedelta(days=30)
        result = (
            session.query(TaskLog)
            .filter(TaskLog.created_at < cutoff)
            .update({"is_deleted": True})
        )
        session.commit()
        logger.info("%s count=%d", _("task.log.task_log_cleaned"), result)
        return {"deleted": result}
    except Exception as e:
        if session:
            session.rollback()
        logger.error("%s error=%s", _("task.log.task_log_cleanup_failed"), str(e))
        return {"deleted": 0, "error": str(e)}
    finally:
        if session:
            session.close()
