"""
Built-in scheduled tasks / 内置定时任务

System built-in periodic maintenance tasks.
系统内置的周期性维护任务
Note: Celery Worker is an independent synchronous process that does not go through FastAPI lifespan,
so RedisManager will not be initialized. All Redis operations must use a sync redis client.
注意：Celery Worker 是独立的同步进程，不经过 FastAPI lifespan，
因此 RedisManager 不会被初始化。所有 Redis 操作必须使用同步 redis 客户端。
"""

import contextlib
from datetime import timedelta

import redis

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


def _get_sync_redis() -> redis.Redis:
    """Get sync Redis client (Celery Worker only) / 获取同步 Redis 客户端（Celery Worker 专用）"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@register_task(
    queue="scheduled",
    description="Clean up expired captcha cache / 清理过期验证码缓存",
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
                expired_keys = [
                    k for k, t in zip(keys, ttls, strict=False) if t == -1
                ]
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
    description="System health check (Redis/DB connection status) / 系统健康检查（Redis/DB 连接状态）",
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
    description="Reset agent daily quotas (clean up Redis keys without TTL) / 重置智能体每日配额（清理无 TTL 的 Redis key）",
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
                    no_ttl = [
                        k for k, t in zip(keys, ttls, strict=False) if t == -1
                    ]
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
    description="Reset agent daily stats (Redis daily count reset) / 重置智能体每日统计（Redis 当日计数归零）",
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
    description="Check plugin trial expirations, auto-disable expired plugins and send warnings / 检查插件试用期到期，自动禁用到期插件并发出预警提醒",
    max_retries=1,
)
def check_plugin_trial_expirations(self: BaseTask) -> dict:
    """Check plugin license trial period; auto-disable on expiry, send reminders for upcoming expiry. / 检查插件 License 试用期，到期自动禁用，即将到期发提醒。"""
    import asyncio

    from app.tasks.async_db import task_async_session

    async def _run():
        from app.core.redis import RedisManager
        from app.plugins.license import check_trial_expirations

        # Celery worker doesn't go through FastAPI lifespan, RedisManager is not initialized.
        # Celery worker 不走 FastAPI lifespan，RedisManager 未初始化。
        # lifecycle.disable() → _plugin_lock() → get_redis_client() needs Redis.
        # lifecycle.disable() → _plugin_lock() → get_redis_client() 需要 Redis。
        # Without initialization, disable() will silently fail (RuntimeError caught by license.py),
        # and plugins will never be disabled even if trial period has expired.
        # 若不初始化，disable() 会 silently fail (RuntimeError 被 license.py 捕获)，
        # 插件将永远不会被禁用，即使试用期已到期。
        redis_was_initialized = RedisManager._pool is not None
        if not redis_was_initialized:
            try:
                await RedisManager.init()
            except Exception as redis_err:
                # Redis unavailable: downgrade — license will still be marked invalid, but disable() may fail
                # Redis 不可用时降级：license 仍会标记为 invalid，但 disable() 可能失败
                logger.warning(
                    "Plugin trial check: Redis unavailable (%s), "
                    "plugin disable may fail (license will still be invalidated)",
                    redis_err,
                )

        try:
            async with task_async_session() as db:
                actions = await check_trial_expirations(db)
                await db.commit()
                return actions
        finally:
            # If this call initialized Redis, close connection pool to avoid reusing old pool across event-loop
            # 若本次调用初始化了 Redis，关闭连接池避免跨 event-loop 复用旧 pool
            if not redis_was_initialized:
                with contextlib.suppress(Exception):
                    await RedisManager.close()

    try:
        loop = asyncio.new_event_loop()
        try:
            actions = loop.run_until_complete(_run())
        finally:
            loop.close()

        disabled = [a for a in actions if a.get("action") == "disabled"]
        warnings = [a for a in actions if a.get("action") == "warning"]
        if disabled or warnings:
            logger.info(
                "Plugin trial check: disabled=%d, warnings=%d",
                len(disabled), len(warnings),
            )
        return {"disabled": len(disabled), "warnings": len(warnings), "total": len(actions)}
    except Exception as exc:
        logger.warning("Plugin trial check failed: %s", exc)
        return {"disabled": 0, "warnings": 0, "error": str(exc)}


@register_task(
    queue="scheduled",
    description="Clean up expired task logs (retain 30 days) / 清理过期任务日志（保留 30 天）",
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


@register_task(
    queue="scheduled",
    description="Clean up expired session memories (24h fallback) / 清理过期会话记忆（24h 兜底）",
    max_retries=1,
)
def clean_expired_session_memories(self: BaseTask) -> dict:
    """
    Clean up expired session memory keys (fallback) / 清理过期会话记忆 key（兜底）

    Note:
    - Normally session memory keys auto-expire via TTL;
    - 正常情况下会话记忆 key 使用 TTL 自动过期；
    - This task provides fallback cleanup for keys without TTL or abnormal residual keys.
    - 本任务用于兜底清理无 TTL 或异常残留 key。
    """
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        cleaned = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor,
                match="mem:sess:*",
                count=200,
            )
            if keys:
                ttls = [client.ttl(key) for key in keys]
                # ttl == -1 means no expiration, needs cleanup / ttl == -1 表示无过期时间，需要清理
                no_ttl = [
                    k for k, t in zip(keys, ttls, strict=False) if t == -1
                ]
                if no_ttl:
                    cleaned += client.delete(*no_ttl)
            if cursor == 0:
                break
        logger.info("Session memory cleanup finished, cleaned=%d", cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("Session memory cleanup skipped: %s", str(e))
        return {"cleaned": 0, "error": str(e)}


# ── LiteLLM Model Capability Registry Sync ───────────────────────────────────

LITELLM_REGISTRY_URLS = [
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
]
LITELLM_REDIS_KEY = "ai:litellm:registry"
LITELLM_REDIS_TTL = 86400 * 3


@register_task(
    queue="scheduled",
    description="Sync LiteLLM model capability registry to Redis / 同步 LiteLLM 模型能力注册表到 Redis",
    max_retries=2,
)
def sync_litellm_registry(self: BaseTask) -> dict:
    """
    Download LiteLLM model_prices_and_context_window.json and cache in Redis.
    从 LiteLLM GitHub 仓库下载模型能力注册表并缓存到 Redis。

    Tries jsdelivr CDN first, falls back to GitHub raw.
    优先使用 jsdelivr CDN，失败后回退到 GitHub raw。
    """
    import json

    import requests

    last_error: Exception | None = None
    for url in LITELLM_REGISTRY_URLS:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            registry = resp.json()
            if not isinstance(registry, dict) or len(registry) < 10:
                logger.warning("LiteLLM registry looks invalid, entries=%s", len(registry) if isinstance(registry, dict) else "N/A")
                continue

            client = _get_sync_redis()
            client.setex(
                LITELLM_REDIS_KEY,
                LITELLM_REDIS_TTL,
                json.dumps(registry, ensure_ascii=False),
            )
            model_count = len(registry)
            logger.info("LiteLLM registry synced: source=%s models=%d", url, model_count)
            return {"source": url, "model_count": model_count}
        except Exception as e:
            last_error = e
            logger.warning("LiteLLM registry fetch failed: url=%s error=%s", url, str(e))

    raise RuntimeError(f"All LiteLLM registry URLs failed: {last_error}")
