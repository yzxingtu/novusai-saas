"""
Hybrid Retrieval Engine / 混合检索引擎

Supports vector search, keyword search, and hybrid search with per-KB fusion.
Built-in Redis search result caching.
支持向量检索、关键词检索，以及按知识库独立召回后的融合检索。
内置 Redis 检索结果缓存。
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field, replace

from sqlalchemy import Integer, String, and_, bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.diagnostics import build_kb_context_diagnostics
from app.ai.rag.embedding import EmbeddingService
from app.ai.rag.merge import WeightedRRFMerger, merge_best_results
from app.ai.rag.query_embedding import QueryEmbeddingResolver
from app.ai.rag.retriever_cache import (
    build_search_cache_key,
    get_search_cache,
    set_search_cache,
)
from app.ai.rag.retriever_cache import (
    invalidate_kb_cache as invalidate_kb_cache_helper,
)
from app.core.logging import LogManager
from app.enums.knowledge_base import DocumentStatusEnum, SearchModeEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument

logger = LogManager.get_logger("ai.rag.retriever")


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

    _PUNCTUATION_CHARS = " \t\r\n，,。：:；;！？!?."
    _PREFIX_PHRASES = [
        "请你根据内部知识库",
        "请根据内部知识库",
        "麻烦你根据内部知识库",
        "帮我根据内部知识库",
        "请你在内部知识库中",
        "请在内部知识库中",
        "根据内部知识库",
        "based on the internal knowledge base",
        "answer based on the internal knowledge base",
        "respond based on the internal knowledge base",
        "please answer based on the internal knowledge base",
        "please explain using the internal knowledge base",
    ]
    _SUFFIX_PHRASES = [
        "请基于内部知识库回答",
        "请基于内部知识库",
        "请只基于内部知识回答",
        "请只基于内部知识库回答",
        "请只基于内部知识",
        "请只参考内部知识库",
        "请仅参考内部知识库",
        "请不要使用外部资料",
        "please answer based on the internal knowledge base only",
        "please do not use external sources",
        "please do not reference external information",
    ]
    _LEADING_FILLERS = [
        "请你回答",
        "麻烦你回答",
        "帮我回答",
        "请你说明",
        "麻烦你说明",
        "请你解释",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_query(self, query: str) -> str:
        return " ".join((query or "").split())

    @staticmethod
    def _is_cjk(ch: str) -> bool:
        return "\u4e00" <= ch <= "\u9fff"

    @classmethod
    def _iter_query_segments(cls, query: str) -> list[str]:
        segments: list[str] = []
        i = 0
        length = len(query)
        while i < length:
            ch = query[i]
            if cls._is_cjk(ch):
                start = i
                while i < length and cls._is_cjk(query[i]):
                    i += 1
                segments.append(query[start:i])
                continue
            if ch.isalnum():
                start = i
                while i < length and (query[i].isalnum() or query[i] in "._-"):
                    i += 1
                segment = query[start:i]
                if segment:
                    segments.append(segment)
                continue
            i += 1
        return segments

    @classmethod
    def _extract_quoted_terms(cls, query: str) -> list[str]:
        terms: list[str] = []
        i = 0
        length = len(query)
        while i < length:
            ch = query[i]
            if ch in {'"', "'"}:
                quote = ch
                start = i + 1
                i += 1
                while i < length and query[i] != quote:
                    i += 1
                term = query[start:i].strip()
                if 2 <= len(term) <= 64:
                    terms.append(term)
                i += 1
                continue
            i += 1
        return terms

    @classmethod
    def _strip_candidates(
        cls,
        text: str,
        candidates: list[str],
        *,
        strip_start: bool,
    ) -> str:
        stripped = text
        while True:
            matched = False
            for candidate in candidates:
                candidate_lower = candidate.lower()
                working = stripped.lstrip(cls._PUNCTUATION_CHARS)
                lower = working.lower()
                if strip_start and lower.startswith(candidate_lower):
                    stripped = working[len(candidate) :]
                    stripped = stripped.lstrip(cls._PUNCTUATION_CHARS)
                    matched = True
                    break
                if not strip_start:
                    working = stripped.rstrip(cls._PUNCTUATION_CHARS)
                    lower = working.lower()
                    if lower.endswith(candidate_lower):
                        stripped = working[: -len(candidate)].rstrip(
                            cls._PUNCTUATION_CHARS
                        )
                        matched = True
                        break
            if not matched:
                break
        return stripped

    @classmethod
    def _strip_leading_fillers(cls, text: str) -> str:
        stripped = text
        for filler in cls._LEADING_FILLERS:
            if stripped.lower().startswith(filler):
                stripped = stripped[len(filler) :]
                stripped = stripped.lstrip(cls._PUNCTUATION_CHARS)
                break
        return stripped

    def _expand_tokens(self, query: str) -> list[str]:
        tokens: list[str] = []
        for segment in self._iter_query_segments(query):
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in segment)
            if has_cjk:
                if len(segment) >= 2:
                    tokens.append(segment)
                if len(segment) > 2:
                    tokens.extend(
                        segment[idx : idx + 2] for idx in range(len(segment) - 1)
                    )
            elif len(segment) >= 2:
                tokens.append(segment.lower())

        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token and token not in seen:
                seen.add(token)
                deduped.append(token)
        return deduped[:12]

    def _extract_exact_terms(self, query: str) -> list[str]:
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        candidates: list[str] = []
        candidates.extend(self._extract_quoted_terms(normalized))

        for token in self._iter_query_segments(normalized):
            token = token.strip()
            if len(token) < 2:
                continue
            has_symbol = any(ch in token for ch in "._-:/#")
            has_digit = any(ch.isdigit() for ch in token)
            has_upper = any(ch.isupper() for ch in token)
            if has_symbol or has_digit or has_upper:
                candidates.append(token)

        deduped: list[str] = []
        seen: set[str] = set()
        for term in candidates:
            lowered = term.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(term)
        return deduped[:8]

    def _technical_term_boost(
        self,
        *,
        query: str,
        content: str,
        metadata: dict | None,
        document_name: str,
    ) -> float:
        exact_terms = self._extract_exact_terms(query)
        if not exact_terms:
            return 0.0

        haystacks = [
            (content or "").lower(),
            str((metadata or {}).get("heading") or "").lower(),
            (document_name or "").lower(),
        ]
        boost = 0.0
        for term in exact_terms:
            lowered = term.lower()
            if any(lowered in haystack for haystack in haystacks if haystack):
                boost += 0.18 if any(ch in term for ch in "._-:/#") else 0.1
        return min(boost, 0.72)

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
            boost = self._technical_term_boost(
                query=normalized_query,
                content=row[1] or "",
                metadata=row[4],
                document_name=row[6] or "",
            )
            rank = round(float(row[7]) + boost, 4)
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

    @classmethod
    def _strip_candidates(
        cls,
        text: str,
        candidates: list[str],
        *,
        strip_start: bool,
    ) -> str:
        return KeywordSearcher._strip_candidates(
            text,
            candidates,
            strip_start=strip_start,
        )

    @classmethod
    def _strip_leading_fillers(cls, text: str) -> str:
        return KeywordSearcher._strip_leading_fillers(text)

    @classmethod
    def _normalize_retrieval_query(cls, query: str) -> str:
        normalized = " ".join((query or "").split())
        if not normalized:
            return ""

        # Remove retrieval wrappers so recall focuses on the user's core question.
        # 去掉“基于内部知识库回答”等包装语，避免污染检索 query。
        stripped = normalized
        stripped = cls._strip_candidates(
            stripped, cls._PREFIX_PHRASES, strip_start=True
        )
        stripped = cls._strip_candidates(
            stripped, cls._SUFFIX_PHRASES, strip_start=False
        )
        stripped = cls._strip_leading_fillers(stripped)
        stripped = stripped.strip(cls._PUNCTUATION_CHARS)
        return stripped or normalized

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
                query=effective_query,
                kb_ids=target_kb_ids,
                top_k=top_k,
            )
            effective_query = hook_ctx.get("query", effective_query)
            target_kb_ids = hook_ctx.get("kb_ids", target_kb_ids)
            top_k = hook_ctx.get("top_k", top_k)

        kb_contexts = [ctx for ctx in kb_contexts if ctx.kb_id in target_kb_ids]
        if not kb_contexts:
            return []

        cache_key = build_search_cache_key(
            kb_contexts,
            effective_query,
            mode,
            top_k,
            score_threshold,
            rewrite_strategy=rewrite_strategy,
            reranker_enabled=reranker_enabled,
        )
        cached = await get_search_cache(
            cache_key,
            result_factory=lambda item: ChunkSearchResult(**item),
        )
        if cached is not None:
            logger.info("Search cache hit: {}", cache_key)
            if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
                hook_ctx = await hook_registry.trigger(
                    HookPoint.AFTER_KB_SEARCH,
                    tenant_id=self.tenant_id,
                    query=effective_query,
                    results=cached,
                )
                cached = hook_ctx.get("results", cached)
            return cached

        from app.ai.rag.query_rewriter import get_rewriter

        rewriter = get_rewriter(rewrite_strategy, self.db, self.tenant_id, llm_model)
        queries = await rewriter.rewrite(effective_query)

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
            from app.ai.rag.reranker import LLMReranker

            reranker = LLMReranker(self.db, self.tenant_id, llm_model)
            results = await reranker.rerank(effective_query, results, top_k=top_k)

        results = self._relevance_gap_filter(results)

        if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_KB_SEARCH,
                tenant_id=self.tenant_id,
                query=effective_query,
                results=results,
            )
            results = hook_ctx.get("results", results)

        await set_search_cache(
            cache_key,
            results,
            payload_factory=lambda item: item.to_dict(),
        )

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
        if len(results) <= min_keep:
            return results

        kept: list[ChunkSearchResult] = []
        previous_score: float | None = None
        for index, result in enumerate(results):
            if index < min_keep:
                kept.append(result)
                previous_score = float(result.score or 0.0)
                continue
            current_score = float(result.score or 0.0)
            if previous_score is not None and previous_score - current_score > max_drop:
                break
            kept.append(result)
            previous_score = current_score
        return kept

    def _build_kb_contexts(
        self,
        *,
        knowledge_base: KnowledgeBase | None,
        knowledge_bases: list[KnowledgeBase] | None,
        kb_weights: dict[int, float] | None,
    ) -> list[SearchKBContext]:
        kb_list = knowledge_bases or (
            [knowledge_base] if knowledge_base is not None else []
        )
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

    async def _vector_search(
        self,
        kb_contexts: list[SearchKBContext],
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        per_kb_limit = max(top_k * 2, top_k)
        resolver = QueryEmbeddingResolver(self.embedding_service)

        async def _search_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            query_embedding = await resolver.resolve_for_context(
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
        return self._apply_technical_term_boost_to_vector_results(query, merged)

    def _apply_technical_term_boost_to_vector_results(
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
        resolver = QueryEmbeddingResolver(self.embedding_service)

        async def _search_vector_for_context(
            context: SearchKBContext,
        ) -> tuple[SearchKBContext, str, list[ChunkSearchResult]]:
            query_embedding = await resolver.resolve_for_context(
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

    @staticmethod
    async def invalidate_kb_cache(kb_id: int) -> None:
        """Clear search cache for specified KB / 清除指定知识库的检索缓存。"""
        await invalidate_kb_cache_helper(kb_id)


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
