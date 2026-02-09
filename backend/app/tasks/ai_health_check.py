"""
AI 供应商健康检查定时任务

每 5 分钟对所有启用的供应商执行轻量级健康探测，
将状态写入 Redis，供故障转移服务读取。
"""

import json
import time
from datetime import datetime

from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("tasks.ai")

# Redis 键前缀
HEALTH_KEY_PREFIX = "ai:provider:{provider_id}:health"
HEALTH_HISTORY_PREFIX = "ai:provider:{provider_id}:health_history"
HEALTH_TTL = 600  # 10 分钟
HEALTH_HISTORY_TTL = 86400  # 24 小时
CONSECUTIVE_FAILURES_THRESHOLD = 3

# 数据库连接
_engine = None
_SessionLocal = None


def _get_db_session() -> Session:
    """获取同步数据库会话"""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL_SYNC,
            pool_pre_ping=True,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionLocal()


def _get_redis():
    """获取同步 Redis 连接"""
    import redis
    return redis.from_url(settings.redis_url, decode_responses=True)


@shared_task(
    bind=True,
    name="tasks.ai.health_check",
    queue="scheduled",
    ignore_result=True,
)
def ai_provider_health_check(self):
    """
    AI 供应商健康检查

    对每个启用的供应商发送轻量测试请求，
    记录响应时间和可用状态到 Redis。
    连续 3 次失败标记为不可用。
    """
    from app.models.ai import AIProvider

    db = _get_db_session()
    redis_client = _get_redis()

    try:
        # 获取所有启用的供应商
        stmt = select(AIProvider).where(
            AIProvider.is_active == True,
            AIProvider.is_deleted == False,
        )
        result = db.execute(stmt)
        providers = result.scalars().all()

        logger.info("Starting health check for %d providers", len(providers))

        for provider in providers:
            _check_provider_health(provider, db, redis_client)

        logger.info("Health check completed for %d providers", len(providers))

    except Exception as e:
        logger.error("Health check task failed: %s", str(e))
        raise
    finally:
        db.close()


def _check_provider_health(provider, db: Session, redis_client):
    """
    检查单个供应商的健康状态

    Args:
        provider: AIProvider 实例
        db: 数据库会话
        redis_client: Redis 客户端
    """
    from app.models.ai import ProviderApiKey

    provider_id = provider.id
    health_key = HEALTH_KEY_PREFIX.format(provider_id=provider_id)
    history_key = HEALTH_HISTORY_PREFIX.format(provider_id=provider_id)

    start_time = time.time()
    is_healthy = False
    error_message = None
    response_time_ms = 0

    try:
        # 获取供应商的 API Key
        stmt = select(ProviderApiKey).where(
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.tenant_id == None,
            ProviderApiKey.is_active == True,
            ProviderApiKey.is_deleted == False,
        ).limit(1)
        result = db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            error_message = "No active platform API key"
            logger.warning(
                "No API key for provider %s, skip health check",
                provider.code,
            )
        else:
            # 发送轻量级测试请求
            is_healthy = _send_health_probe(
                provider_type=provider.type,
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
            )
            response_time_ms = int((time.time() - start_time) * 1000)

    except Exception as e:
        error_message = str(e)
        response_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Health check failed for provider %s: %s",
            provider.code,
            str(e),
        )

    # 读取当前状态获取连续失败次数
    current_data = redis_client.get(health_key)
    consecutive_failures = 0
    if current_data:
        try:
            current = json.loads(current_data)
            consecutive_failures = current.get("consecutive_failures", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    if is_healthy:
        consecutive_failures = 0
    else:
        consecutive_failures += 1

    # 写入当前健康状态
    health_data = {
        "provider_id": provider_id,
        "provider_code": provider.code,
        "provider_name": provider.name,
        "is_healthy": is_healthy,
        "response_time_ms": response_time_ms,
        "error_message": error_message,
        "consecutive_failures": consecutive_failures,
        "is_available": consecutive_failures < CONSECUTIVE_FAILURES_THRESHOLD,
        "checked_at": datetime.utcnow().isoformat(),
    }

    redis_client.setex(
        health_key,
        HEALTH_TTL,
        json.dumps(health_data, ensure_ascii=False),
    )

    # 追加到历史记录（使用 sorted set，score 为时间戳）
    history_entry = json.dumps({
        "is_healthy": is_healthy,
        "response_time_ms": response_time_ms,
        "error_message": error_message,
        "checked_at": datetime.utcnow().isoformat(),
    }, ensure_ascii=False)

    redis_client.zadd(history_key, {history_entry: time.time()})
    # 只保留 24h 内的记录
    cutoff = time.time() - HEALTH_HISTORY_TTL
    redis_client.zremrangebyscore(history_key, 0, cutoff)
    redis_client.expire(history_key, HEALTH_HISTORY_TTL)

    status_text = "healthy" if is_healthy else f"unhealthy (failures: {consecutive_failures})"
    logger.info(
        "Health check: provider=%s status=%s response_time=%dms",
        provider.code,
        status_text,
        response_time_ms,
    )


def _send_health_probe(
    provider_type: str,
    api_key: str,
    base_url: str | None = None,
) -> bool:
    """
    发送轻量级健康探测请求

    使用同步 HTTP 请求（Celery Worker 是同步环境）

    Args:
        provider_type: 供应商类型
        api_key: API 密钥
        base_url: 基础 URL

    Returns:
        是否健康
    """
    import httpx

    try:
        # OpenAI 兼容: 使用 models list 接口（最轻量）
        # base_url 应已包含完整路径（如 https://api.openai.com/v1）
        # 与 OpenAI SDK 保持一致，直接在 base_url 后追加 /models
        url = (base_url or "https://api.openai.com/v1").rstrip("/")

        response = httpx.get(
            f"{url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        return response.status_code < 500

    except httpx.TimeoutException:
        return False
    except httpx.ConnectError:
        return False
    except Exception:
        return False


__all__ = ["ai_provider_health_check"]
