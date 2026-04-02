"""
AI provider health check scheduled task / AI 供应商健康检查定时任务

Performs lightweight health probes on all enabled providers every 5 minutes,
writing status to Redis for failover service consumption.
每 5 分钟对所有启用的供应商执行轻量级健康探测，
将状态写入 Redis，供故障转移服务读取。
"""

import json
import time

import redis
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("tasks.ai")

HEALTH_KEY_PREFIX = "ai:provider:{provider_id}:health"
HEALTH_HISTORY_PREFIX = "ai:provider:{provider_id}:health_history"
HEALTH_TTL = 600
HEALTH_HISTORY_TTL = 86400
CONSECUTIVE_FAILURES_THRESHOLD = 3
_FALSE_VALUES = {"0", "false", "no", "off"}


def _get_sync_redis() -> redis.Redis:
    """Get sync Redis client (Celery Worker only) / 获取同步 Redis 客户端（Celery Worker 专用）"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@register_task(
    queue="scheduled",
    description="AI provider health check / AI 供应商健康检查",
    max_retries=1,
)
def ai_provider_health_check(self: BaseTask) -> dict:
    """
    AI provider health check / AI 供应商健康检查

    Sends lightweight test requests to each enabled provider,
    recording response time and availability to Redis.
    对每个启用的供应商发送轻量测试请求，
    记录响应时间和可用状态到 Redis。
    Marks as unavailable after 3 consecutive failures.
    连续 3 次失败标记为不可用。
    """
    from app.models.ai import AIProvider

    db = sync_session_factory()
    redis_client = _get_sync_redis()

    try:
        # Get all enabled providers / 获取所有启用的供应商
        stmt = select(AIProvider).where(
            AIProvider.is_active.is_(True),
            AIProvider.is_deleted.is_(False),
        )
        result = db.execute(stmt)
        providers = result.scalars().all()

        logger.info("{} provider_count={}", _("ai.log.health_check_start"), len(providers))

        for provider in providers:
            _check_provider_health(provider, db, redis_client)

        logger.info("{} provider_count={}", _("ai.log.health_check_completed"), len(providers))
        return {"provider_count": len(providers), "status": "completed"}

    except Exception as e:
        logger.error("{} error={}", _("ai.log.health_check_task_failed"), str(e))
        raise
    finally:
        db.close()

    return {"provider_count": 0, "status": "no_providers"}


def _check_provider_health(provider: object, db: Session, redis_client: redis.Redis) -> None:
    """
    Check health status of a single provider / 检查单个供应商的健康状态

    Args:
        provider: AIProvider instance / AIProvider 实例
        db: Database session / 数据库会话
        redis_client: Redis client / Redis 客户端
    """
    from app.models.ai import ProviderApiKey

    provider_id = provider.id
    health_key = HEALTH_KEY_PREFIX.format(provider_id=provider_id)
    history_key = HEALTH_HISTORY_PREFIX.format(provider_id=provider_id)

    start_time = time.time()
    is_healthy = False
    error_message = None
    response_time_ms = 0
    base_connectivity_healthy = False
    tool_calling_healthy: bool | None = None
    tool_probe_model: str | None = None
    tool_probe_error_message: str | None = None
    wire_api = _normalize_wire_api(
        (provider.config or {}).get("wire_api")
        if isinstance(getattr(provider, "config", None), dict)
        else None
    )

    try:
        # Get provider's API Key / 获取供应商的 API Key
        stmt = select(ProviderApiKey).where(
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.tenant_id.is_(None),
            ProviderApiKey.is_active.is_(True),
            ProviderApiKey.is_deleted.is_(False),
        ).limit(1)
        result = db.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            error_message = _("ai.log.health_no_api_key")
            logger.warning(
                "{} provider={}",
                _("ai.log.health_skip_no_key"),
                provider.code,
            )
        else:
            base_connectivity_healthy, base_error = _send_base_health_probe(
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
            )
            if base_error:
                error_message = base_error

            tool_model = _resolve_tool_probe_model(provider, db)
            if base_connectivity_healthy and tool_model is not None:
                tool_probe_model = tool_model.code
                tool_calling_healthy, tool_probe_error_message = (
                    _send_responses_tool_probe(
                        api_key=api_key.decrypt_key(),
                        base_url=provider.base_url,
                        model_code=tool_model.code,
                    )
                    if _provider_needs_responses_tool_probe(provider, tool_model)
                    else (None, None)
                )
                if tool_calling_healthy is False:
                    error_message = tool_probe_error_message or error_message

            is_healthy = base_connectivity_healthy and (
                tool_calling_healthy is not False
            )
            response_time_ms = int((time.time() - start_time) * 1000)

    except Exception as e:
        error_message = str(e)
        response_time_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "{} provider={} error={}",
            _("ai.log.health_check_provider_failed"),
            provider.code,
            str(e),
        )

    # Read current state to get consecutive failure count / 读取当前状态获取连续失败次数
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

    # Write current health status / 写入当前健康状态
    health_data = {
        "provider_id": provider_id,
        "provider_code": provider.code,
        "provider_name": provider.name,
        "wire_api": wire_api,
        "is_healthy": is_healthy,
        "base_connectivity_healthy": base_connectivity_healthy,
        "tool_calling_healthy": tool_calling_healthy,
        "tool_probe_model": tool_probe_model,
        "tool_probe_error_message": tool_probe_error_message,
        "response_time_ms": response_time_ms,
        "error_message": error_message,
        "consecutive_failures": consecutive_failures,
        "is_available": consecutive_failures < CONSECUTIVE_FAILURES_THRESHOLD,
        "checked_at": utc_now().isoformat(),
    }

    redis_client.setex(
        health_key,
        HEALTH_TTL,
        json.dumps(health_data, ensure_ascii=False),
    )

    # Append to history (sorted set, score = timestamp) / 追加到历史记录（使用 sorted set，score 为时间戳）
    history_entry = json.dumps({
        "is_healthy": is_healthy,
        "base_connectivity_healthy": base_connectivity_healthy,
        "tool_calling_healthy": tool_calling_healthy,
        "response_time_ms": response_time_ms,
        "error_message": error_message,
        "checked_at": utc_now().isoformat(),
    }, ensure_ascii=False)

    redis_client.zadd(history_key, {history_entry: time.time()})
    # Keep only records within 24h / 只保留 24h 内的记录
    cutoff = time.time() - HEALTH_HISTORY_TTL
    redis_client.zremrangebyscore(history_key, 0, cutoff)
    redis_client.expire(history_key, HEALTH_HISTORY_TTL)

    logger.info(
        "{} provider={} is_healthy={} base_connectivity_healthy={} tool_calling_healthy={} tool_probe_model={} consecutive_failures={} response_time_ms={}",
        _("ai.log.health_check_result"),
        provider.code,
        is_healthy,
        base_connectivity_healthy,
        tool_calling_healthy,
        tool_probe_model or "",
        consecutive_failures,
        response_time_ms,
    )


def _normalize_wire_api(wire_api: str | None) -> str:
    value = str(wire_api or "").strip().lower().replace("-", "_")
    if value in {"responses", "response", "responses_api"}:
        return "responses"
    return "chat_completions"


def _config_enabled(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in _FALSE_VALUES


def _resolve_tool_probe_model(provider: object, db: Session):
    from app.models.ai import AIModel

    stmt = (
        select(AIModel)
        .where(
            AIModel.provider_id == provider.id,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
            AIModel.type == "chat",
            AIModel.supports_function_calling.is_(True),
        )
        .order_by(AIModel.id.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _provider_needs_responses_tool_probe(provider: object, tool_model: object | None) -> bool:
    if tool_model is None:
        return False
    wire_api = _normalize_wire_api(
        (provider.config or {}).get("wire_api")
        if isinstance(getattr(provider, "config", None), dict)
        else None
    )
    if wire_api != "responses":
        return False
    if not bool(getattr(tool_model, "supports_function_calling", False)):
        return False
    config = provider.config if isinstance(getattr(provider, "config", None), dict) else {}
    return _config_enabled(
        config.get("responses_tool_probe_enabled"),
        default=True,
    )


def _send_base_health_probe(
    api_key: str,
    base_url: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send lightweight health probe request / 发送轻量级健康探测请求

    Uses synchronous HTTP request (Celery Worker is a sync environment).
    使用同步 HTTP 请求（Celery Worker 是同步环境）

    Args:
        api_key: API key / API 密钥
        base_url: Base URL / 基础 URL

    Returns:
        Probe result / 探测结果
    """
    try:
        # OpenAI compatible: use models list interface (lightest)
        # base_url should already contain the full path (e.g. https://api.openai.com/v1)
        # Consistent with OpenAI SDK, directly append /models to base_url
        # 与 OpenAI SDK 保持一致，直接在 base_url 后追加 /models
        url = (base_url or "https://api.openai.com/v1").rstrip("/")

        response = httpx.get(
            f"{url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        if response.status_code < 500:
            return True, None
        return False, f"GET /models -> HTTP {response.status_code}"

    except httpx.TimeoutException:
        return False, "GET /models timed out"
    except httpx.ConnectError:
        return False, "GET /models connect error"
    except Exception as exc:
        return False, str(exc)


def _send_responses_tool_probe(
    *,
    api_key: str,
    base_url: str | None,
    model_code: str,
) -> tuple[bool, str | None]:
    url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/responses"
    payload = {
        "model": model_code,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "health check"}],
            }
        ],
        "tools": [
            {
                "type": "function",
                "name": "health_check_tool",
                "description": "Provider health probe tool",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            }
        ],
        "tool_choice": "required",
        "max_output_tokens": 1,
    }

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10.0,
        )
        if 200 <= response.status_code < 400:
            return True, None
        preview = (response.text or "").strip()
        if len(preview) > 200:
            preview = f"{preview[:197]}..."
        detail = f"POST /responses tool probe -> HTTP {response.status_code}"
        if preview:
            detail = f"{detail}: {preview}"
        return False, detail
    except httpx.TimeoutException:
        return False, "POST /responses tool probe timed out"
    except httpx.ConnectError:
        return False, "POST /responses tool probe connect error"
    except Exception as exc:
        return False, str(exc)


__all__ = ["ai_provider_health_check"]
