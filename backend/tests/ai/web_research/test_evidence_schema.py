"""
Test type: structural
Scope: provider-neutral WebResearch evidence schema and deterministic quality.
Mock strategy: no mocks; tests pure DTO and normalization helpers.
"""

from app.ai.web_research import (
    PageEvidence,
    SearchEvidenceItem,
    SearchResultSet,
    WebResearchRunOptions,
    answer_source_for_quality,
    build_web_research_evidence,
    normalize_page_evidence,
    normalize_search_item,
    select_fetch_candidates,
)


def test_public_facade_exports_core_contracts() -> None:
    options = WebResearchRunOptions(pipeline_id="pipeline-structural")
    assert options.max_fetches == 3
    assert PageEvidence.__name__ == "PageEvidence"
    assert SearchEvidenceItem.__name__ == "SearchEvidenceItem"


def test_page_quality_prefers_body_then_summary_then_none() -> None:
    body_page = normalize_page_evidence(
        url=" https://example.com/body ",
        status="completed",
        title=" Body ",
        body_text=" Full body ",
        summary=" Summary ",
        description="",
        provider="fetch",
    )
    summary_page = normalize_page_evidence(
        url="https://example.com/summary",
        status="completed",
        title="Summary",
        body_text="",
        summary=" Condensed source ",
        description="",
        provider="fetch",
    )
    blocked_page = normalize_page_evidence(
        url="https://example.com/blocked",
        status="blocked",
        title="Blocked",
        body_text="Body that must not count",
        summary="Summary that must not count",
        description="",
        provider="fetch",
        failure_kind="robots_blocked",
    )

    assert body_page.answer_quality == "body"
    assert body_page.url == "https://example.com/body"
    assert summary_page.answer_quality == "summary"
    assert blocked_page.answer_quality == "none"


def test_search_snippet_quality_is_explicit_opt_in() -> None:
    default_item = normalize_search_item(
        title="Result",
        url="https://example.com/default",
        snippet="Search snippet",
        rank=1,
        provider="search",
    )
    snippet_item = normalize_search_item(
        title="Result",
        url="https://example.com/snippet",
        snippet="Search snippet",
        rank=2,
        provider="search",
        allow_snippet_quality=True,
    )

    assert default_item.answer_quality == "none"
    assert snippet_item.answer_quality == "snippet"
    assert answer_source_for_quality("snippet") == "search_snippet"


def test_required_fetch_suppresses_snippet_answer_quality() -> None:
    search_results = SearchResultSet(
        query="llm ranking",
        provider="search",
        items=[
            normalize_search_item(
                title="Snippet",
                url="https://example.com/snippet",
                snippet="Snippet evidence",
                rank=1,
                provider="search",
                allow_snippet_quality=True,
            )
        ],
    )

    evidence = build_web_research_evidence(
        query="llm ranking",
        search_results=search_results,
        fetched_pages=[],
        fetch_provider="fetch",
        pipeline_id="pipeline-require-fetch",
        candidate_urls=["https://example.com/snippet"],
        require_fetch=True,
    )

    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "fetch_not_attempted"
    assert evidence.citations == []
    assert evidence.diagnostics.answer_source == "none"


def test_fetch_candidate_selection_filters_unsafe_and_duplicate_urls() -> None:
    search_results = SearchResultSet(
        query="llm ranking",
        provider="search",
        items=[
            normalize_search_item(
                title="Second",
                url="https://example.com/second",
                snippet="",
                rank=2,
                provider="search",
            ),
            normalize_search_item(
                title="Primary",
                url="https://example.com/primary",
                snippet="",
                rank=1,
                provider="search",
            ),
            normalize_search_item(
                title="Duplicate",
                url="https://example.com/primary",
                snippet="",
                rank=3,
                provider="search",
            ),
            normalize_search_item(
                title="Unsafe",
                url="javascript:alert(1)",
                snippet="",
                rank=4,
                provider="search",
            ),
        ],
    )

    selection = select_fetch_candidates(
        search_results,
        max_fetches=1,
        require_fetch=True,
    )

    assert selection.candidate_urls == [
        "https://example.com/primary",
        "https://example.com/second",
    ]
    assert selection.selected_urls == ["https://example.com/primary"]
    assert [(item.url, item.reason) for item in selection.skipped] == [
        ("https://example.com/primary", "duplicate_url"),
        ("javascript:alert(1)", "unsupported_scheme"),
    ]


def test_evidence_serializes_canonical_diagnostics() -> None:
    search_results = SearchResultSet(
        query="llm ranking",
        provider="builtin-search",
        items=[
            normalize_search_item(
                title="Ranking",
                url="https://example.com/ranking",
                snippet="Ranking snippet",
                rank=1,
                provider="builtin-search",
            )
        ],
    )
    page = normalize_page_evidence(
        url="https://example.com/ranking",
        status="completed",
        title="Ranking page",
        body_text="Detailed ranking body",
        summary="Ranking summary",
        description="",
        provider="builtin-fetch",
    )

    evidence = build_web_research_evidence(
        query="llm ranking",
        search_results=search_results,
        fetched_pages=[page],
        fetch_provider="builtin-fetch",
        pipeline_id="pipeline-1",
        candidate_urls=["https://example.com/ranking"],
        require_fetch=True,
    )
    payload = evidence.to_dict()

    assert payload["status"] == "completed"
    assert payload["answer_quality"] == "body"
    assert payload["diagnostics"]["pipeline_id"] == "pipeline-1"
    assert payload["diagnostics"]["answer_source"] == "fetched_body"
    assert payload["diagnostics"]["candidate_urls"] == ["https://example.com/ranking"]
    assert payload["citations"][0]["source"] == "page"


def test_evidence_requires_configured_cross_checked_source_count() -> None:
    search_results = SearchResultSet(
        query="今日ai新闻查一下",
        provider="builtin-search",
        items=[
            normalize_search_item(
                title="OpenAI news",
                url="https://www.reuters.com/technology/ai/openai-news",
                snippet="OpenAI AI news",
                rank=1,
                provider="builtin-search",
            )
        ],
        diagnostics={"minimum_relevant_sources": 2},
    )
    page = normalize_page_evidence(
        url="https://www.reuters.com/technology/ai/openai-news",
        status="completed",
        title="OpenAI news",
        body_text="OpenAI announced an AI update.",
        summary="OpenAI announced an AI update.",
        description="",
        provider="builtin-fetch",
        relevance_status="relevant",
        relevance_profile="ai_news",
    )

    evidence = build_web_research_evidence(
        query="今日ai新闻查一下",
        search_results=search_results,
        fetched_pages=[page],
        fetch_provider="builtin-fetch",
        pipeline_id="pipeline-cross-check",
        candidate_urls=["https://www.reuters.com/technology/ai/openai-news"],
        require_fetch=True,
        raw_diagnostics={"minimum_relevant_sources": 2},
    )

    assert evidence.status == "partial"
    assert evidence.answer_quality == "none"
    assert evidence.failure_kind == "insufficient_cross_checked_sources"
    assert evidence.diagnostics.answer_source == "none"
    assert evidence.diagnostics.fetched_urls == [
        "https://www.reuters.com/technology/ai/openai-news"
    ]
    assert evidence.citations == []
    assert evidence.diagnostics.raw["accepted_source_count"] == 1
