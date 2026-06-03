"""
Test type: behavioral
Scope: RAGContributor observable injection diagnostics.
Mock strategy: only the retrieval transport seam is patched; the contributor's
diagnostic decision logic runs real and must not report KB injection without
retrieval evidence.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.context.contributors.rag import RAGContributor
from app.ai.types import ChatMessage


@pytest.mark.asyncio
async def test_rag_contributor_does_not_mark_kb_injected_without_sources() -> None:
    contributor = RAGContributor()
    messages = [ChatMessage(role="user", content="查询知识库")]

    with patch(
        "app.ai.rag_injector.inject_rag_context",
        new_callable=AsyncMock,
        return_value=(messages, None),
    ):
        contribution = await contributor.contribute(
            db=object(),
            agent=object(),
            tenant_id=1,
            messages=messages,
            kb_ids=[101],
            rag_config={},
            kb_weights=None,
            enabled=True,
        )

    assert contribution.messages == messages
    assert contribution.rag_sources is None
    assert contribution.rag_source_kinds == []
    assert contribution.kb_injected is False
    assert contribution.rag_attempted is True
    assert contribution.rag_retrieval_status == "attempted_no_results"
    assert contribution.rag_no_hit_reason == "retrieval_returned_no_sources"
    assert contribution.rag_matched_chunk_count == 0


@pytest.mark.asyncio
async def test_rag_contributor_reports_skipped_status_without_fabricating_sources() -> (
    None
):
    contributor = RAGContributor()
    messages = [ChatMessage(role="user", content="普通问候")]

    contribution = await contributor.contribute(
        db=object(),
        agent=object(),
        tenant_id=1,
        messages=messages,
        kb_ids=[101],
        rag_config={},
        kb_weights=None,
        enabled=False,
    )

    assert contribution.messages == messages
    assert contribution.rag_sources is None
    assert contribution.kb_injected is False
    assert contribution.rag_attempted is False
    assert contribution.rag_retrieval_status == "skipped_not_knowledge_intent"
