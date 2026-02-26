"""
混合检索引擎

支持向量检索、关键词检索、混合检索（RRF 融合排序）
内置 Redis 检索结果缓存
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict

from sqlalchemy import and_, select, func, text, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedding import EmbeddingService
from app.core.logging import LogManager
from app.enums.knowledge_base import DocumentStatusEnum, SearchModeEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument

logger = LogManager.get_logger("ai.rag.retriever")

# RRF 融合常数
RRF_K = 60

# Redis 检索缓存 TTL（5 分钟）
SEARCH_CACHE_TTL = 300
SEARCH_CACHE_PREFIX = "kb:search:"


@dataclass
class ChunkSearchResult:
    """检索结果项"""

    chunk_id: int
    content: str
    score: float
    metadata: dict | None = None
    document_name: str = ""
    document_id: int = 0
    chunk_index: int = 0
    highlight: str | None = None

    def to_dict(self) -> dict:
        """for serialization"""
        return asdict(self)


class VectorSearcher:
    """
    向量检索器

    使用 pgvector <=> 余弦距离检索最相似分块
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
    ) -> list[ChunkSearchResult]:
        """
        pgvector 余弦距离检索

        Args:
            kb_ids: 知识库 ID 列表
            query: 查询文本
            knowledge_base: 用于获取 Embedding 模型的知识库
            limit: 返回数量
            score_threshold: 相似度阈值

        Returns:
            检索结果列表（按相似度降序）
        """
        query_embedding = await self.embedding_service.generate_embedding(
            text=query, knowledge_base=knowledge_base,
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
            except Exception:
                pass

            results.append(ChunkSearchResult(
                chunk_id=chunk.id,
                content=chunk.content,
                score=round(1.0 - distance, 4),
                metadata=chunk.metadata_,
                document_name=doc_name,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
            ))

        return results


class KeywordSearcher:
    """
    关键词检索器

    使用 PostgreSQL tsvector + plainto_tsquery('simple', ...) 全文检索
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        kb_ids: list[int],
        query: str,
        limit: int = 10,
    ) -> list[ChunkSearchResult]:
        """
        tsvector 全文检索

        使用 'simple' 配置跨语言兼容，不依赖中文分词插件

        Args:
            kb_ids: 知识库 ID 列表
            query: 查询文本
            limit: 返回数量

        Returns:
            检索结果列表（按 ts_rank 降序）
        """
        # 使用 raw SQL 因为 SQLAlchemy 对 tsvector 支持有限
        sql = text("""
            SELECT
                dc.id,
                dc.content,
                dc.document_id,
                dc.chunk_index,
                dc.metadata AS chunk_metadata,
                kd.file_name AS document_name,
                ts_rank(dc.content_tsv, plainto_tsquery('simple', :query)) AS rank
            FROM document_chunks dc
            JOIN knowledge_documents kd
                ON kd.id = dc.document_id
                AND kd.is_deleted = false
                AND kd.status = 'completed'
            WHERE dc.knowledge_base_id = ANY(:kb_ids)
                AND dc.is_deleted = false
                AND dc.content_tsv @@ plainto_tsquery('simple', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await self.db.execute(sql, {
            "query": query,
            "kb_ids": kb_ids,
            "limit": limit,
        })
        rows = result.fetchall()

        results: list[ChunkSearchResult] = []
        for row in rows:
            results.append(ChunkSearchResult(
                chunk_id=row[0],
                content=row[1],
                score=round(float(row[6]), 4),
                metadata=row[4],
                document_name=row[5] or "",
                document_id=row[2],
                chunk_index=row[3],
            ))

        return results


class HybridRetriever:
    """
    混合检索器

    支持三种检索模式：
    - hybrid: 向量 + 关键词，RRF 融合排序
    - vector: 纯向量检索
    - keyword: 纯关键词检索

    内置 Redis 缓存（TTL 5 分钟）
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        self.embedding_service = EmbeddingService(db, tenant_id)
        self.vector_searcher = VectorSearcher(db, self.embedding_service)
        self.keyword_searcher = KeywordSearcher(db)

    async def search(
        self,
        knowledge_base: KnowledgeBase,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.5,
        search_mode: str | None = None,
        kb_ids: list[int] | None = None,
        rewrite_strategy: str = "none",
        reranker_enabled: bool = False,
        llm_model: str | None = None,
    ) -> list[ChunkSearchResult]:
        """
        混合检索（支持查询改写和重排序）

        Args:
            knowledge_base: 知识库对象（用于获取 Embedding 模型和默认配置）
            query: 查询文本
            top_k: 返回数量
            score_threshold: 相似度阈值
            search_mode: 检索模式 (hybrid/vector/keyword)，None 时使用知识库配置
            kb_ids: 知识库 ID 列表，None 时使用当前知识库
            rewrite_strategy: 查询改写策略 (none/multi/hyde)
            reranker_enabled: 是否启用 LLM 重排序
            llm_model: 改写/重排序使用的 LLM 模型代码

        Returns:
            按综合得分降序的检索结果
        """
        mode = search_mode or knowledge_base.search_mode or "hybrid"
        target_kb_ids = kb_ids or [knowledge_base.id]

        # ── Hook: BEFORE_KB_SEARCH — 插件可修改 query/top_k/kb_ids ──
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

        # 尝试从 Redis 缓存读取
        cache_key = self._build_cache_key(
            target_kb_ids, query, mode, top_k, score_threshold,
            rewrite_strategy=rewrite_strategy, reranker_enabled=reranker_enabled,
        )
        cached = await self._get_cache(cache_key)
        if cached is not None:
            logger.info("Search cache hit: %s", cache_key)
            # 缓存命中也需过 AFTER hook（插件可能做权限过滤/脱敏）
            if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
                hook_ctx = await hook_registry.trigger(
                    HookPoint.AFTER_KB_SEARCH,
                    tenant_id=self.tenant_id,
                    query=query,
                    results=cached,
                )
                cached = hook_ctx.get("results", cached)
            return cached

        # 1. 查询改写
        from app.ai.rag.query_rewriter import get_rewriter
        rewriter = get_rewriter(rewrite_strategy, self.db, self.tenant_id, llm_model)
        queries = await rewriter.rewrite(query)

        # 2. 对每个改写查询执行检索并合并
        all_results: list[ChunkSearchResult] = []
        seen_chunk_ids: set[int] = set()

        for q in queries:
            if mode == SearchModeEnum.VECTOR.value:
                batch = await self._vector_search(
                    target_kb_ids, q, knowledge_base, top_k, score_threshold,
                )
            elif mode == SearchModeEnum.KEYWORD.value:
                batch = await self._keyword_search(
                    target_kb_ids, q, top_k,
                )
            else:
                batch = await self._hybrid_search(
                    target_kb_ids, q, knowledge_base, top_k, score_threshold,
                )

            # 去重合并
            for r in batch:
                if r.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(r.chunk_id)
                    all_results.append(r)

        # 按分数降序排序后截取
        all_results.sort(key=lambda x: x.score, reverse=True)
        results = all_results[:top_k * 2] if reranker_enabled else all_results[:top_k]

        # 后融合质量门控：过滤归一化分数过低的结果（hybrid 模式 RRF 归一化后适用）
        if mode != SearchModeEnum.VECTOR.value and results:
            min_score = 0.15
            filtered = [r for r in results if r.score >= min_score]
            if filtered:
                results = filtered

        # 3. LLM 重排序（可选）
        if reranker_enabled and results:
            from app.ai.rag.reranker import LLMReranker
            reranker = LLMReranker(self.db, self.tenant_id, llm_model)
            results = await reranker.rerank(query, results, top_k=top_k)

        # ── Hook: AFTER_KB_SEARCH — 插件可过滤/重排结果 ──
        if hook_registry.has_hooks(HookPoint.AFTER_KB_SEARCH):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_KB_SEARCH,
                tenant_id=self.tenant_id,
                query=query,
                results=results,
            )
            results = hook_ctx.get("results", results)

        # 写入 Redis 缓存
        await self._set_cache(cache_key, results)

        logger.info(
            "Search: mode=%s, kb_ids=%s, query_len=%d, results=%d, rewrite=%s, rerank=%s",
            mode, target_kb_ids, len(query), len(results),
            rewrite_strategy, reranker_enabled,
        )

        return results

    async def _vector_search(
        self,
        kb_ids: list[int],
        query: str,
        knowledge_base: KnowledgeBase,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        """纯向量检索"""
        return await self.vector_searcher.search(
            kb_ids=kb_ids,
            query=query,
            knowledge_base=knowledge_base,
            limit=top_k,
            score_threshold=score_threshold,
        )

    async def _keyword_search(
        self,
        kb_ids: list[int],
        query: str,
        top_k: int,
    ) -> list[ChunkSearchResult]:
        """纯关键词检索"""
        return await self.keyword_searcher.search(
            kb_ids=kb_ids,
            query=query,
            limit=top_k,
        )

    async def _hybrid_search(
        self,
        kb_ids: list[int],
        query: str,
        knowledge_base: KnowledgeBase,
        top_k: int,
        score_threshold: float,
    ) -> list[ChunkSearchResult]:
        """
        混合检索 + RRF 融合

        两路各取 top_k*2，通过 Reciprocal Rank Fusion 融合排序
        RRF 公式: score(d) = Σ 1/(k + rank_i(d)), k=60
        """
        expand_limit = top_k * 2

        # 并行执行两路检索
        import asyncio

        vector_results, keyword_results = await asyncio.gather(
            self.vector_searcher.search(
                kb_ids=kb_ids,
                query=query,
                knowledge_base=knowledge_base,
                limit=expand_limit,
                score_threshold=score_threshold,
            ),
            self.keyword_searcher.search(
                kb_ids=kb_ids,
                query=query,
                limit=expand_limit,
            ),
        )

        # RRF 融合
        return self._rrf_merge(vector_results, keyword_results, top_k)

    @staticmethod
    def _rrf_merge(
        vector_results: list[ChunkSearchResult],
        keyword_results: list[ChunkSearchResult],
        top_k: int,
    ) -> list[ChunkSearchResult]:
        """
        Reciprocal Rank Fusion

        score(d) = Σ 1/(k + rank_i(d)), k=60

        同一 chunk_id 只保留一次，合并得分。
        最终分数归一化到 [0, 1]（除以理论最大值 2/(k+1)）。
        """
        # chunk_id -> (rrf_score, ChunkSearchResult)
        score_map: dict[int, tuple[float, ChunkSearchResult]] = {}

        # 向量检索结果排名
        for rank, result in enumerate(vector_results, start=1):
            rrf = 1.0 / (RRF_K + rank)
            if result.chunk_id in score_map:
                old_score, old_result = score_map[result.chunk_id]
                score_map[result.chunk_id] = (old_score + rrf, old_result)
            else:
                score_map[result.chunk_id] = (rrf, result)

        # 关键词检索结果排名
        for rank, result in enumerate(keyword_results, start=1):
            rrf = 1.0 / (RRF_K + rank)
            if result.chunk_id in score_map:
                old_score, old_result = score_map[result.chunk_id]
                score_map[result.chunk_id] = (old_score + rrf, old_result)
            else:
                score_map[result.chunk_id] = (rrf, result)

        # 按 RRF 得分降序排序
        sorted_items = sorted(score_map.values(), key=lambda x: x[0], reverse=True)

        # 归一化：RRF 理论最大值 = num_lists / (k + 1)
        num_lists = 2  # vector + keyword
        rrf_max = num_lists / (RRF_K + 1)

        results: list[ChunkSearchResult] = []
        for rrf_score, chunk_result in sorted_items[:top_k]:
            normalized = min(rrf_score / rrf_max, 1.0) if rrf_max > 0 else 0.0
            chunk_result.score = round(normalized, 4)
            results.append(chunk_result)

        return results

    # ==================== Redis 缓存 ====================

    @staticmethod
    def _build_cache_key(
        kb_ids: list[int],
        query: str,
        mode: str,
        top_k: int,
        score_threshold: float,
        rewrite_strategy: str = "none",
        reranker_enabled: bool = False,
    ) -> str:
        """生成检索缓存 Key（含 kb_ids 前缀，支持按 KB 失效）"""
        sorted_ids = sorted(kb_ids)
        kb_prefix = "_".join(str(i) for i in sorted_ids)
        raw = f"{sorted_ids}:{query}:{mode}:{top_k}:{score_threshold}:{rewrite_strategy}:{reranker_enabled}"
        digest = hashlib.md5(raw.encode()).hexdigest()
        return f"{SEARCH_CACHE_PREFIX}{kb_prefix}:{digest}"

    @staticmethod
    async def _get_cache(key: str) -> list[ChunkSearchResult] | None:
        """从 Redis 读取缓存"""
        try:
            from app.core.redis import cache_get
            data = await cache_get(key)
            if data is None:
                return None
            return [
                ChunkSearchResult(**item)
                for item in data
            ]
        except Exception:
            return None

    @staticmethod
    async def _set_cache(key: str, results: list[ChunkSearchResult]) -> None:
        """写入 Redis 缓存"""
        try:
            from app.core.redis import cache_set
            data = [r.to_dict() for r in results]
            await cache_set(key, data, ttl=SEARCH_CACHE_TTL)
        except Exception:
            pass

    @staticmethod
    async def invalidate_kb_cache(kb_id: int) -> None:
        """
        清除指定知识库的检索缓存

        文档变更时调用，通过前缀扫描仅删除包含该 kb_id 的缓存
        """
        try:
            from app.core.redis import RedisManager
            client = await RedisManager.get_client()
            # 匹配所有包含该 kb_id 的缓存 key
            # key 格式: kb:search:{kb_prefix}:{hash}，kb_prefix 如 "1" 或 "1_3_5"
            # 用 *{kb_id}* 匹配，可能误删含相似数字的 key，但 TTL 仅 5 分钟影响极小
            patterns = [
                f"{SEARCH_CACHE_PREFIX}{kb_id}:*",       # 单 KB: kb:search:5:xxx
                f"{SEARCH_CACHE_PREFIX}*_{kb_id}:*",     # 多 KB 尾部: kb:search:1_5:xxx
                f"{SEARCH_CACHE_PREFIX}{kb_id}_*",       # 多 KB 头部: kb:search:5_8:xxx
                f"{SEARCH_CACHE_PREFIX}*_{kb_id}_*",     # 多 KB 中间: kb:search:1_5_8:xxx
            ]
            for pattern in patterns:
                async for key in client.scan_iter(match=pattern, count=100):
                    await client.delete(key)
        except Exception:
            pass


# 向后兼容：保留 VectorRetriever 别名
VectorRetriever = HybridRetriever


__all__ = [
    "ChunkSearchResult",
    "VectorSearcher",
    "KeywordSearcher",
    "HybridRetriever",
    "VectorRetriever",
]
