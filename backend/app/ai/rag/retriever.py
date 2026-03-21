"""
Hybrid Retrieval Engine / 混合检索引擎

Supports vector search, keyword search, and hybrid search with per-KB fusion.
Built-in Redis search result caching.
支持向量检索、关键词检索，以及按知识库独立召回后的融合检索。
内置 Redis 检索结果缓存。
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from dataclasses import asdict, dataclass, field

from sqlalchemy import Integer, String, and_, bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedding import EmbeddingService
from app.core.logging import LogManager
from app.enums.knowledge_base import DocumentStatusEnum, SearchModeEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument

logger = LogManager.get_logger("ai.rag.retriever")

# RRF fusion constant / RRF 融合常数
RRF_K = 60

# Redis search cache TTL (5 minutes) / Redis 检索缓存 TTL（5 分钟）
SEARCH_CACHE_TTL = 300
SEARCH_CACHE_PREFIX = "kb:search:"


@dataclass
class ChunkSearchResult:
    """Search result item / 检索结果项"""

    chunk_id: int
    content: str
    score: float
    metadata: dict | None = None
    document_name: str = ""
    document_id: int = 0
    chunk_index: int = 0
    highlight: str | None = None
    knowledge_base_id: int = 0
    raw_score: float | None = None
    fusion_score: float | None = None
    kb_weight: float | None = None
    recall_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """For serialization / 用于序列化"""
        return asdict(self)


@dataclass
class SearchKBContext:
    """Runtime retrieval context for one KB / 单个知识库的运行时检索上下文。"""

    knowledge_base: KnowledgeBase
    weight: float = 1.0

    @property
    def kb_id(self) -> int:
        return int(self.knowledge_base.id)

    @property
    def embedding_signature(self) -> tuple[int, int]:
        return (
            int(getattr(self.knowledge_base, "embedding_model_id", 0) or 0),
            int(getattr(self.knowledge_base, "embedding_dimensions", 0) or 0),
        )

    def cache_signature(self) -> str:
        model_id, dimensions = self.embedding_signature
        return f"{self.kb_id}:{round(float(self.weight), 3)}:{model_id}:{dimensions}"


class VectorSearcher:
    """
    Vector Searcher / 向量检索器

    Uses pgvector <=> cosine distance to retrieve most similar chunks.
    使用 pgvector <=> 余弦距离检索最相似分块。
    """

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embedding_service = embedding_service

    async def search(
        self,
        kb_ids: list[int],
        query: str,
        knowledge_base: KnowledgeBase,
        limit: int = 10,
        score_threshold: float = 0.5,
        *,
        query_embedding: list[float] | None = None,
    ) -> list[ChunkSearchResult]:
        """
        pgvector cosine distance search / pgvector 余弦距离检索。
        """
        if query_embedding is None:
            query_embedding = await self.embedding_service.generate_embedding(
                text=query,
                knowledge_base=knowledge_base,
            )

        max_distance = 1.0 - score_threshold
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)

        stmt = (
            select(
                DocumentChunk,
                distance_expr.label("distance"),
            )
            .join(
                KnowledgeDocument,
                and_(
                    KnowledgeDocument.id == DocumentChunk.document_id,
                    KnowledgeDocument.is_deleted.is_(False),
                    KnowledgeDocument.status == DocumentStatusEnum.COMPLETED.value,
                ),
            )
            .where(
                and_(
                    DocumentChunk.knowledge_base_id.in_(kb_ids),
                    DocumentChunk.is_deleted.is_(False),
                    DocumentChunk.embedding.isnot(None),
                    distance_expr <= max_distance,
                )
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        results: list[ChunkSearchResult] = []
        for row in rows:
            chunk = row[0]
            distance = float(row[1])
            doc_name = ""
            try:
                if chunk.document:
                    doc_name = chunk.document.file_name
            except Exception as exc:
                logger.debug(
                    "Vector search document name fallback: chunk_id={} err={}",
                    getattr(chunk, "id", None),
                    str(exc),
                )

            similarity = round(1.0 - distance, 4)
            results.append(
                ChunkSearchResult(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    score=similarity,
                    raw_score=similarity,
                    metadata=chunk.metadata_,
                    document_name=doc_name,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    knowledge_base_id=int(getattr(chunk, "knowledge_base_id", 0) or 0),
                    recall_sources=["vector"],
                )
            )

        return results


class KeywordSearcher:
    """
    Keyword Searcher / 关键词检索器

    Uses PostgreSQL full-text search as the baseline, then boosts exact phrase,
    heading, filename and Chinese token matches.
    使用 PostgreSQL 全文检索作为基线，再叠加短语命中、标题命中、
    文件名命中和中文关键词命中增强。
    """

    _QUERY_SEGMENT_RE = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9][A-Za-z0-9._-]*")

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_query(self, query: str) -> str:
        return re.sub(r"\s+", " ", (query or "").strip())

    def _expand_tokens(self, query: str) -> list[str]:
        tokens: list[str] = []
        for segment in self._QUERY_SEGMENT_RE.findall(query):
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in segment)
            if has_cjk:
                if len(segment) >= 2:
                    tokens.append(segment)
                if len(segment) > 2:
                    tokens.extend(segment[idx:idx + 2] for idx in range(len(segment) - 1))
            elif len(segment) >= 2:
                tokens.append(segment.lower())

        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token and token not in seen:
                seen.add(token)
                deduped.append(token)
        return deduped[:12]

    async def search(
        self,
        kb_ids: list[int],
        query: str,
        limit: int = 10,
    ) -> list[ChunkSearchResult]:
        """
        Boosted keyword search / 增强型关键词检索。
        """
        normalized_query = self._normalize_query(query)
        if not normalized_query:
            return []

        tokens = self._expand_tokens(normalized_query)
        sql = text(
            """
            WITH search_input AS (
                SELECT
                    :raw_query AS raw_query,
                    :fts_query AS fts_query,
                    :tokens AS tokens
            ),
            ranked AS (
                SELECT
                    dc.id,
                    dc.content,
                    dc.document_id,
                    dc.chunk_index,
                    dc.metadata AS chunk_metadata,
                    dc.knowledge_base_id,
                    kd.file_name AS document_name,
                    CASE
                        WHEN si.fts_query <> ''
                             AND dc.content_tsv @@ plainto_tsquery('simple', si.fts_query)
                        THEN ts_rank(dc.content_tsv, plainto_tsquery('simple', si.fts_query))
                        ELSE 0
                    END AS fts_rank,
                    CASE
                        WHEN si.raw_query <> '' AND dc.content ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS exact_hit,
                    CASE
                        WHEN si.raw_query <> ''
                             AND COALESCE(dc.metadata->>'heading', '') ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS heading_hit,
                    CASE
                        WHEN si.raw_query <> '' AND kd.file_name ILIKE '%' || si.raw_query || '%'
                        THEN 1 ELSE 0
                    END AS filename_hit,
                    (
                        SELECT count(*)
                        FROM unnest(si.tokens) AS token
                        WHERE token <> ''
                          AND (
                              dc.content ILIKE '%' || token || '%'
                              OR COALESCE(dc.metadata->>'heading', '') ILIKE '%' || token || '%'
                              OR kd.file_name ILIKE '%' || token || '%'
                          )
                    ) AS token_hits
                FROM document_chunks dc
                JOIN knowledge_documents kd
                    ON kd.id = dc.document_id
                    AND kd.is_deleted = false
                    AND kd.status = 'completed'
                CROSS JOIN search_input si
                WHERE dc.knowledge_base_id = ANY(:kb_ids)
                    AND dc.is_deleted = false
                    AND (
                        (si.fts_query <> '' AND dc.content_tsv @@ plainto_tsquery('simple', si.fts_query))
                        OR (si.raw_query <> '' AND dc.content ILIKE '%' || si.raw_query || '%')
                        OR (si.raw_query <> '' AND COALESCE(dc.metadata->>'heading', '') ILIKE '%' || si.raw_query || '%')
                        OR (si.raw_query <> '' AND kd.file_name ILIKE '%' || si.raw_query || '%')
                        OR EXISTS (
                            SELECT 1
                            FROM unnest(si.tokens) AS token
                            WHERE token <> ''
                              AND (
                                  dc.content ILIKE '%' || token || '%'
                                  OR COALESCE(dc.metadata->>'heading', '') ILIKE '%' || token || '%'
                                  OR kd.file_name ILIKE '%' || token || '%'
                              )
                        )
                    )
            )
            SELECT
                id,
                content,
                document_id,
                chunk_index,
                chunk_metadata,
                knowledge_base_id,
                document_name,
                (
                    fts_rank
                    + exact_hit * 0.8
                    + heading_hit * 0.45
                    + filename_hit * 0.35
                    + LEAST(token_hits, :token_hit_cap) * :token_hit_weight
                ) AS rank
            FROM ranked
            ORDER BY rank DESC, exact_hit DESC, heading_hit DESC, token_hits DESC, id DESC
            LIMIT :limit
            """
        ).bindparams(
            bindparam("kb_ids", type_=ARRAY(Integer)),
            bindparam("tokens", type_=ARRAY(String)),
        )

        result = await self.db.execute(
            sql,
            {
                "raw_query": normalized_query,
                "fts_query": normalized_query,
                "tokens": tokens,
                "kb_ids": kb_ids,
                "limit": limit,
                "token_hit_cap": 6,
                "token_hit_weight": 0.08,
            },
        )
        rows = result.fetchall()

        results: list[ChunkSearchResult] = []
        for row in rows:
            rank = round(float(row[7]), 4)
            results.append(
                ChunkSearchResult(
                    chunk_id=row[0],
                    content=row[1],
                    score=rank,
                    raw_score=rank,
                    metadata=row[4],
                    document_name=row[6] or "",
                    document_id=row[2],
                    chunk_index=row[3],
                    knowledge_base_id=int(row[5] or 0),
                    recall_sources=["keyword"],
                )
            )

        return results


class HybridRetriever:
    """
    Hybrid Retriever / 混合检索器

    Supports vector, keyword and hybrid retrieval with per-KB fusion.
    支持向量、关键词和混合检索，并按知识库独立召回后再融合。
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        self.embedding_service = EmbeddingService(db, tenant_id)
        self.vector_searcher = VectorSearcher(db, self.embedding_service)
        self.keyword_searcher = KeywordSearcher(db)

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
        kb_contexts = self._build_kb_contexts(
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

        from app.ai.events.hooks import HookPoint, get_hook_registry

        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_KB_SEARCH):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_KB_SEARCH,
                tenant_id=self.tenant_id,
                query=query,
                kb_ids=target_kb_ids,
                top_k=top_k,
            )
            query = hook_ctx.get("query", query)
            target_kb_ids = hook_ctx.get("kb_ids", target_kb_ids)
            top_k = hook_ctx.get("top_k", top_k)

        kb_contexts = [ctx for ctx in kb_contexts if ctx.kb_id in target_kb_ids]
        if not kb_contexts:
            return []

        cache_key = self._build_cache_key(
            kb_contexts,
            query,
            mode,
            top_k,
            score_threshold,
            rewrite_strategy=rewrite_strategy,
            reranker_enabled=reranker_enabled,
        )
        cached = await self._get_cache(cache_key)
        if cached is not None:
            logger.info("Search cache hit: {}", cache_key)
            if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
                hook_ctx = await hook_registry.trigger(
                    HookPoint.AFTER_KB_SEARCH,
                    tenant_id=self.tenant_id,
                    query=query,
                    results=cached,
                )
                cached = hook_ctx.get("results", cached)
            return cached

        from app.ai.rag.query_rewriter import get_rewriter

        rewriter = get_rewriter(rewrite_strategy, self.db, self.tenant_id, llm_model)
        queries = await rewriter.rewrite(query)

        best_results: dict[int, ChunkSearchResult] = {}
        for rewritten_query in queries:
            if mode == SearchModeEnum.VECTOR.value:
                batch = await self._vector_search(
                    kb_contexts,
                    rewritten_query,
                    top_k,
                    score_threshold,
                )
            elif mode == SearchModeEnum.KEYWORD.value:
                batch = await self._keyword_search(
                    kb_contexts,
                    rewritten_query,
                    top_k,
                )
            else:
                batch = await self._hybrid_search(
                    kb_contexts,
                    rewritten_query,
                    top_k,
                    score_threshold,
                )

            self._merge_best_results(best_results, batch)

        all_results = sorted(best_results.values(), key=lambda item: item.score, reverse=True)
        results = all_results[: top_k * 2] if reranker_enabled else all_results[:top_k]

        if mode != SearchModeEnum.VECTOR.value and results:
            filtered = [item for item in results if item.score >= 0.12]
            if filtered:
                results = filtered

        if reranker_enabled and results:
            from app.ai.rag.reranker import LLMReranker

            reranker = LLMReranker(self.db, self.tenant_id, llm_model)
            results = await reranker.rerank(query, results, top_k=top_k)

        if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_KB_SEARCH,
                tenant_id=self.tenant_id,
                query=query,
                results=results,
            )
            results = hook_ctx.get("results", results)

        await self._set_cache(cache_key, results)

        logger.info(
            "Search: mode={}, query_len={}, kb_contexts={}, results={}, rewrite={}, rerank={}",
            mode,
            len(query),
            [
                {
                    "kb_id": ctx.kb_id,
                    "weight": round(float(ctx.weight), 3),
                    "embedding": ctx.embedding_signature,
                }
                for ctx in kb_contexts
            ],
            len(results),
            rewrite_strategy,
            reranker_enabled,
        )
        return results

    def _build_kb_contexts(
        self,
        *,
        knowledge_base: KnowledgeBase | None,
        knowledge_bases: list[KnowledgeBase] | None,
        kb_weights: dict[int, float] | None,
    ) -> list[SearchKBContext]:
        kb_list = knowledge_bases or ([knowledge_base] if knowledge_base is not None else [])
        contexts: list[SearchKBContext] = []
        seen: set[int] = set()
        for kb in kb_list:
            kb_id = int(getattr(kb, "id", 0) or 0)
            if kb_id <= 0 or kb_id in seen:
                continue
            seen.add(kb_id)
            contexts.append(
                SearchKBContext(
                    knowledge_base=kb,
                    weight=float((kb_weights or {}).get(kb_id, 1.0)),
                )
            )
        return contexts

    def _merge_best_results(
        self,
        best_results: dict[int, ChunkSearchResult],
        batch: list[ChunkSearchResult],
    ) -> None:
        for result in batch:
            current = best_results.get(result.chunk_id)
            if current is None:
                best_results[result.chunk_id] = result
                continue

            current.recall_sources = sorted(
                set(current.recall_sources) | set(result.recall_sources)
            )
            if result.raw_score is not None:
                current.raw_score = max(current.raw_score or 0.0, result.raw_score)
            if result.fusion_score is not None:
                current.fusion_score = max(current.fusion_score or 0.0, result.fusion_score)
            current.score = max(current.score, result.score)

    async def _vector_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)
        embedding_cache: dict[tuple[int, int], list[float]] = {}

        async def _search_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            signature = context.embedding_signature
            if signature not in embedding_cache:
                embedding_cache[signature] = await self.embedding_service.generate_embedding(
                    text=query,
                    knowledge_base=context.knowledge_base,
                )
            results = await self.vector_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                knowledge_base=context.knowledge_base,
                limit=per_kb_limit,
                score_threshold=score_threshold,
                query_embedding=embedding_cache[signature],
            )
            return context, "vector", results

        search_lists = await asyncio.gather(
            *[_search_for_context(context) for context in kb_contexts]
        )
        return self._weighted_rrf_merge(search_lists, top_k)

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
        return self._weighted_rrf_merge(search_lists, top_k)

    async def _hybrid_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)
        embedding_cache: dict[tuple[int, int], list[float]] = {}

        async def _search_vector_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            signature = context.embedding_signature
            if signature not in embedding_cache:
                embedding_cache[signature] = await self.embedding_service.generate_embedding(
                    text=query,
                    knowledge_base=context.knowledge_base,
                )
            results = await self.vector_searcher.search(
                kb_ids=[context.kb_id],
                query=query,
                knowledge_base=context.knowledge_base,
                limit=per_kb_limit,
                score_threshold=score_threshold,
                query_embedding=embedding_cache[signature],
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
        return self._weighted_rrf_merge(search_lists, top_k)

    def _weighted_rrf_merge(
        self,
        search_lists: list[tuple[SearchKBContext, str, list[ChunkSearchResult]]],
        top_k: int,
    ) -> list[ChunkSearchResult]:
        if not search_lists:
            return []

        score_map: dict[int, tuple[float, ChunkSearchResult]] = {}
        rrf_max = 0.0

        for context, source, results in search_lists:
            if not results:
                continue

            weight_factor = self._weight_factor(context.weight)
            rrf_max += weight_factor / (RRF_K + 1)

            for rank, result in enumerate(results, start=1):
                contribution = weight_factor / (RRF_K + rank)
                if result.chunk_id in score_map:
                    merged_score, merged_result = score_map[result.chunk_id]
                    merged_result.recall_sources = sorted(
                        set(merged_result.recall_sources) | {source}
                    )
                    if result.raw_score is not None:
                        merged_result.raw_score = max(
                            merged_result.raw_score or 0.0,
                            result.raw_score,
                        )
                    merged_result.kb_weight = context.weight
                    score_map[result.chunk_id] = (merged_score + contribution, merged_result)
                    continue

                cloned = ChunkSearchResult(**result.to_dict())
                cloned.recall_sources = sorted(set(cloned.recall_sources) | {source})
                cloned.kb_weight = context.weight
                if cloned.raw_score is None:
                    cloned.raw_score = result.score
                score_map[result.chunk_id] = (contribution, cloned)

        if not score_map:
            return []

        sorted_items = sorted(score_map.values(), key=lambda item: item[0], reverse=True)
        results: list[ChunkSearchResult] = []
        for weighted_rrf, chunk_result in sorted_items[:top_k]:
            normalized = min(weighted_rrf / max(rrf_max, 1e-9), 1.0)
            chunk_result.fusion_score = round(normalized, 4)
            chunk_result.score = chunk_result.fusion_score
            results.append(chunk_result)
        return results

    @staticmethod
    def _weight_factor(weight: float) -> float:
        """
        Keep KB weight as a prior, not an override.
        将 KB 权重作为先验而非绝对覆盖，避免低相关结果被硬顶上来。
        """
        safe_weight = max(0.1, min(2.0, float(weight)))
        return max(0.65, min(1.25, 0.5 + (math.sqrt(safe_weight) / 2)))

    @staticmethod
    def _build_cache_key(
        kb_contexts: list[SearchKBContext],
        query: str,
        mode: str,
        top_k: int,
        score_threshold: float,
        rewrite_strategy: str = "none",
        reranker_enabled: bool = False,
    ) -> str:
        signatures = sorted(context.cache_signature() for context in kb_contexts)
        raw = (
            f"{signatures}:{query}:{mode}:{top_k}:{score_threshold}:"
            f"{rewrite_strategy}:{reranker_enabled}"
        )
        digest = hashlib.md5(raw.encode()).hexdigest()
        kb_prefix = "_".join(str(context.kb_id) for context in sorted(kb_contexts, key=lambda item: item.kb_id))
        return f"{SEARCH_CACHE_PREFIX}{kb_prefix}:{digest}"

    @staticmethod
    async def _get_cache(key: str) -> list[ChunkSearchResult] | None:
        """Read from Redis cache / 从 Redis 读取缓存"""
        try:
            from app.core.redis import cache_get

            data = await cache_get(key)
            if data is None:
                return None
            return [ChunkSearchResult(**item) for item in data]
        except Exception as exc:
            logger.debug("Search cache read failed: key={} err={}", key, str(exc))
            return None

    @staticmethod
    async def _set_cache(key: str, results: list[ChunkSearchResult]) -> None:
        """Write to Redis cache / 写入 Redis 缓存"""
        try:
            from app.core.redis import cache_set

            await cache_set(key, [item.to_dict() for item in results], ttl=SEARCH_CACHE_TTL)
        except Exception as exc:
            logger.debug("Search cache write failed: key={} err={}", key, str(exc))

    @staticmethod
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
            logger.debug("Search cache invalidation failed: kb_id={} err={}", kb_id, str(exc))


# Backward compatibility: keep VectorRetriever alias / 向后兼容：保留 VectorRetriever 别名
VectorRetriever = HybridRetriever


__all__ = [
    "ChunkSearchResult",
    "SearchKBContext",
    "VectorSearcher",
    "KeywordSearcher",
    "HybridRetriever",
    "VectorRetriever",
]
