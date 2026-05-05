"""
Query-profile planning for platform WebResearch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.ai.web_research.evidence import SearchEvidenceItem, SearchResultSet
from app.ai.web_research.normalization import normalize_search_item
from app.ai.web_research.relevance import detect_query_profile


@dataclass(frozen=True, slots=True)
class TrustedSeedCandidate:
    title: str
    url: str
    snippet: str
    provider: str = "platform:trusted_seed"


@dataclass(frozen=True, slots=True)
class WebResearchQueryPlan:
    profile: str
    trusted_seed_candidates: list[TrustedSeedCandidate]
    search_queries: list[str] = field(default_factory=list)
    minimum_relevant_sources: int = 1
    source_quality_floor: str = "any_relevant_fetch_evidence"

    @property
    def trusted_seed_urls(self) -> list[str]:
        return [candidate.url for candidate in self.trusted_seed_candidates]


_LLM_LEADERBOARD_TRUSTED_SEEDS = (
    TrustedSeedCandidate(
        title="Artificial Analysis LLM Leaderboard",
        url="https://artificialanalysis.ai/leaderboards/models",
        snippet=(
            "Comparison and ranking of AI models across intelligence, "
            "performance, price, speed and context metrics."
        ),
    ),
    TrustedSeedCandidate(
        title="LMArena Arena Leaderboard",
        url="https://lmarena.ai/leaderboard",
        snippet=(
            "Arena leaderboard comparing frontier AI models across text, code, "
            "vision, document, search and other benchmark arenas."
        ),
    ),
)
_FASHION_TREND_TRUSTED_SEEDS = (
    TrustedSeedCandidate(
        title="Vogue Spring 2026 Dress Trends",
        url="https://www.vogue.com/article/spring-2026-dress-trends",
        snippet=(
            "Vogue rounds up Spring 2026 dress trends from the runways, "
            "including minis, florals, lace, slip dresses and shirt dresses."
        ),
    ),
    TrustedSeedCandidate(
        title="Marie Claire Summer 2026 Fashion Trends",
        url="https://www.marieclaire.com/fashion/summer-fashion/summer-fashion-trends-2026/",
        snippet=(
            "Marie Claire lists Summer 2026 fashion trends with dress and "
            "skirt styles including A-line, maxi, slip and sheer details."
        ),
    ),
)


def build_web_research_query_plan(query: str) -> WebResearchQueryPlan:
    normalized_query = str(query or "").strip()
    profile = detect_query_profile(query)
    if profile == "llm_leaderboard":
        return WebResearchQueryPlan(
            profile=profile,
            trusted_seed_candidates=list(_LLM_LEADERBOARD_TRUSTED_SEEDS),
            search_queries=_dedupe_text([normalized_query]),
            minimum_relevant_sources=2,
            source_quality_floor="trusted_leaderboard_or_relevant_benchmark",
        )
    if profile == "fashion_trend_ranking":
        query_year = _query_year(normalized_query)
        return WebResearchQueryPlan(
            profile=profile,
            trusted_seed_candidates=_fashion_trend_trusted_seeds(query_year),
            search_queries=_fashion_trend_search_queries(
                normalized_query,
                year=query_year,
            ),
            minimum_relevant_sources=2,
            source_quality_floor="relevant_fashion_trend_ranking",
        )
    if profile == "ai_news":
        return WebResearchQueryPlan(
            profile=profile,
            trusted_seed_candidates=[],
            search_queries=_ai_news_search_queries(normalized_query),
            minimum_relevant_sources=2,
            source_quality_floor="current_trusted_cross_checked_ai_news",
        )
    return WebResearchQueryPlan(
        profile=profile,
        trusted_seed_candidates=[],
        search_queries=_dedupe_text([normalized_query]),
    )


def apply_query_plan_to_search_results(
    search_results: SearchResultSet,
    *,
    plan: WebResearchQueryPlan,
) -> SearchResultSet:
    should_attach_diagnostics = bool(
        plan.trusted_seed_candidates
        or plan.profile not in {"generic", "leaderboard"}
        or _dedupe_text(plan.search_queries)
        != _dedupe_text([str(search_results.query or "").strip()])
    )
    if not plan.trusted_seed_candidates:
        if not should_attach_diagnostics:
            return search_results
        items = _renumber_items(_ordered_organic_items(search_results, plan=plan))
        return replace(
            search_results,
            items=items,
            diagnostics=_planned_diagnostics(
                search_results,
                plan=plan,
                planned_result_count=len(items),
            ),
        )

    if not should_attach_diagnostics:
        return search_results

    items: list[SearchEvidenceItem] = []
    seen_url_keys: set[str] = set()
    organic_items = _ordered_organic_items(search_results, plan=plan)

    for seed in plan.trusted_seed_candidates:
        url_key = _canonical_url_key(seed.url)
        if url_key and url_key in seen_url_keys:
            continue
        if url_key:
            seen_url_keys.add(url_key)
        items.append(
            normalize_search_item(
                title=seed.title,
                url=seed.url,
                snippet=seed.snippet,
                rank=len(items) + 1,
                provider=seed.provider,
                raw={
                    "source": "trusted_seed",
                    "query_profile": plan.profile,
                    "trusted_seed": True,
                    "trusted_seed_index": len(items) + 1,
                },
            )
        )

    for item in organic_items:
        url_key = _canonical_url_key(item.url)
        if url_key and url_key in seen_url_keys:
            continue
        if url_key:
            seen_url_keys.add(url_key)
        items.append(replace(item, rank=len(items) + 1))

    planned_status = "completed" if items else search_results.status
    return replace(
        search_results,
        status=planned_status,
        failure_kind=None
        if planned_status == "completed"
        else search_results.failure_kind,
        items=items,
        diagnostics=_planned_diagnostics(
            search_results,
            plan=plan,
            planned_result_count=len(items),
        ),
    )


_CANONICAL_URL_SCHEME = "https"
_LEADING_WWW_PREFIX = "www."
_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "spm",
    }
)
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def _canonical_url_key(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/")

    netloc = _canonical_netloc(parsed.netloc)
    path = parsed.path.rstrip("/") or "/"
    query = _canonical_query(parsed.query)
    return urlunsplit((_CANONICAL_URL_SCHEME, netloc, path, query, ""))


def _canonical_netloc(netloc: str) -> str:
    normalized = str(netloc or "").casefold()
    if normalized.startswith(_LEADING_WWW_PREFIX):
        return normalized.removeprefix(_LEADING_WWW_PREFIX)
    return normalized


def _canonical_query(query: str) -> str:
    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        if _is_tracking_query_key(key):
            continue
        kept.append((key, value))
    return urlencode(sorted(kept))


def _is_tracking_query_key(key: str) -> bool:
    normalized_key = str(key or "").casefold()
    return normalized_key.startswith("utm_") or normalized_key in _TRACKING_QUERY_KEYS


def _ordered_organic_items(
    search_results: SearchResultSet,
    *,
    plan: WebResearchQueryPlan,
) -> list[SearchEvidenceItem]:
    items = sorted(search_results.items, key=lambda result: result.rank)
    if plan.profile == "ai_news":
        return sorted(
            items,
            key=lambda item: (
                -_ai_news_candidate_score(item),
                item.rank,
            ),
        )
    if plan.profile != "fashion_trend_ranking":
        return items
    return sorted(
        items,
        key=lambda item: (
            0 if _raw_search_query_index(item) > 0 else 1,
            -_fashion_candidate_score(item),
            item.rank,
        ),
    )


def _raw_search_query_index(item: SearchEvidenceItem) -> int:
    raw = dict(item.raw or {})
    try:
        return max(0, int(raw.get("search_query_index") or 0))
    except (TypeError, ValueError):
        return 0


def _fashion_candidate_score(item: SearchEvidenceItem) -> float:
    text = f"{item.title} {item.snippet}".casefold()
    score = 0.0
    for term in (
        "dress trends",
        "fashion trends",
        "women",
        "women's",
        "runway",
        "spring/summer",
        "ss26",
        "流行趋势",
        "裙子款式",
        "裙子",
        "连衣裙",
        "半身裙",
        "蕾丝",
        "款式",
        "时尚",
        "八大",
    ):
        if term in text:
            score += 1.0
    for penalty in (
        "京东",
        "选购",
        "儿童",
        "baby shower",
        "wedding",
        "bridal",
        "buying guide",
        "top sellers",
        "bloomingdale",
        "net-a-porter",
        "官网",
        "official",
        "shop",
    ):
        if penalty in text:
            score -= 1.5
    return score


_AI_NEWS_TRUSTED_HOST_SUFFIXES = (
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "cnbc.com",
    "theverge.com",
    "techcrunch.com",
    "wired.com",
    "technologyreview.com",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "nvidia.com",
    "microsoft.com",
    "meta.com",
    "mistral.ai",
    "deepseek.com",
)
_AI_NEWS_LOW_TRUST_HOST_SUFFIXES = (
    "baijiahao.baidu.com",
    "baijiahao.baidu.cn",
    "toutiao.com",
    "sohu.com",
    "163.com",
    "qq.com",
)


def _ai_news_candidate_score(item: SearchEvidenceItem) -> float:
    text = f"{item.title} {item.snippet}".casefold()
    host = _canonical_netloc(urlsplit(str(item.url or "")).netloc)
    score = 0.0
    if _host_matches(host, _AI_NEWS_TRUSTED_HOST_SUFFIXES):
        score += 3.0
    if _host_matches(host, _AI_NEWS_LOW_TRUST_HOST_SUFFIXES):
        score -= 3.0
    for term in (
        "ai",
        "人工智能",
        "大模型",
        "openai",
        "chatgpt",
        "anthropic",
        "claude",
        "gemini",
        "nvidia",
        "英伟达",
        "deepseek",
        "qwen",
        "千问",
    ):
        if term in text:
            score += 0.35
    for term in (
        "新闻",
        "资讯",
        "快讯",
        "今日",
        "今天",
        "latest",
        "today",
        "news",
        "breaking",
        "announced",
        "launch",
        "发布",
        "宣布",
        "报道",
    ):
        if term in text:
            score += 0.3
    for penalty in (
        "转载",
        "软文",
        "投毒",
        "广告",
        "黑产",
        "营销",
        "早新闻",
        "daily早新闻",
        "号",
    ):
        if penalty in text:
            score -= 0.5
    return score


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    normalized = str(host or "").casefold()
    return any(
        normalized == suffix or normalized.endswith(f".{suffix}") for suffix in suffixes
    )


def _renumber_items(items: list[SearchEvidenceItem]) -> list[SearchEvidenceItem]:
    return [replace(item, rank=index) for index, item in enumerate(items, start=1)]


def _query_year(query: str) -> str:
    years = _YEAR_RE.findall(str(query or ""))
    return years[0] if years else ""


def _fashion_trend_trusted_seeds(year: str) -> list[TrustedSeedCandidate]:
    if str(year or "").strip() == "2026":
        return list(_FASHION_TREND_TRUSTED_SEEDS)
    return []


def _fashion_trend_search_queries(query: str, *, year: str) -> list[str]:
    year_prefix = str(year or "").strip()
    english_query = (
        f"{year_prefix} women's dress trends ranking"
        if year_prefix
        else "women's dress trends ranking"
    )
    chinese_query = (
        f"{year_prefix} 女性 裙子 款式 流行趋势 排行"
        if year_prefix
        else "女性 裙子 款式 流行趋势 排行"
    )
    return _dedupe_text(
        [
            query,
            english_query,
            chinese_query,
        ]
    )


def _ai_news_search_queries(query: str) -> list[str]:
    return _dedupe_text(
        [
            query,
            "今日 AI 新闻 OpenAI NVIDIA 人工智能",
            "latest AI news today OpenAI NVIDIA artificial intelligence",
        ]
    )


def _planned_diagnostics(
    search_results: SearchResultSet,
    *,
    plan: WebResearchQueryPlan,
    planned_result_count: int,
) -> dict[str, object]:
    diagnostics = dict(search_results.diagnostics or {})
    diagnostics.update(
        {
            "query_profile": plan.profile,
            "trusted_seed_candidate_urls": plan.trusted_seed_urls,
            "trusted_seed_count": len(plan.trusted_seed_candidates),
            "organic_result_count": len(search_results.items),
            "planned_result_count": planned_result_count,
            "minimum_relevant_sources": plan.minimum_relevant_sources,
            "source_quality_floor": plan.source_quality_floor,
        }
    )
    search_queries = _dedupe_text(plan.search_queries)
    if search_queries:
        diagnostics["planned_search_queries"] = search_queries
    return diagnostics


def _dedupe_text(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


__all__ = [
    "TrustedSeedCandidate",
    "WebResearchQueryPlan",
    "apply_query_plan_to_search_results",
    "build_web_research_query_plan",
]
