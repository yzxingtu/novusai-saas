"""
Test type: behavioral
Scope: QA regression matrix for 2026 LLM leaderboard web-research query planning.
Mock strategy: no LLM, planner, search provider, tool executor, or runtime decision
layer is mocked. Tests exercise the real deterministic query-profile planner and
SearchResultSet normalization contracts only.
"""

import pytest

from app.ai.web_research import (
    SearchResultSet,
    apply_query_plan_to_search_results,
    build_web_research_query_plan,
    normalize_search_item,
)

TRUSTED_LEADERBOARD_URLS = [
    "https://artificialanalysis.ai/leaderboards/models",
    "https://lmarena.ai/leaderboard",
]


@pytest.mark.parametrize(
    ("query", "expected_profile"),
    [
        pytest.param("大模型排行榜 2026 水平排行", "llm_leaderboard", id="zh_rank"),
        pytest.param(
            "2026 LLM leaderboard by price and speed",
            "llm_leaderboard",
            id="en_price_speed",
        ),
        pytest.param(
            "AI model ranking context window latency TTFT",
            "llm_leaderboard",
            id="en_speed_metrics",
        ),
        pytest.param(
            "全球 AI 模型榜单 价格 速度",
            "llm_leaderboard",
            id="zh_price_speed",
        ),
        pytest.param("排行榜", "leaderboard", id="short_leaderboard_word_only"),
        pytest.param("2026 59.68 65.71 20.54", "generic", id="numeric_fragments_only"),
        pytest.param("猫", "generic", id="unrelated_short_word"),
        pytest.param("北京今天适合带伞吗", "generic", id="ordinary_search"),
    ],
)
def test_query_profile_matrix_for_leaderboard_and_non_leaderboard_queries(
    query: str, expected_profile: str
) -> None:
    # behavioral: query classification must be broad enough for equivalent LLM
    # leaderboard wording, but narrow enough not to inject leaderboard sources
    # into short words, numeric fragments, or ordinary search prompts.
    plan = build_web_research_query_plan(query)

    assert plan.profile == expected_profile
    if expected_profile == "llm_leaderboard":
        assert plan.trusted_seed_urls == TRUSTED_LEADERBOARD_URLS
        assert plan.minimum_relevant_sources == 2
    else:
        assert plan.trusted_seed_urls == []


@pytest.mark.parametrize(
    "query",
    [
        pytest.param("大模型排行榜 2026 水平排行", id="zh_rank"),
        pytest.param("2026 LLM leaderboard by price and speed", id="en_price_speed"),
    ],
)
def test_llm_leaderboard_seeds_precede_weak_or_low_trust_sources(query: str) -> None:
    # behavioral: when public search yields weak, noisy, or unsupported sources,
    # trusted leaderboard seeds must be first so low max_fetches still reaches
    # authoritative evidence instead of public-search noise.
    plan = build_web_research_query_plan(query)
    search_results = SearchResultSet(
        query=query,
        provider="public-search",
        items=[
            normalize_search_item(
                title="2026大模型 创新TOP100",
                url="https://baijiahao.baidu.com/s?id=weak-source",
                snippet="GEO营销、广告监管、token调用量和信息操控，不是可核实能力榜单。",
                rank=1,
                provider="public-search",
            ),
            normalize_search_item(
                title="Unsourced personal LLM top list",
                url="https://example.invalid/blog/unsourced-llm-top",
                snippet=(
                    "Personal ranking without source, price table, speed data, "
                    "or benchmark methodology."
                ),
                rank=2,
                provider="public-search",
            ),
        ],
    )

    planned = apply_query_plan_to_search_results(search_results, plan=plan)

    assert [item.url for item in planned.items] == [
        *TRUSTED_LEADERBOARD_URLS,
        "https://baijiahao.baidu.com/s?id=weak-source",
        "https://example.invalid/blog/unsourced-llm-top",
    ]
    assert [item.provider for item in planned.items] == [
        "platform:trusted_seed",
        "platform:trusted_seed",
        "public-search",
        "public-search",
    ]
    assert [item.rank for item in planned.items] == [1, 2, 3, 4]
    assert planned.diagnostics["query_profile"] == "llm_leaderboard"
    assert (
        planned.diagnostics["trusted_seed_candidate_urls"] == TRUSTED_LEADERBOARD_URLS
    )
    assert planned.diagnostics["minimum_relevant_sources"] == 2


def test_non_llm_leaderboard_queries_do_not_inherit_trusted_seed_or_diagnostics() -> (
    None
):
    # behavioral: the leaderboard repair must not regress unrelated search by
    # adding an LLM leaderboard source to generic, numeric, or short prompts.
    for query in ["猫", "2026 59.68 65.71 20.54", "北京今天适合带伞吗", "排行榜"]:
        plan = build_web_research_query_plan(query)
        search_results = SearchResultSet(
            query=query,
            provider="public-search",
            items=[
                normalize_search_item(
                    title="Original result",
                    url=f"https://example.invalid/search/{abs(hash(query))}",
                    snippet="Original public search result.",
                    rank=1,
                    provider="public-search",
                )
            ],
        )

        planned = apply_query_plan_to_search_results(search_results, plan=plan)

        assert planned.items == search_results.items
        assert planned.diagnostics == search_results.diagnostics
        assert not set(TRUSTED_LEADERBOARD_URLS) & {item.url for item in planned.items}
