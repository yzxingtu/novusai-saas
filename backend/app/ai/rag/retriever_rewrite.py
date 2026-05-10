"""
Query rewrite helpers for retrieval.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


async def rewrite_queries(
    *,
    db: AsyncSession,
    tenant_id: int | None,
    query: str,
    rewrite_strategy: str,
) -> list[str]:
    from app.ai.rag.query_rewriter import get_rewriter

    rewriter = get_rewriter(rewrite_strategy, db, tenant_id)
    return await rewriter.rewrite(query)


__all__ = ["rewrite_queries"]
