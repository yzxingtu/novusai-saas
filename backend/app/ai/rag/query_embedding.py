"""
Query embedding helpers for retriever pipeline.
"""

from __future__ import annotations

from typing import Any


class QueryEmbeddingResolver:
    """Reuse query embeddings across KB contexts with the same signature."""

    def __init__(self, embedding_service: Any):
        self.embedding_service = embedding_service
        self._cache: dict[tuple[int, int], list[float]] = {}

    async def resolve_for_context(
        self,
        *,
        query: str,
        context: Any,
    ) -> list[float]:
        signature = tuple(context.embedding_signature)
        if signature not in self._cache:
            self._cache[signature] = await self.embedding_service.generate_embedding(
                text=query,
                knowledge_base=context.knowledge_base,
            )
        return self._cache[signature]


__all__ = ["QueryEmbeddingResolver"]
