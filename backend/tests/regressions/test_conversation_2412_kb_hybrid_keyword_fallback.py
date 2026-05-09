"""
Test type: behavioral
Regression for: conversation_id=2412
Original symptom: conversation 2412 was a knowledge_query with bound KB id=1,
but RAG produced rag_source_count=0 / retrieval skipped, and the assistant
claimed it could not inspect the bound knowledge base.
Scope: hybrid RAG retrieval fallback when query embedding is unavailable.
Real dependencies: RetrieverSearchExecutor hybrid search and RRF/fallback control
flow.
Mocked dependencies: embedding provider unavailable fixture plus vector/keyword
search transport fakes only.
Why this is not self-fulfilling: no LLM response is mocked; the test asserts
that real hybrid retrieval keeps keyword evidence when the vector branch raises
the same no-API-key class of failure.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.rag.retriever import ChunkSearchResult
from app.ai.rag.retriever_search import RetrieverSearchExecutor
from app.ai.rag.retriever_types import SearchKBContext
from app.core.i18n import _
from app.exceptions import BusinessException


class _UnavailableEmbeddingService:
    async def generate_embedding(
        self, *, text: str, knowledge_base: object
    ) -> list[float]:
        _unused = text, knowledge_base
        raise BusinessException(message=_("ai.no_api_key"))


class _UnexpectedVectorSearcher:
    async def search(self, **_kwargs: object) -> list[ChunkSearchResult]:
        raise AssertionError(
            "vector search should not run when embedding is unavailable"
        )


class _KeywordResultSearcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        kb_ids: list[int],
        query: str,
        limit: int,
    ) -> list[ChunkSearchResult]:
        self.calls.append({"kb_ids": kb_ids, "query": query, "limit": limit})
        return [
            ChunkSearchResult(
                chunk_id=7,
                content=(
                    "知识库系统支持文档上传、自动分块、向量化存储，实现 RAG 检索增强生成。"
                ),
                score=0.64,
                raw_score=0.64,
                document_name="test_doc.txt",
                document_id=5,
                chunk_index=2,
                knowledge_base_id=1,
                recall_sources=["keyword"],
            )
        ]


@pytest.mark.asyncio
async def test_conversation_2412_hybrid_kb_retrieval_keeps_keyword_evidence_when_embedding_key_missing() -> (
    None
):
    keyword_searcher = _KeywordResultSearcher()
    executor = RetrieverSearchExecutor(
        embedding_service=_UnavailableEmbeddingService(),  # type: ignore[arg-type]
        vector_searcher=_UnexpectedVectorSearcher(),  # type: ignore[arg-type]
        keyword_searcher=keyword_searcher,  # type: ignore[arg-type]
    )
    context = SearchKBContext(
        knowledge_base=SimpleNamespace(
            id=1,
            embedding_model_id=5,
            embedding_dimensions=1536,
        )
    )

    results = await executor.search(
        [context],
        "看看绑定的知识库有什么内容",
        top_k=5,
        score_threshold=0.5,
        mode="hybrid",
    )

    assert [item.chunk_id for item in results] == [7]
    assert results[0].knowledge_base_id == 1
    assert results[0].document_name == "test_doc.txt"
    assert results[0].recall_sources == ["keyword"]
    assert keyword_searcher.calls == [
        {
            "kb_ids": [1],
            "query": "看看绑定的知识库有什么内容",
            "limit": 10,
        }
    ]
