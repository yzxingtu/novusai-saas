"""
AI Provider Failover Service / AI 供应商故障转移服务

Automatically switches to fallback models when primary provider is unavailable.
Reads health status from Redis and finds fallback on AIGateway call failure.
当主供应商不可用时，自动切换到备用模型。
从 Redis 读取健康状态，在 AIGateway 调用失败时查找 fallback。
"""

import contextlib
import json
from datetime import datetime, timezone

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import (
    AIGatewayError,
    extract_provider_error_message,
    is_retryable,
    looks_like_html_document_text,
)
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.models.ai import AIModel
from app.repositories.ai.model_repository import AIModelRepository

logger = LogManager.get_logger("ai.failover")

# Redis key prefixes (consistent with health check) / Redis 键前缀（与 health check 一致）
HEALTH_KEY_PREFIX = "ai:provider:{provider_id}:health"
HEALTH_HISTORY_PREFIX = "ai:provider:{provider_id}:health_history"
RUNTIME_FAILURE_KEY_PREFIX = "ai:provider:{provider_id}:runtime_failure"
DEFAULT_RUNTIME_FAILURE_TTL_SECONDS = 300


def _normalize_checked_at(value: object) -> object:
    """Normalize ISO timestamps in health payloads / 规范化健康负载中的 ISO 时间戳。"""
    if not isinstance(value, str) or not value:
        return value

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.isoformat()


def _normalize_health_payload(payload: dict) -> dict:
    """Normalize checked_at field in a Redis health payload / 规范化 Redis 健康负载中的 checked_at。"""
    checked_at = payload.get("checked_at")
    if checked_at is not None:
        payload["checked_at"] = _normalize_checked_at(checked_at)
    return payload


def _safe_runtime_error_message(error: BaseException | None) -> str | None:
    provider_message = str(extract_provider_error_message(error) or "").strip()
    if provider_message and not looks_like_html_document_text(provider_message):
        return provider_message

    text = str(error or "").strip()
    if text and not looks_like_html_document_text(text):
        return text
    return None


class FailoverService:
    """
    Failover Service / 故障转移服务

    Queries provider health status and finds fallback models.
    查询供应商健康状态，查找备用模型。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._model_repo = AIModelRepository(db)

    @staticmethod
    def should_record_runtime_failure(error: BaseException | None) -> bool:
        if not isinstance(error, AIGatewayError):
            return False
        if is_retryable(error):
            return True
        status_code = int(getattr(error, "status_code", 0) or 0)
        return 500 <= status_code < 600

    async def get_provider_runtime_failure(
        self,
        provider_id: int,
    ) -> dict | None:
        try:
            redis = await get_redis()
            key = RUNTIME_FAILURE_KEY_PREFIX.format(provider_id=provider_id)
            data = await redis.get(key)
            if not data:
                return None
            return _normalize_health_payload(json.loads(data))
        except (RedisError, json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Failover runtime failure lookup failed: provider_id={} error={}",
                provider_id,
                str(e),
            )
            return None

    async def record_provider_runtime_failure(
        self,
        provider_id: int,
        *,
        model_id: int | None = None,
        error: BaseException | None = None,
        ttl_seconds: int = DEFAULT_RUNTIME_FAILURE_TTL_SECONDS,
    ) -> None:
        if provider_id <= 0 or not self.should_record_runtime_failure(error):
            return

        payload = {
            "provider_id": provider_id,
            "model_id": model_id,
            "error_code": str(getattr(error, "error_code", "") or "").strip() or None,
            "status_code": int(getattr(error, "status_code", 0) or 0) or None,
            "message": _safe_runtime_error_message(error),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": "runtime_failure",
        }
        payload = {key: value for key, value in payload.items() if value is not None}

        try:
            redis = await get_redis()
            key = RUNTIME_FAILURE_KEY_PREFIX.format(provider_id=provider_id)
            await redis.setex(
                key,
                ttl_seconds,
                json.dumps(payload, ensure_ascii=False),
            )
            logger.warning(
                "Failover runtime failure recorded: provider_id={} model_id={} ttl_seconds={} error_code={} status_code={}",
                provider_id,
                model_id,
                ttl_seconds,
                payload.get("error_code"),
                payload.get("status_code"),
            )
        except (RedisError, TypeError, ValueError) as e:
            logger.warning(
                "Failover runtime failure record failed: provider_id={} error={}",
                provider_id,
                str(e),
            )

    @staticmethod
    def _candidate_sort_key(
        model: AIModel,
        *,
        preferred_provider_id: int | None,
        preferred_tier: str | None,
    ) -> tuple[int, int, float, int, int]:
        input_price = getattr(model, "input_price_per_1k", None)
        normalized_price = float(input_price) if input_price is not None else float("inf")
        context_window = int(getattr(model, "context_window", 0) or 0)
        return (
            0
            if preferred_provider_id is not None
            and getattr(model, "provider_id", None) == preferred_provider_id
            else 1,
            0
            if preferred_tier
            and str(getattr(model, "tier", "") or "").strip() == preferred_tier
            else 1,
            normalized_price,
            -context_window,
            int(getattr(model, "id", 0) or 0),
        )

    async def is_provider_healthy(self, provider_id: int) -> bool:
        """
        Check if provider is healthy.
        检查供应商是否健康。

        Args:
            provider_id: Provider ID / 供应商 ID

        Returns:
            Whether healthy (available) / 是否健康（可用）
        """
        try:
            runtime_failure = await self.get_provider_runtime_failure(provider_id)
            if runtime_failure is not None:
                return False

            redis = await get_redis()
            health_key = HEALTH_KEY_PREFIX.format(provider_id=provider_id)
            data = await redis.get(health_key)

            if not data:
                # No health data, assume available / 没有健康数据，假设可用
                return True

            health = json.loads(data)
            return bool(health.get("is_healthy", health.get("is_available", True)))

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Failover health check failed: {}", str(e))
            # Don't block requests on query failure / 查询失败时不阻断请求
            return True

    async def get_fallback_model(
        self,
        model_id: int,
        max_depth: int = 3,
        *,
        needs_vision: bool = False,
        needs_audio: bool = False,
        needs_video: bool = False,
        needs_fc: bool = False,
        min_context_window: int | None = None,
    ) -> AIModel | None:
        """
        Get fallback model (find first available along fallback chain).
        获取备用模型（沿 fallback 链查找第一个可用的）。

        Args:
            model_id: Current model ID / 当前模型 ID
            max_depth: Max chain depth (prevents loops) / 最大链式深度（防止循环）

        Returns:
            Available fallback AIModel, or None / 可用的备用 AIModel，如果没有返回 None
        """
        visited = set()
        current_id = model_id
        original_model = await self._model_repo.get_active_with_provider(model_id)
        preferred_provider_id = (
            getattr(original_model, "provider_id", None) if original_model else None
        )
        preferred_tier = (
            str(getattr(original_model, "tier", "") or "").strip() or None
            if original_model is not None
            else None
        )

        for _attempt in range(max_depth):
            # Get current model via Repository / 通过 Repository 获取当前模型
            model = await self._model_repo.get_by_id(current_id)

            if not model or not model.is_active:
                return None

            # Check if fallback exists / 检查是否有 fallback
            fallback_id = getattr(model, "fallback_model_id", None)
            if not fallback_id:
                break

            # Prevent circular chains / 防止循环
            if fallback_id in visited:
                logger.warning(
                    "Failover: circular chain detected: model_id={} fallback_id={}",
                    current_id,
                    fallback_id,
                )
                break

            visited.add(current_id)

            # Get fallback model via Repository (eager-load provider) / 通过 Repository 获取备用模型（预加载 provider 关系）
            fallback = await self._model_repo.get_active_with_provider(fallback_id)

            if not fallback:
                break

            # Check if fallback model's provider is healthy / 检查备用模型的供应商是否健康
            if await self.is_provider_healthy(fallback.provider_id):
                logger.info(
                    "Failover found: original_model={} fallback_model={} fallback_name={}",
                    model_id,
                    fallback.id,
                    fallback.name,
                )
                return fallback

            # Fallback provider also unhealthy, continue along chain / 备用供应商也不健康，继续沿链查找
            current_id = fallback_id

        unhealthy_provider_ids: set[int] = set()
        if preferred_provider_id and not await self.is_provider_healthy(preferred_provider_id):
            unhealthy_provider_ids.add(preferred_provider_id)

        compatible_candidates = await self._model_repo.list_compatible_chat_models(
            exclude_model_ids=list({model_id, *visited}),
            needs_vision=needs_vision,
            needs_audio=needs_audio,
            needs_video=needs_video,
            needs_function_calling=needs_fc,
            min_context_window=min_context_window,
        )
        compatible_candidates = sorted(
            compatible_candidates,
            key=lambda item: self._candidate_sort_key(
                item,
                preferred_provider_id=preferred_provider_id,
                preferred_tier=preferred_tier,
            ),
        )
        for candidate in compatible_candidates:
            if getattr(candidate, "provider_id", None) in unhealthy_provider_ids:
                continue
            if not await self.is_provider_healthy(candidate.provider_id):
                continue
            logger.info(
                "Failover compatible fallback found: original_model={} fallback_model={} fallback_name={}",
                model_id,
                candidate.id,
                candidate.name,
            )
            return candidate

        logger.warning(
            "Failover: no healthy provider found: model_id={} max_depth={}",
            model_id,
            max_depth,
        )
        return None

    @staticmethod
    async def get_all_provider_health() -> list[dict]:
        """
        Get health status of all providers.
        获取所有供应商的健康状态。

        Returns:
            Health status list / 健康状态列表
        """
        try:
            redis = await get_redis()
            results = []

            runtime_failures: dict[int, dict] = {}
            async for key in redis.scan_iter(match="ai:provider:*:runtime_failure"):
                data = await redis.get(key)
                if not data:
                    continue
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    payload = _normalize_health_payload(json.loads(data))
                    provider_id = int(payload.get("provider_id") or 0)
                    if provider_id > 0:
                        runtime_failures[provider_id] = payload

            # Scan all health status keys / 扫描所有健康状态键
            async for key in redis.scan_iter(match="ai:provider:*:health"):
                # Exclude history keys / 排除 history 键
                if "history" in str(key):
                    continue
                data = await redis.get(key)
                if data:
                    try:
                        health = _normalize_health_payload(json.loads(data))
                        runtime_failure = runtime_failures.get(
                            int(health.get("provider_id") or 0)
                        )
                        if runtime_failure is not None:
                            health["runtime_failure"] = runtime_failure
                            health["runtime_failure_override"] = True
                            health["is_healthy"] = False
                            health["is_available"] = False
                        results.append(health)
                    except (json.JSONDecodeError, TypeError):
                        pass

            return sorted(results, key=lambda x: x.get("provider_id", 0))

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Failover get all health failed: {}", str(e))
            return []

    @staticmethod
    async def get_provider_health_history(
        provider_id: int,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get provider health check history (last 24h).
        获取供应商健康检查历史（最近 24h）。

        Args:
            provider_id: Provider ID / 供应商 ID
            limit: Max entries to return / 最大返回条数

        Returns:
            Health check history list (reverse chronological) / 健康检查历史列表（按时间倒序）
        """
        try:
            redis = await get_redis()
            history_key = HEALTH_HISTORY_PREFIX.format(provider_id=provider_id)

            # Get latest records (reverse order) / 获取最近的记录（倒序）
            entries = await redis.zrevrange(history_key, 0, limit - 1)

            results = []
            for entry in entries:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    results.append(_normalize_health_payload(json.loads(entry)))

            return results

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(
                "Failover: get history failed: provider_id={} error={}",
                provider_id,
                str(e),
            )
            return []


__all__ = ["FailoverService"]
