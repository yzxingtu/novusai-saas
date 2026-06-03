"""
Search execution helpers for retrieval.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

from app.ai.rag.embedding import EmbeddingService
from app.ai.rag.merge import WeightedRRFMerger
from app.ai.rag.query_embedding import QueryEmbeddingResolver
from app.ai.rag.retriever_keyword import KeywordSearcher
from app.ai.rag.retriever_types import ChunkSearchResult, SearchKBContext
from app.ai.rag.retriever_vector import VectorSearcher
from app.ai.rag.unavailable import is_rag_unavailable_error
from app.core.logging import LogManager
from app.exceptions import BusinessException

logger = LogManager.get_logger("ai.rag.retriever")


class RetrieverSearchExecutor:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        vector_searcher: VectorSearcher,
        keyword_searcher: KeywordSearcher,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_searcher = vector_searcher
        self.keyword_searcher = keyword_searcher
        self._embedding_resolver = QueryEmbeddingResolver(self.embedding_service)

    async def search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
        mode: str,
    ) -> list[ChunkSearchResult]:
        from app.enums.knowledge_base import SearchModeEnum

        if mode == SearchModeEnum.VECTOR.value:
            return await self._vector_search(
                kb_contexts,
                query,
                top_k,
                score_threshold,
            )
        if mode == SearchModeEnum.KEYWORD.value:
            return await self._keyword_search(kb_contexts, query, top_k)
        return await self._hybrid_search(
            kb_contexts,
            query,
            top_k,
            score_threshold,
        )

    async def _vector_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)

        async def _search_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            query_embedding = await self._embedding_resolver.resolve_for_context(
                query=query,
                context=context,
            )
            results = await self.vector_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                knowledge_base=context.knowledge_base,
                limit=per_kb_limit,
                score_threshold=score_threshold,
                query_embedding=query_embedding,
            )
            return context, "vector", results

        search_lists = await asyncio.gather(
            *[_search_for_context(context) for context in kb_contexts]
        )
        merged = WeightedRRFMerger.merge(search_lists=search_lists, top_k=top_k)
        return self.apply_technical_term_boost_to_vector_results(query, merged)

    async def _keyword_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)

        async def _search_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            results = await self.keyword_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                limit=per_kb_limit,
            )
            return context, "keyword", results

        search_lists = await asyncio.gather(
            *[_search_for_context(context) for context in kb_contexts]
        )
        return WeightedRRFMerger.merge(search_lists=search_lists, top_k=top_k)

    async def _hybrid_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)

        async def _search_vector_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            try:
                query_embedding = await self._embedding_resolver.resolve_for_context(
                    query=query,
                    context=context,
                )
            except BusinessException as exc:
                if not is_rag_unavailable_error(exc):
                    raise
                logger.warning(
                    "Hybrid RAG vector branch unavailable for kb_id={}, using keyword branch only: {}",
                    context.kb_id,
                    str(exc),
                )
                return context, "vector_unavailable", []
            results = await self.vector_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                knowledge_base=context.knowledge_base,
                limit=per_kb_limit,
                score_threshold=score_threshold,
                query_embedding=query_embedding,
            )
            return context, "vector", results

        async def _search_keyword_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            results = await self.keyword_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                limit=per_kb_limit,
            )
            return context, "keyword", results

        tasks = []
        for context in kb_contexts:
            tasks.append(_search_vector_for_context(context))
            tasks.append(_search_keyword_for_context(context))
        search_lists = await asyncio.gather(*tasks)
        return WeightedRRFMerger.merge(search_lists=search_lists, top_k=top_k)

    def apply_technical_term_boost_to_vector_results(
        self,
        query: str,
        results: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """
        Align vector-only mode with keyword/hybrid technical-term boosting.
        纯向量模式补充与关键词路径一致的技术术语/标识符加权。
        """
        if not results:
            return results
        q = (query or "").strip()
        if not q:
            return results
        boosted: list[ChunkSearchResult] = []
        for r in results:
            boost = self.keyword_searcher._technical_term_boost(
                query=q,
                content=r.content or "",
                metadata=r.metadata,
                document_name=r.document_name or "",
            )
            if boost <= 0:
                boosted.append(r)
                continue
            new_score = min(1.0, float(r.score or 0.0) + boost)
            new_raw = (
                max(float(r.raw_score or 0.0), new_score)
                if r.raw_score is not None
                else new_score
            )
            boosted.append(replace(r, score=new_score, raw_score=new_raw))
        return sorted(boosted, key=lambda item: item.score, reverse=True)


__all__ = ["RetrieverSearchExecutor"]
