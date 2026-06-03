"""
Test type: behavioral
中文: 覆盖混合检索的查询规范化、融合排序和 embedding 不可用降级行为。
EN: Covers hybrid retrieval query normalization, fusion ranking, and embedding-unavailable degradation.
Mock strategy:
中文: 仅用替身触发可选 embedding/vector 故障，关键词与融合逻辑走真实代码路径。
EN: External embedding/vector dependencies are faked only to force the optional outage; keyword/fusion behavior runs through real code paths.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.rag.retriever import ChunkSearchResult, HybridRetriever, KeywordSearcher
from app.ai.rag.retriever_cache import build_search_cache_key
from app.ai.rag.retriever_search import RetrieverSearchExecutor
from app.ai.rag.retriever_types import SearchKBContext
from app.core.i18n import _
from app.exceptions import BusinessException


class _UnavailableEmbeddingService:
    async def generate_embedding(
        self, *, text: str, knowledge_base: object
    ) -> list[float]:
        _ignored_inputs = (text, knowledge_base)
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
                content="知识库系统支持文档上传、自动分块、向量化存储，实现 RAG 检索增强生成。",
                score=0.64,
                raw_score=0.64,
                document_name="test_doc.txt",
                document_id=5,
                chunk_index=2,
                knowledge_base_id=1,
                recall_sources=["keyword"],
            )
        ]


class _CacheContext:
    def __init__(self, kb_id: int):
        self.kb_id = kb_id

    def cache_signature(self) -> str:
        return f"{self.kb_id}:1.0:8:1536"


def test_keyword_searcher_extracts_technical_terms() -> None:
    searcher = KeywordSearcher(db=None)  # type: ignore[arg-type]

    terms = searcher._extract_exact_terms(
        '请对比 "OAuth 2.1" 与 auth.user-login API 的差异，并关注 workflow_submit_form_v2'
    )

    assert "OAuth 2.1" in terms
    assert "auth.user-login" in terms
    assert "workflow_submit_form_v2" in terms


def test_keyword_searcher_technical_term_boost_prefers_exact_identifier() -> None:
    searcher = KeywordSearcher(db=None)  # type: ignore[arg-type]

    boost = searcher._technical_term_boost(
        query="请解释 auth.user-login 的回调流程",
        content="这里记录了 auth.user-login 的完整回调流程。",
        metadata={"heading": "登录 API"},
        document_name="user-auth.md",
    )

    assert boost > 0


def test_hybrid_retriever_vector_results_get_technical_term_boost() -> None:
    hr = HybridRetriever(db=MagicMock(), tenant_id=1)
    results = [
        ChunkSearchResult(
            chunk_id=1, content="generic text", score=0.55, document_name="a.md"
        ),
        ChunkSearchResult(
            chunk_id=2,
            content="See auth.user-login for details.",
            score=0.52,
            document_name="b.md",
        ),
    ]
    out = hr._apply_technical_term_boost_to_vector_results(
        "auth.user-login callback",
        results,
    )
    assert out[0].chunk_id == 2
    assert out[0].score > out[1].score


def test_hybrid_retriever_relevance_gap_filter_stops_after_large_drop() -> None:
    results = [
        ChunkSearchResult(chunk_id=1, content="a", score=0.95),
        ChunkSearchResult(chunk_id=2, content="b", score=0.79),
        ChunkSearchResult(chunk_id=3, content="c", score=0.31),
    ]

    kept = HybridRetriever._relevance_gap_filter(results, max_drop=0.32)

    assert [item.chunk_id for item in kept] == [1, 2]


def test_hybrid_retriever_normalizes_instruction_wrapped_kb_query() -> None:
    normalized = HybridRetriever._normalize_retrieval_query(
        "根据内部知识库，NovusAI 的核心功能有哪些？请只基于内部知识回答。"
    )

    assert normalized == "NovusAI 的核心功能有哪些"


def test_hybrid_retriever_keeps_plain_query_when_no_wrapper_present() -> None:
    normalized = HybridRetriever._normalize_retrieval_query("NovusAI 的核心功能有哪些")

    assert normalized == "NovusAI 的核心功能有哪些"


def test_hybrid_retriever_normalizes_multilingual_wrapper_suffix() -> None:
    normalized = HybridRetriever._normalize_retrieval_query(
        "Please answer based on the internal knowledge base: What integrations does NovusAI support? Please do not use external sources."
    )

    assert normalized == "What integrations does NovusAI support"


def test_hybrid_retriever_does_not_strip_core_question_with_kb_wording() -> None:
    normalized = HybridRetriever._normalize_retrieval_query(
        "内部知识库绑定失败的根因是什么？"
    )

    assert normalized == "内部知识库绑定失败的根因是什么"


def test_search_cache_key_is_tenant_scoped_for_hook_mutated_results() -> None:
    contexts = [_CacheContext(101)]

    tenant_a_key = build_search_cache_key(
        contexts,
        "same query",
        "hybrid",
        5,
        0.5,
        tenant_id=7,
        rewrite_strategy="none",
        reranker_enabled=False,
    )
    tenant_b_key = build_search_cache_key(
        contexts,
        "same query",
        "hybrid",
        5,
        0.5,
        tenant_id=8,
        rewrite_strategy="none",
        reranker_enabled=False,
    )
    tenant_a_key_again = build_search_cache_key(
        contexts,
        "same query",
        "hybrid",
        5,
        0.5,
        tenant_id=7,
        rewrite_strategy="none",
        reranker_enabled=False,
    )

    assert tenant_a_key != tenant_b_key
    assert tenant_a_key == tenant_a_key_again


@pytest.mark.asyncio
async def test_hybrid_search_falls_back_to_keyword_when_embedding_api_key_unavailable_for_conversation_2412() -> (
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
    assert results[0].document_name == "test_doc.txt"
    assert results[0].knowledge_base_id == 1
    assert results[0].recall_sources == ["keyword"]
    assert keyword_searcher.calls == [
        {
            "kb_ids": [1],
            "query": "看看绑定的知识库有什么内容",
            "limit": 10,
        }
    ]


@pytest.mark.asyncio
async def test_vector_search_keeps_embedding_api_key_error_fail_closed() -> None:
    executor = RetrieverSearchExecutor(
        embedding_service=_UnavailableEmbeddingService(),  # type: ignore[arg-type]
        vector_searcher=_UnexpectedVectorSearcher(),  # type: ignore[arg-type]
        keyword_searcher=_KeywordResultSearcher(),  # type: ignore[arg-type]
    )
    context = SearchKBContext(
        knowledge_base=SimpleNamespace(
            id=1,
            embedding_model_id=5,
            embedding_dimensions=1536,
        )
    )

    with pytest.raises(BusinessException, match="没有可用的 API Key"):
        await executor.search(
            [context],
            "看看绑定的知识库有什么内容",
            top_k=5,
            score_threshold=0.5,
            mode="vector",
        )
