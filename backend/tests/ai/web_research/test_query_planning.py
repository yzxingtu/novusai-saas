"""
Test type: behavioral
Scope: WebResearch query-profile planning and trusted seed candidate ordering.
Mock strategy: no LLM, planner, search provider, or tool executor is mocked.
Tests use the real deterministic planner and normalized search result contracts.
"""

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


def test_chinese_2026_llm_leaderboard_query_gets_trusted_seed_plan() -> None:
    # behavioral: this would fail if Chinese leaderboard intent stops mapping
    # to the llm_leaderboard profile or loses the trusted seeds.
    plan = build_web_research_query_plan("大模型排行榜 2026")

    assert plan.profile == "llm_leaderboard"
    assert plan.trusted_seed_urls == TRUSTED_LEADERBOARD_URLS
    assert plan.minimum_relevant_sources == 2
    assert plan.source_quality_floor == "trusted_leaderboard_or_relevant_benchmark"
    assert plan.trusted_seed_candidates[0].title == (
        "Artificial Analysis LLM Leaderboard"
    )
    assert plan.trusted_seed_candidates[1].title == "LMArena Arena Leaderboard"


def test_trusted_seeds_are_ranked_before_noisy_public_search_results() -> None:
    # behavioral: real plan application must put trusted leaderboard sources
    # ahead of unrelated public-search noise even when noise was rank 1.
    plan = build_web_research_query_plan("大模型排行榜 2026")
    search_results = SearchResultSet(
        query="大模型排行榜 2026",
        provider="public-search",
        items=[
            normalize_search_item(
                title="大模型排行榜被投毒了吗",
                url="https://baijiahao.baidu.com/s?id=noisy-315",
                snippet="3·15 广告监管 黑产 软文 信息操控，不是模型榜单。",
                rank=1,
                provider="public-search",
            ),
            normalize_search_item(
                title="General AI news",
                url="https://example.com/ai-news",
                snippet="General news about AI model launches.",
                rank=2,
                provider="public-search",
            ),
        ],
    )

    planned = apply_query_plan_to_search_results(search_results, plan=plan)

    assert [item.url for item in planned.items] == [
        *TRUSTED_LEADERBOARD_URLS,
        "https://baijiahao.baidu.com/s?id=noisy-315",
        "https://example.com/ai-news",
    ]
    assert [item.rank for item in planned.items] == [1, 2, 3, 4]
    assert planned.items[0].provider == "platform:trusted_seed"
    assert planned.items[1].provider == "platform:trusted_seed"
    assert planned.items[0].raw == {
        "source": "trusted_seed",
        "query_profile": "llm_leaderboard",
        "trusted_seed": True,
        "trusted_seed_index": 1,
    }
    assert planned.diagnostics["query_profile"] == "llm_leaderboard"
    assert planned.diagnostics["trusted_seed_candidate_urls"] == (
        TRUSTED_LEADERBOARD_URLS
    )
    assert planned.diagnostics["minimum_relevant_sources"] == 2
    assert planned.diagnostics["planned_result_count"] == 4


def test_duplicate_trusted_seed_and_search_url_is_deduplicated() -> None:
    # behavioral: if public search already returns the same trusted URLs, the
    # platform seeds stay first and duplicate search hits are removed.
    plan = build_web_research_query_plan("大模型排行榜 2026")
    search_results = SearchResultSet(
        query="大模型排行榜 2026",
        provider="public-search",
        items=[
            normalize_search_item(
                title="Search duplicate",
                url="https://artificialanalysis.ai/leaderboards/models/",
                snippet="Duplicate of the platform trusted seed.",
                rank=1,
                provider="public-search",
            ),
            normalize_search_item(
                title="LM Arena duplicate",
                url="https://lmarena.ai/leaderboard",
                snippet="Duplicate of the arena trusted seed.",
                rank=2,
                provider="public-search",
            ),
            normalize_search_item(
                title="LiveBench leaderboard",
                url="https://livebench.ai/",
                snippet="Model ranking and benchmark.",
                rank=3,
                provider="public-search",
            ),
        ],
    )

    planned = apply_query_plan_to_search_results(search_results, plan=plan)

    assert [item.url for item in planned.items] == [
        *TRUSTED_LEADERBOARD_URLS,
        "https://livebench.ai/",
    ]
    assert [item.provider for item in planned.items] == [
        "platform:trusted_seed",
        "platform:trusted_seed",
        "public-search",
    ]
    assert [item.rank for item in planned.items] == [1, 2, 3]


def test_generic_query_does_not_inject_trusted_seed() -> None:
    # behavioral: trusted leaderboard seeds are profile-specific and must not
    # pollute unrelated generic web research queries.
    plan = build_web_research_query_plan("北京今天适合带伞吗")
    search_results = SearchResultSet(
        query="北京今天适合带伞吗",
        provider="public-search",
        items=[
            normalize_search_item(
                title="Beijing weather",
                url="https://weather.example.com/beijing",
                snippet="Forecast and precipitation probability.",
                rank=1,
                provider="public-search",
            )
        ],
    )

    planned = apply_query_plan_to_search_results(search_results, plan=plan)

    assert plan.profile == "generic"
    assert plan.trusted_seed_urls == []
    assert planned.items == search_results.items
    assert planned.diagnostics == search_results.diagnostics
