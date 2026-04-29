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
        if not enabled or not kb_ids:
            return RAGContextContribution(messages=list(messages))

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
        if rag_sources:
            kinds.append("formal_kb")
        return RAGContextContribution(
            messages=injected_messages,
            rag_sources=rag_sources,
            rag_source_kinds=kinds,
            kb_injected=bool(rag_sources),
        )


__all__ = ["RAGContributor", "RAGContextContribution"]
