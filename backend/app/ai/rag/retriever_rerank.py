"""
Rerank helpers for retrieval.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.retriever_types import ChunkSearchResult


async def rerank_results(
    *,
    db: AsyncSession,
    tenant_id: int | None,
    query: str,
    results: list[ChunkSearchResult],
    top_k: int,
    llm_model: str | None,
) -> list[ChunkSearchResult]:
    if not results:
        return results

    from app.ai.rag.reranker import LLMReranker

    reranker = LLMReranker(db, tenant_id, llm_model)
    return await reranker.rerank(query, results, top_k=top_k)


__all__ = ["rerank_results"]
