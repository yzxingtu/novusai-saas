"""
Hybrid Retrieval Engine / 混合检索引擎

Supports vector search, keyword search, and hybrid search with per-KB fusion.
Built-in Redis search result caching.
支持向量检索、关键词检索，以及按知识库独立召回后的融合检索。
内置 Redis 检索结果缓存。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.diagnostics import build_kb_context_diagnostics
from app.ai.rag.embedding import EmbeddingService
from app.ai.rag.merge import merge_best_results
from app.ai.rag.retriever_cache import (
    invalidate_kb_cache as invalidate_kb_cache_helper,
)
from app.ai.rag.retriever_cache_ops import load_search_cache, store_search_cache
from app.ai.rag.retriever_hooks import apply_after_kb_search, apply_before_kb_search
from app.ai.rag.retriever_keyword import KeywordSearcher
from app.ai.rag.retriever_rerank import rerank_results
from app.ai.rag.retriever_rewrite import rewrite_queries
from app.ai.rag.retriever_search import RetrieverSearchExecutor
from app.ai.rag.retriever_support import (
    build_kb_contexts,
    normalize_retrieval_query,
    relevance_gap_filter,
)
from app.ai.rag.retriever_types import ChunkSearchResult, SearchKBContext
from app.ai.rag.retriever_vector import VectorSearcher
from app.core.logging import LogManager
from app.enums.knowledge_base import SearchModeEnum
from app.models.ai.knowledge_base import KnowledgeBase

logger = LogManager.get_logger("ai.rag.retriever")


class HybridRetriever:
    """
    Hybrid Retriever / 混合检索器

    Supports vector, keyword and hybrid retrieval with per-KB fusion.
    支持向量、关键词和混合检索，并按知识库独立召回后再融合。
    """

    _PUNCTUATION_CHARS = KeywordSearcher._PUNCTUATION_CHARS
    _PREFIX_PHRASES = KeywordSearcher._PREFIX_PHRASES
    _SUFFIX_PHRASES = KeywordSearcher._SUFFIX_PHRASES
    _LEADING_FILLERS = KeywordSearcher._LEADING_FILLERS

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        self.embedding_service = EmbeddingService(db, tenant_id)
        self.vector_searcher = VectorSearcher(db, self.embedding_service)
        self.keyword_searcher = KeywordSearcher(db)
        self.search_executor = RetrieverSearchExecutor(
            embedding_service=self.embedding_service,
            vector_searcher=self.vector_searcher,
            keyword_searcher=self.keyword_searcher,
        )

    @classmethod
    def _normalize_retrieval_query(cls, query: str) -> str:
        return normalize_retrieval_query(query)

    async def search(
        self,
        knowledge_base: KnowledgeBase | None = None,
        query: str = "",
        top_k: int = 5,
        score_threshold: float = 0.5,
        search_mode: str | None = None,
        kb_ids: list[int] | None = None,
        rewrite_strategy: str = "none",
        reranker_enabled: bool = False,
        llm_model: str | None = None,
        *,
        knowledge_bases: list[KnowledgeBase] | None = None,
        kb_weights: dict[int, float] | None = None,
    ) -> list[ChunkSearchResult]:
        """
        Hybrid search (with query rewriting and reranking support)
        混合检索（支持查询改写和重排序）。
        """
        effective_query = self._normalize_retrieval_query(query) or query
        kb_contexts = build_kb_contexts(
            knowledge_base=knowledge_base,
            knowledge_bases=knowledge_bases,
            kb_weights=kb_weights,
        )
        if not kb_contexts:
            return []

        mode = search_mode or getattr(
            knowledge_base or kb_contexts[0].knowledge_base,
            "search_mode",
            SearchModeEnum.HYBRID.value,
        )
        target_kb_ids = kb_ids or [ctx.kb_id for ctx in kb_contexts]

        effective_query, target_kb_ids, top_k = await apply_before_kb_search(
            tenant_id=self.tenant_id,
            query=effective_query,
            kb_ids=target_kb_ids,
            top_k=top_k,
        )

        kb_contexts = [ctx for ctx in kb_contexts if ctx.kb_id in target_kb_ids]
        if not kb_contexts:
            return []

        cache_key, cached = await load_search_cache(
            tenant_id=self.tenant_id,
            kb_contexts=kb_contexts,
            query=effective_query,
            mode=mode,
            top_k=top_k,
            score_threshold=score_threshold,
            rewrite_strategy=rewrite_strategy,
            reranker_enabled=reranker_enabled,
        )
        if cached is not None:
            return await apply_after_kb_search(
                tenant_id=self.tenant_id,
                query=effective_query,
                results=cached,
            )

        queries = await rewrite_queries(
            db=self.db,
            tenant_id=self.tenant_id,
            query=effective_query,
            rewrite_strategy=rewrite_strategy,
            llm_model=llm_model,
        )

        best_results: dict[int, ChunkSearchResult] = {}
        for rewritten_query in queries:
            batch = await self.search_executor.search(
                kb_contexts,
                rewritten_query,
                top_k,
                score_threshold,
                mode,
            )
            merge_best_results(best_results, batch)

        all_results = sorted(
            best_results.values(), key=lambda item: item.score, reverse=True
        )
        results = all_results[: top_k * 2] if reranker_enabled else all_results[:top_k]

        if mode != SearchModeEnum.VECTOR.value and results:
            filtered = [item for item in results if item.score >= 0.12]
            if filtered:
                results = filtered

        if reranker_enabled and results:
            results = await rerank_results(
                db=self.db,
                tenant_id=self.tenant_id,
                query=effective_query,
                results=results,
                top_k=top_k,
                llm_model=llm_model,
            )

        results = relevance_gap_filter(results)
        results = await apply_after_kb_search(
            tenant_id=self.tenant_id,
            query=effective_query,
            results=results,
        )

        await store_search_cache(cache_key, results)

        logger.info(
            "Search: mode={}, query_len={}, kb_contexts={}, results={}, rewrite={}, rerank={}",
            mode,
            len(effective_query),
            build_kb_context_diagnostics(kb_contexts),
            len(results),
            rewrite_strategy,
            reranker_enabled,
        )
        return results

    @staticmethod
    def _relevance_gap_filter(
        results: list[ChunkSearchResult],
        *,
        max_drop: float = 0.32,
        min_keep: int = 1,
    ) -> list[ChunkSearchResult]:
        return relevance_gap_filter(results, max_drop=max_drop, min_keep=min_keep)

    def _build_kb_contexts(
        self,
        *,
        knowledge_base: KnowledgeBase | None,
        knowledge_bases: list[KnowledgeBase] | None,
        kb_weights: dict[int, float] | None,
    ) -> list[SearchKBContext]:
        return build_kb_contexts(
            knowledge_base=knowledge_base,
            knowledge_bases=knowledge_bases,
            kb_weights=kb_weights,
        )

    def _apply_technical_term_boost_to_vector_results(
        self,
        query: str,
        results: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        return self.search_executor.apply_technical_term_boost_to_vector_results(
            query,
            results,
        )

    @staticmethod
    async def invalidate_kb_cache(kb_id: int) -> None:
        """Clear search cache for specified KB / 清除指定知识库的检索缓存。"""
        await invalidate_kb_cache_helper(kb_id)


__all__ = [
    "ChunkSearchResult",
    "SearchKBContext",
    "VectorSearcher",
    "KeywordSearcher",
    "HybridRetriever",
]
