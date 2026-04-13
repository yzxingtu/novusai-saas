"""
Vector retrieval helpers for RAG.
"""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedding import EmbeddingService
from app.ai.rag.retriever_types import ChunkSearchResult
from app.core.logging import LogManager
from app.enums.knowledge_base import DocumentStatusEnum
from app.models.ai.document_chunk import DocumentChunk
from app.models.ai.knowledge_base import KnowledgeBase
from app.models.ai.knowledge_document import KnowledgeDocument

logger = LogManager.get_logger("ai.rag.retriever")


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


__all__ = ["VectorSearcher"]
