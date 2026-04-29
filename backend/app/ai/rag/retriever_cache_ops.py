"""
Cache boundary helpers for retrieval.
"""

from __future__ import annotations

from app.ai.rag.retriever_cache import (
    build_search_cache_key,
    get_search_cache,
    set_search_cache,
)
from app.ai.rag.retriever_types import ChunkSearchResult, SearchKBContext
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag.retriever")


async def load_search_cache(
    *,
    tenant_id: int | None,
    kb_contexts: list[SearchKBContext],
    query: str,
    mode: str,
    top_k: int,
    score_threshold: float,
    rewrite_strategy: str,
    reranker_enabled: bool,
) -> tuple[str, list[ChunkSearchResult] | None]:
    cache_key = build_search_cache_key(
        kb_contexts,
        query,
        mode,
        top_k,
        score_threshold,
        tenant_id=tenant_id,
        rewrite_strategy=rewrite_strategy,
        reranker_enabled=reranker_enabled,
    )
    cached = await get_search_cache(
        cache_key,
        result_factory=lambda item: ChunkSearchResult(**item),
    )
    if cached is not None:
        logger.info("Search cache hit: {}", cache_key)
    return cache_key, cached


async def store_search_cache(
    cache_key: str,
    results: list[ChunkSearchResult],
) -> None:
    await set_search_cache(
        cache_key,
        results,
        payload_factory=lambda item: item.to_dict(),
    )


__all__ = ["load_search_cache", "store_search_cache"]
