"""
AI 供应商故障转移服务

当主供应商不可用时，自动切换到备用模型。
从 Redis 读取健康状态，在 AIGateway 调用失败时查找 fallback。
"""

import contextlib
import json

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.models.ai import AIModel
from app.repositories.ai.model_repository import AIModelRepository

logger = LogManager.get_logger("ai.failover")

# Redis 键前缀（与 health check 一致）
HEALTH_KEY_PREFIX = "ai:provider:{provider_id}:health"
HEALTH_HISTORY_PREFIX = "ai:provider:{provider_id}:health_history"


class FailoverService:
    """
    故障转移服务

    查询供应商健康状态，查找备用模型。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._model_repo = AIModelRepository(db)

    async def is_provider_healthy(self, provider_id: int) -> bool:
        """
        检查供应商是否健康

        Args:
            provider_id: 供应商 ID

        Returns:
            是否健康（可用）
        """
        try:
            redis = await get_redis()
            health_key = HEALTH_KEY_PREFIX.format(provider_id=provider_id)
            data = await redis.get(health_key)

            if not data:
                # 没有健康数据，假设可用
                return True

            health = json.loads(data)
            return health.get("is_available", True)

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Failover health check failed: %s", str(e))
            # 查询失败时不阻断请求
            return True

    async def get_fallback_model(
        self,
        model_id: int,
        max_depth: int = 3,
    ) -> AIModel | None:
        """
        获取备用模型（沿 fallback 链查找第一个可用的）

        Args:
            model_id: 当前模型 ID
            max_depth: 最大链式深度（防止循环）

        Returns:
            可用的备用 AIModel，如果没有返回 None
        """
        visited = set()
        current_id = model_id

        for _attempt in range(max_depth):
            # 通过 Repository 获取当前模型
            model = await self._model_repo.get_by_id(current_id)

            if not model or not model.is_active:
                return None

            # 检查是否有 fallback
            fallback_id = getattr(model, "fallback_model_id", None)
            if not fallback_id:
                return None

            # 防止循环
            if fallback_id in visited:
                logger.warning(
                    "Failover: circular chain detected: model_id=%s fallback_id=%s",
                    current_id, fallback_id,
                )
                return None

            visited.add(current_id)

            # 通过 Repository 获取备用模型（预加载 provider 关系）
            fallback = await self._model_repo.get_active_with_provider(fallback_id)

            if not fallback:
                return None

            # 检查备用模型的供应商是否健康
            if await self.is_provider_healthy(fallback.provider_id):
                logger.info(
                    "Failover found: original_model=%s fallback_model=%s fallback_name=%s",
                    model_id, fallback.id, fallback.name,
                )
                return fallback

            # 备用供应商也不健康，继续沿链查找
            current_id = fallback_id

        logger.warning(
            "Failover: no healthy provider found: model_id=%s max_depth=%s",
            model_id, max_depth,
        )
        return None

    @staticmethod
    async def get_all_provider_health() -> list[dict]:
        """
        获取所有供应商的健康状态

        Returns:
            健康状态列表
        """
        try:
            redis = await get_redis()
            results = []

            # 扫描所有健康状态键
            async for key in redis.scan_iter(match="ai:provider:*:health"):
                # 排除 history 键
                if "history" in str(key):
                    continue
                data = await redis.get(key)
                if data:
                    try:
                        health = json.loads(data)
                        results.append(health)
                    except (json.JSONDecodeError, TypeError):
                        pass

            return sorted(results, key=lambda x: x.get("provider_id", 0))

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Failover get all health failed: %s", str(e))
            return []

    @staticmethod
    async def get_provider_health_history(
        provider_id: int,
        limit: int = 100,
    ) -> list[dict]:
        """
        获取供应商健康检查历史（最近 24h）

        Args:
            provider_id: 供应商 ID
            limit: 最大返回条数

        Returns:
            健康检查历史列表（按时间倒序）
        """
        try:
            redis = await get_redis()
            history_key = HEALTH_HISTORY_PREFIX.format(provider_id=provider_id)

            # 获取最近的记录（倒序）
            entries = await redis.zrevrange(history_key, 0, limit - 1)

            results = []
            for entry in entries:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    results.append(json.loads(entry))

            return results

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(
                "Failover: get history failed: provider_id=%s error=%s",
                provider_id, str(e),
            )
            return []


__all__ = ["FailoverService"]
