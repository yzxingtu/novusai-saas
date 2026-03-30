import pytest

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.ai.types import ChatMessage
from app.ai.context.ephemeral_rag import EphemeralRAGProvider, EphemeralRAGSource


def test_ephemeral_rag_build_query_terms_splits_cjk_sequences() -> None:
    provider = EphemeralRAGProvider()
    terms = provider._build_query_terms("请总结这份接口文档里的认证方式")

    assert "认证方式" in terms
    assert "接口文档" in terms


def test_ephemeral_rag_relevance_gap_filter_keeps_close_scores_only() -> None:
    provider = EphemeralRAGProvider()
    sources = [
        EphemeralRAGSource(doc_name="A", doc_id=1, score=0.9, snippet="a"),
        EphemeralRAGSource(doc_name="B", doc_id=2, score=0.72, snippet="b"),
        EphemeralRAGSource(doc_name="C", doc_id=3, score=0.2, snippet="c"),
    ]
    kept = provider._relevance_gap_filter(sources)

    assert [item.doc_name for item in kept] == ["A", "B"]


@pytest.mark.asyncio
async def test_ephemeral_rag_inject_loads_persisted_scope_documents() -> None:
    provider = EphemeralRAGProvider()
    messages = [
        ChatMessage(role="system", content="System prompt"),
        ChatMessage(role="user", content="请根据这些资料回答"),
    ]
    persisted_docs = [
        SimpleNamespace(
            id=11,
            title="Workspace Notes",
            content_kind="text",
            content="认证方式使用 OAuth 2.1 PKCE。",
            source_ref="workspace://notes/auth",
            scope_type="agent_workspace_scoped",
        )
    ]

    with (
        patch(
            "app.ai.context.ephemeral_rag.EphemeralDocumentService",
        ) as service_cls,
        patch.object(
            provider,
            "_retrieve_sources",
            AsyncMock(
                return_value=[
                    EphemeralRAGSource(
                        doc_name="Workspace Notes",
                        doc_id=11,
                        score=0.88,
                        snippet="认证方式使用 OAuth 2.1 PKCE。",
                    )
                ]
            ),
        ),
    ):
        service = service_cls.return_value
        service.upsert_refs = AsyncMock(return_value=[])
        service.list_runtime_documents = AsyncMock(return_value=persisted_docs)
        new_messages, sources = await provider.inject(
            messages=messages,
            ephemeral_rag_refs=[],
            db=object(),
            tenant_id=1,
            conversation_id=42,
            agent_id=9,
            user_id=7,
        )

    service.list_runtime_documents.assert_awaited_once_with(
        conversation_id=42,
        agent_id=9,
        user_id=7,
    )
    assert "[EPHEMERAL DOCUMENT CONTEXT]" in new_messages[0].content
    assert sources[0]["doc_id"] == 11
