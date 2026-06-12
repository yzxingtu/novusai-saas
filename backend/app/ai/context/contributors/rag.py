"""
RAG context contributor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.types import ChatMessage


@dataclass
class RAGContextContribution:
    messages: list[ChatMessage]
    rag_sources: list[dict[str, Any]] | None = None
    rag_source_kinds: list[str] = field(default_factory=list)
    kb_injected: bool = False
    rag_attempted: bool = False
    rag_retrieval_status: str | None = None
    rag_no_hit_reason: str | None = None
    rag_matched_chunk_count: int = 0


class RAGContributor:
    async def contribute(
        self,
        *,
        db: Any,
        agent: Any,
        tenant_id: int,
        messages: list[ChatMessage],
        kb_ids: list[int],
        rag_config: dict[str, Any] | None,
        kb_weights: dict[int, float] | None,
        enabled: bool,
    ) -> RAGContextContribution:
        if not kb_ids:
            return RAGContextContribution(
                messages=list(messages),
                rag_retrieval_status="no_effective_knowledge_base",
            )
        if not enabled:
            return RAGContextContribution(
                messages=list(messages),
                rag_retrieval_status="skipped_tool_managed",
            )

        from app.ai.rag_injector import inject_rag_context

        injected_messages, rag_sources = await inject_rag_context(
            db,
            agent,
            list(messages),
            tenant_id,
            kb_ids=kb_ids,
            rag_config=rag_config or None,
            kb_weights=kb_weights,
        )
        kinds: list[str] = []
        source_count = len(rag_sources or [])
        if rag_sources:
            kinds.append("formal_kb")
        return RAGContextContribution(
            messages=injected_messages,
            rag_sources=rag_sources,
            rag_source_kinds=kinds,
            kb_injected=bool(rag_sources),
            rag_attempted=True,
            rag_retrieval_status="injected" if rag_sources else "attempted_no_results",
            rag_no_hit_reason=None if rag_sources else "retrieval_returned_no_sources",
            rag_matched_chunk_count=source_count,
        )


__all__ = ["RAGContributor", "RAGContextContribution"]
