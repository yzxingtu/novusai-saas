from unittest.mock import MagicMock

from app.ai.rag.retriever import ChunkSearchResult, HybridRetriever, KeywordSearcher


def test_keyword_searcher_extracts_technical_terms() -> None:
    searcher = KeywordSearcher(db=None)  # type: ignore[arg-type]

    terms = searcher._extract_exact_terms(
        '请对比 "OAuth 2.1" 与 auth.user-login API 的差异，并关注 ui_submit_form_v2'
    )

    assert "OAuth 2.1" in terms
    assert "auth.user-login" in terms
    assert "ui_submit_form_v2" in terms


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
        ChunkSearchResult(chunk_id=1, content="generic text", score=0.55, document_name="a.md"),
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
    normalized = HybridRetriever._normalize_retrieval_query(
        "NovusAI 的核心功能有哪些"
    )

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
