"""
Retriever cache helpers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.retriever_cache")

# Redis search cache TTL (5 minutes) / Redis 检索缓存 TTL（5 分钟）
SEARCH_CACHE_TTL = 300
SEARCH_CACHE_PREFIX = "kb:search:"


def build_search_cache_key(
    kb_contexts: list[Any],
    query: str,
    mode: str,
    top_k: int,
    score_threshold: float,
    *,
    tenant_id: int | None,
    rewrite_strategy: str = "none",
    reranker_enabled: bool = False,
) -> str:
    signatures = sorted(context.cache_signature() for context in kb_contexts)
    tenant_signature = "platform" if tenant_id is None else str(int(tenant_id))
    raw = (
        f"tenant:{tenant_signature}:{signatures}:{query}:{mode}:{top_k}:{score_threshold}:"
        f"{rewrite_strategy}:{reranker_enabled}"
    )
    digest = hashlib.md5(raw.encode()).hexdigest()
    kb_prefix = "_".join(
        str(context.kb_id)
        for context in sorted(kb_contexts, key=lambda item: item.kb_id)
    )
    return f"{SEARCH_CACHE_PREFIX}{kb_prefix}:{digest}"


async def get_search_cache(
    key: str,
    *,
    result_factory: Callable[[dict[str, Any]], Any],
) -> list[Any] | None:
    """Read from Redis cache / 从 Redis 读取缓存"""
    try:
        from app.core.redis import cache_get

        data = await cache_get(key)
        if data is None:
            return None
        return [result_factory(item) for item in data]
    except Exception as exc:
        logger.debug("Search cache read failed: key={} err={}", key, str(exc))
        return None


async def set_search_cache(
    key: str,
    results: list[Any],
    *,
    payload_factory: Callable[[Any], dict[str, Any]],
) -> None:
    """Write to Redis cache / 写入 Redis 缓存"""
    try:
        from app.core.redis import cache_set

        await cache_set(
            key,
            [payload_factory(item) for item in results],
            ttl=SEARCH_CACHE_TTL,
        )
    except Exception as exc:
        logger.debug("Search cache write failed: key={} err={}", key, str(exc))


async def invalidate_kb_cache(kb_id: int) -> None:
    """
    Clear search cache for specified KB / 清除指定知识库的检索缓存。
    """
    try:
        from app.core.redis import RedisManager

        client = await RedisManager.get_client()
        patterns = [
            f"{SEARCH_CACHE_PREFIX}{kb_id}:*",
            f"{SEARCH_CACHE_PREFIX}*_{kb_id}:*",
            f"{SEARCH_CACHE_PREFIX}{kb_id}_*",
            f"{SEARCH_CACHE_PREFIX}*_{kb_id}_*",
        ]
        for pattern in patterns:
            async for key in client.scan_iter(match=pattern, count=100):
                await client.delete(key)
    except Exception as exc:
        logger.debug(
            "Search cache invalidation failed: kb_id={} err={}", kb_id, str(exc)
        )


__all__ = [
    "SEARCH_CACHE_PREFIX",
    "SEARCH_CACHE_TTL",
    "build_search_cache_key",
    "get_search_cache",
    "invalidate_kb_cache",
    "set_search_cache",
]
