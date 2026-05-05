"""
Deterministic query-to-evidence relevance gates for WebResearch.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.ai.web_research.evidence import (
    PageEvidence,
    RelevanceStatus,
    SearchEvidenceItem,
)

_LLM_SUBJECT_TERMS = (
    "大模型",
    "语言模型",
    "基础模型",
    "模型",
    "llm",
    "large language model",
    "language model",
    "ai model",
    "frontier model",
)
_LEADERBOARD_QUERY_TERMS = (
    "排行榜",
    "排行",
    "排名",
    "榜单",
    "水平排行",
    "leaderboard",
    "ranking",
    "rank",
    "top",
)
_LEADERBOARD_EVIDENCE_TERMS = _LEADERBOARD_QUERY_TERMS + (
    "arena",
    "benchmark",
    "benchmarks",
    "评测",
    "测评",
    "评估",
    "得分",
    "score",
    "scores",
    "elo",
    "quality index",
    "intelligence index",
    "livebench",
    "artificial analysis",
    "lmarena",
    "chatbot arena",
    "superclue",
    "swe-bench",
    "swebench",
    "mmlu",
    "gpqa",
)
_KNOWN_MODEL_TERMS = (
    "gpt",
    "openai",
    "claude",
    "anthropic",
    "gemini",
    "google",
    "deepseek",
    "qwen",
    "千问",
    "kimi",
    "moonshot",
    "doubao",
    "豆包",
    "ernie",
    "文心",
    "llama",
    "mistral",
    "mixtral",
    "grok",
    "xai",
    "minimax",
    "step",
    "阶跃",
    "智谱",
    "glm",
    "yi",
    "零一万物",
)
_FASHION_SUBJECT_TERMS = (
    "女性",
    "女士",
    "女装",
    "裙子",
    "女裙",
    "连衣裙",
    "半身裙",
    "款式",
    "穿搭",
    "服装",
    "时尚",
    "dress",
    "dresses",
    "skirt",
    "skirts",
    "fashion",
    "style",
    "styles",
    "outfit",
    "womenswear",
    "women",
)
_FASHION_TREND_TERMS = (
    "趋势",
    "流行",
    "热门",
    "热销",
    "春夏",
    "秋冬",
    "秀场",
    "runway",
    "trend",
    "trends",
    "popular",
    "spring",
    "summer",
    "fall",
    "winter",
)
_AI_NEWS_SUBJECT_TERMS = (
    "ai",
    "人工智能",
    "大模型",
    "生成式人工智能",
    "openai",
    "chatgpt",
    "anthropic",
    "claude",
    "gemini",
    "google",
    "deepmind",
    "nvidia",
    "英伟达",
    "microsoft",
    "微软",
    "meta",
    "llama",
    "deepseek",
    "qwen",
    "千问",
    "kimi",
    "mistral",
)
_AI_NEWS_QUERY_TERMS = (
    "新闻",
    "资讯",
    "快讯",
    "消息",
    "今日",
    "今天",
    "最新",
    "current",
    "today",
    "latest",
    "news",
    "breaking",
)
_AI_NEWS_EVENT_TERMS = _AI_NEWS_QUERY_TERMS + (
    "发布",
    "宣布",
    "报道",
    "推出",
    "上线",
    "更新",
    "融资",
    "监管",
    "announced",
    "reported",
    "launch",
    "launched",
    "released",
    "updated",
)
_AI_NEWS_FRESHNESS_TERMS = (
    "今日",
    "今天",
    "刚刚",
    "最新",
    "小时前",
    "分钟前",
    "天前",
    "today",
    "latest",
    "breaking",
    "hours ago",
    "minutes ago",
    "days ago",
    "yesterday",
)
_FASHION_STYLE_TERMS = (
    "a字裙",
    "a-line",
    "迷你裙",
    "mini",
    "midi",
    "maxi",
    "吊带裙",
    "slip dress",
    "衬衫裙",
    "shirt dress",
    "背心裙",
    "tank dress",
    "收腰",
    "waist",
    "蕾丝",
    "lace",
    "碎花",
    "floral",
    "ruffle",
    "ruffles",
    "褶皱",
    "draping",
    "cape dress",
    "半身裙",
    "连衣裙",
)
_LOW_VALUE_CONTEXT_TERMS = (
    "投毒",
    "3·15",
    "315",
    "广告监管",
    "信息操控",
    "黑产",
    "软文",
    "geo",
    "生成式引擎优化",
    "openclaw",
    "龙虾",
    "养虾",
    "安全风险",
    "漏洞",
    "token调用量",
    "token消耗",
    "消费",
    "恐慌",
)
_LOW_TRUST_HOST_SUFFIXES = (
    "baijiahao.baidu.com",
    "baijiahao.baidu.cn",
    "toutiao.com",
    "sohu.com",
    "163.com",
    "qq.com",
)
_TRUSTED_LEADERBOARD_HOSTS = (
    "artificialanalysis.ai",
    "lmarena.ai",
    "chatbotarena.ai",
    "livebench.ai",
    "openrouter.ai",
    "huggingface.co",
    "superclueai.com",
    "paperswithcode.com",
)
_TRUSTED_AI_NEWS_HOSTS = (
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
_RANK_MARKER_RE = re.compile(
    r"(?i)(?:^|[\s\n，。；;:：])(?:#?\d{1,2}[.)、]|第[一二三四五六七八九十\d]{1,3}|top\s*\d{1,3})"
)
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_GENERIC_QUERY_TOKEN_RE = re.compile(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}")
_GENERIC_QUERY_STOP_TERMS = frozenset(
    {
        "查一下",
        "一下",
        "最新",
        "热门",
        "当前",
        "现在",
        "排行",
        "排行榜",
        "排名",
        "榜单",
        "水平排行",
        "top",
        "rank",
        "ranking",
        "leaderboard",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceRelevance:
    status: RelevanceStatus
    score: float
    profile: str
    reason: str
    matched_terms: list[str]
    required_terms: list[str]
    source_quality: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_query_profile(query: str) -> str:
    normalized = _normalize(query)
    if _contains_any(normalized, _LLM_SUBJECT_TERMS) and _contains_any(
        normalized, _LEADERBOARD_QUERY_TERMS
    ):
        return "llm_leaderboard"
    if _contains_any(normalized, _AI_NEWS_SUBJECT_TERMS) and _contains_any(
        normalized, _AI_NEWS_QUERY_TERMS
    ):
        return "ai_news"
    if _contains_any(normalized, _FASHION_SUBJECT_TERMS) and (
        _contains_any(normalized, _LEADERBOARD_QUERY_TERMS)
        or _contains_any(normalized, _FASHION_TREND_TERMS)
    ):
        return "fashion_trend_ranking"
    if _contains_any(normalized, _LEADERBOARD_QUERY_TERMS):
        return "leaderboard"
    return "generic"


def evaluate_page_relevance(
    *,
    query: str,
    page: PageEvidence,
    search_item: SearchEvidenceItem | None = None,
) -> EvidenceRelevance:
    profile = detect_query_profile(query)
    if profile == "generic":
        return EvidenceRelevance(
            status="unscored",
            score=1.0,
            profile=profile,
            reason="generic_profile_unscored",
            matched_terms=[],
            required_terms=[],
            source_quality=_source_quality(page.url),
        )

    text = _normalize(
        " ".join(
            [
                page.title,
                page.summary,
                page.description,
                page.body_text,
                search_item.title if search_item else "",
                search_item.snippet if search_item else "",
            ]
        )
    )
    query_years = set(_YEAR_RE.findall(query))
    evidence_years = set(_YEAR_RE.findall(text))
    source_quality = _source_quality(page.url)

    if profile == "fashion_trend_ranking":
        return _evaluate_fashion_trend_relevance(
            profile=profile,
            text=text,
            query_years=query_years,
            evidence_years=evidence_years,
            source_quality=source_quality,
        )
    if profile == "ai_news":
        return _evaluate_ai_news_relevance(
            profile=profile,
            text=text,
            query=_normalize(query),
            query_years=query_years,
            evidence_years=evidence_years,
            source_quality=source_quality,
        )
    if profile == "leaderboard":
        return _evaluate_generic_leaderboard_relevance(
            profile=profile,
            text=text,
            query=_normalize(query),
            query_years=query_years,
            evidence_years=evidence_years,
            source_quality=source_quality,
        )

    return _evaluate_llm_leaderboard_relevance(
        profile=profile,
        text=text,
        query_years=query_years,
        evidence_years=evidence_years,
        source_quality=source_quality,
    )


def _evaluate_ai_news_relevance(
    *,
    profile: str,
    text: str,
    query: str,
    query_years: set[str],
    evidence_years: set[str],
    source_quality: str,
) -> EvidenceRelevance:
    subject_matches = _matched_terms(text, _AI_NEWS_SUBJECT_TERMS)
    event_matches = _matched_terms(text, _AI_NEWS_EVENT_TERMS)
    freshness_matches = _matched_terms(text, _AI_NEWS_FRESHNESS_TERMS)
    current_query = _contains_any(query, _AI_NEWS_QUERY_TERMS)
    stale_years = _stale_evidence_years(evidence_years)
    has_current_year = _current_year_text() in evidence_years
    has_current_date = _has_current_date_signal(text)
    has_freshness_signal = bool(
        freshness_matches or has_current_year or has_current_date
    )

    score = 0.0
    matched_terms: list[str] = []
    required_terms: list[str] = []
    if subject_matches:
        score += 0.3
        matched_terms.extend(subject_matches[:6])
    else:
        required_terms.append("ai_news_subject")
    if event_matches:
        score += 0.25
        matched_terms.extend(event_matches[:6])
    else:
        required_terms.append("current_news_event_signal")
    if query_years:
        if query_years & evidence_years:
            score += 0.1
            matched_terms.extend(sorted(query_years & evidence_years))
        else:
            required_terms.append("query_year_match")
    elif current_query and has_freshness_signal and not stale_years:
        score += 0.12
        matched_terms.extend(freshness_matches[:4])
        if has_current_year:
            matched_terms.append(_current_year_text())
        if has_current_date:
            matched_terms.append("current_date")
    elif current_query:
        required_terms.append("current_date_or_current_year_signal")
    if source_quality == "trusted":
        score += 0.25
    elif source_quality == "low":
        score -= 0.35
        required_terms.append("trusted_current_news_source")
    if current_query and stale_years:
        score -= 0.3
        required_terms.append("current_date_or_current_year_signal")
    score = max(0.0, min(1.0, round(score, 3)))

    if required_terms or score < _threshold_for_profile(profile):
        return EvidenceRelevance(
            status="low_relevance",
            score=score,
            profile=profile,
            reason="low_query_relevance",
            matched_terms=_dedupe(matched_terms),
            required_terms=_dedupe(required_terms),
            source_quality=source_quality,
        )
    return EvidenceRelevance(
        status="relevant",
        score=score,
        profile=profile,
        reason="query_relevance_passed",
        matched_terms=_dedupe(matched_terms),
        required_terms=[],
        source_quality=source_quality,
    )


def _evaluate_llm_leaderboard_relevance(
    *,
    profile: str,
    text: str,
    query_years: set[str],
    evidence_years: set[str],
    source_quality: str,
) -> EvidenceRelevance:
    llm_matches = _matched_terms(text, _LLM_SUBJECT_TERMS)
    leaderboard_matches = _matched_terms(text, _LEADERBOARD_EVIDENCE_TERMS)
    model_matches = _matched_terms(text, _KNOWN_MODEL_TERMS)
    noise_matches = _matched_terms(text, _LOW_VALUE_CONTEXT_TERMS)
    rank_marker_count = len(_RANK_MARKER_RE.findall(text))

    score = 0.0
    matched_terms: list[str] = []
    required_terms: list[str] = []
    if llm_matches:
        score += 0.2
        matched_terms.extend(llm_matches[:4])
    else:
        required_terms.append("llm_subject")
    if leaderboard_matches:
        score += 0.2
        matched_terms.extend(leaderboard_matches[:5])
    else:
        required_terms.append("leaderboard_or_benchmark")
    if len(model_matches) >= 3:
        score += 0.15
        matched_terms.extend(model_matches[:6])
    else:
        required_terms.append("multiple_model_names")
    if rank_marker_count >= 2:
        score += 0.15
        matched_terms.append("rank_markers")
    elif len(model_matches) >= 4 and leaderboard_matches:
        score += 0.08
    else:
        required_terms.append("ranked_list_or_scores")
    if _contains_any(text, ("benchmark", "评测", "测评", "得分", "score", "elo")):
        score += 0.15
    if query_years and query_years & evidence_years:
        score += 0.05
        matched_terms.extend(sorted(query_years & evidence_years))
    if source_quality == "trusted":
        score += 0.15
    elif source_quality == "low":
        score -= 0.25
    if len(noise_matches) >= 3:
        score -= 0.25
    score = max(0.0, min(1.0, round(score, 3)))

    low_trust_noise = source_quality == "low" and len(noise_matches) >= 3
    if low_trust_noise:
        required_terms.append("source_not_dominated_by_unrelated_context")

    if required_terms or score < _threshold_for_profile(profile):
        return EvidenceRelevance(
            status="low_relevance",
            score=score,
            profile=profile,
            reason="low_query_relevance",
            matched_terms=_dedupe(matched_terms),
            required_terms=_dedupe(required_terms),
            source_quality=source_quality,
        )
    return EvidenceRelevance(
        status="relevant",
        score=score,
        profile=profile,
        reason="query_relevance_passed",
        matched_terms=_dedupe(matched_terms),
        required_terms=[],
        source_quality=source_quality,
    )


def _evaluate_fashion_trend_relevance(
    *,
    profile: str,
    text: str,
    query_years: set[str],
    evidence_years: set[str],
    source_quality: str,
) -> EvidenceRelevance:
    subject_matches = _matched_terms(text, _FASHION_SUBJECT_TERMS)
    trend_matches = _matched_terms(text, _FASHION_TREND_TERMS)
    leaderboard_matches = _matched_terms(text, _LEADERBOARD_EVIDENCE_TERMS)
    style_matches = _matched_terms(text, _FASHION_STYLE_TERMS)
    rank_marker_count = len(_RANK_MARKER_RE.findall(text))
    trend_list_signal = bool(
        rank_marker_count >= 2
        or (
            style_matches
            and trend_matches
            and _contains_any(text, ("八大", "十大", "top", "list", "roundup"))
        )
        or (len(style_matches) >= 3 and trend_matches)
    )

    score = 0.0
    matched_terms: list[str] = []
    required_terms: list[str] = []
    if subject_matches:
        score += 0.25
        matched_terms.extend(subject_matches[:5])
    else:
        required_terms.append("fashion_subject")
    if trend_matches or leaderboard_matches:
        score += 0.25
        matched_terms.extend((trend_matches + leaderboard_matches)[:6])
    else:
        required_terms.append("trend_or_ranking")
    if len(style_matches) >= 2:
        score += 0.2
        matched_terms.extend(style_matches[:6])
    elif style_matches:
        score += 0.1
        matched_terms.extend(style_matches[:3])
    else:
        required_terms.append("concrete_dress_styles")
    if trend_list_signal:
        score += 0.15
        matched_terms.append("rank_or_trend_list_markers")
    elif leaderboard_matches and style_matches:
        score += 0.08
    else:
        required_terms.append("ranked_list_or_trend_list")
    if query_years and query_years & evidence_years:
        score += 0.05
        matched_terms.extend(sorted(query_years & evidence_years))
    if source_quality == "low":
        score -= 0.25
    score = max(0.0, min(1.0, round(score, 3)))

    if required_terms or score < _threshold_for_profile(profile):
        return EvidenceRelevance(
            status="low_relevance",
            score=score,
            profile=profile,
            reason="low_query_relevance",
            matched_terms=_dedupe(matched_terms),
            required_terms=_dedupe(required_terms),
            source_quality=source_quality,
        )
    return EvidenceRelevance(
        status="relevant",
        score=score,
        profile=profile,
        reason="query_relevance_passed",
        matched_terms=_dedupe(matched_terms),
        required_terms=[],
        source_quality=source_quality,
    )


def _evaluate_generic_leaderboard_relevance(
    *,
    profile: str,
    text: str,
    query: str,
    query_years: set[str],
    evidence_years: set[str],
    source_quality: str,
) -> EvidenceRelevance:
    leaderboard_matches = _matched_terms(text, _LEADERBOARD_EVIDENCE_TERMS)
    rank_marker_count = len(_RANK_MARKER_RE.findall(text))
    subject_hits = _generic_query_subject_hits(query, text)

    score = 0.0
    matched_terms: list[str] = []
    required_terms: list[str] = []
    if leaderboard_matches:
        score += 0.3
        matched_terms.extend(leaderboard_matches[:6])
    else:
        required_terms.append("ranking_or_list_signal")
    if rank_marker_count >= 2:
        score += 0.25
        matched_terms.append("rank_markers")
    else:
        required_terms.append("ranked_list_or_scores")
    if subject_hits >= 1:
        score += 0.2
        matched_terms.append("query_subject_terms")
    if query_years and query_years & evidence_years:
        score += 0.05
        matched_terms.extend(sorted(query_years & evidence_years))
    if source_quality == "trusted":
        score += 0.1
    elif source_quality == "low":
        score -= 0.25
    score = max(0.0, min(1.0, round(score, 3)))

    if required_terms or score < _threshold_for_profile(profile):
        return EvidenceRelevance(
            status="low_relevance",
            score=score,
            profile=profile,
            reason="low_query_relevance",
            matched_terms=_dedupe(matched_terms),
            required_terms=_dedupe(required_terms),
            source_quality=source_quality,
        )
    return EvidenceRelevance(
        status="relevant",
        score=score,
        profile=profile,
        reason="query_relevance_passed",
        matched_terms=_dedupe(matched_terms),
        required_terms=[],
        source_quality=source_quality,
    )


def apply_page_relevance_gate(
    *,
    query: str,
    page: PageEvidence,
    search_item: SearchEvidenceItem | None = None,
) -> PageEvidence:
    if page.status != "completed" or page.answer_quality == "none":
        return page

    relevance = evaluate_page_relevance(
        query=query,
        page=page,
        search_item=search_item,
    )
    if relevance.status != "low_relevance":
        return _with_relevance(page, relevance)

    raw = dict(page.raw or {})
    raw["query_relevance"] = relevance.to_dict()
    raw["original_status"] = page.status
    raw["original_answer_quality"] = page.answer_quality
    return _with_relevance(
        replace(
            page,
            status="skipped",
            body_text="",
            summary="",
            answer_quality="none",
            failure_kind="low_query_relevance",
            raw=raw,
        ),
        relevance,
    )


def _with_relevance(page: PageEvidence, relevance: EvidenceRelevance) -> PageEvidence:
    return replace(
        page,
        relevance_status=relevance.status,
        relevance_score=relevance.score,
        relevance_profile=relevance.profile,
        relevance_reason=relevance.reason,
        relevance_matched_terms=list(relevance.matched_terms),
        relevance_required_terms=list(relevance.required_terms),
    )


def _threshold_for_profile(profile: str) -> float:
    if profile == "llm_leaderboard":
        return 0.58
    if profile == "ai_news":
        return 0.55
    if profile == "fashion_trend_ranking":
        return 0.5
    if profile == "leaderboard":
        return 0.5
    return 0.0


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_term_in_text(text, term) for term in terms)


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if _term_in_text(text, term)]


def _term_in_text(text: str, term: str) -> bool:
    normalized = term.casefold()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9]+", normalized):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return normalized in text


def _source_quality(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").casefold()
    if any(
        host == trusted or host.endswith(f".{trusted}")
        for trusted in _TRUSTED_LEADERBOARD_HOSTS
    ):
        return "trusted"
    if any(
        host == trusted or host.endswith(f".{trusted}")
        for trusted in _TRUSTED_AI_NEWS_HOSTS
    ):
        return "trusted"
    if any(host == low or host.endswith(f".{low}") for low in _LOW_TRUST_HOST_SUFFIXES):
        return "low"
    return "neutral"


def _stale_evidence_years(evidence_years: set[str]) -> set[str]:
    current_year = int(_current_year_text())
    stale: set[str] = set()
    for raw_year in evidence_years:
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        if year < current_year:
            stale.add(raw_year)
    return stale


def _current_year_text() -> str:
    return str(datetime.now(UTC).year)


def _has_current_date_signal(text: str) -> bool:
    now = datetime.now(UTC)
    month = now.month
    day = now.day
    compact_patterns = (
        f"{month}月{day}日",
        f"{month:02d}月{day:02d}日",
        f"{now.year}-{month:02d}-{day:02d}",
        f"{now.year}/{month:02d}/{day:02d}",
    )
    if any(pattern.casefold() in text for pattern in compact_patterns):
        return True
    month_abbr = calendar.month_abbr[month].casefold()
    month_name = calendar.month_name[month].casefold()
    english_patterns = (
        f"{month_abbr} {day}",
        f"{month_name} {day}",
        f"{month_abbr} {day}, {now.year}",
        f"{month_name} {day}, {now.year}",
    )
    return any(pattern and pattern in text for pattern in english_patterns)


def _generic_query_subject_hits(query: str, text: str) -> int:
    hits = 0
    for token in _GENERIC_QUERY_TOKEN_RE.findall(query):
        normalized_token = token.casefold()
        if normalized_token in _GENERIC_QUERY_STOP_TERMS:
            continue
        if _YEAR_RE.fullmatch(normalized_token):
            continue
        if _term_in_text(text, normalized_token):
            hits += 1
    return hits


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


__all__ = [
    "EvidenceRelevance",
    "apply_page_relevance_gate",
    "detect_query_profile",
    "evaluate_page_relevance",
]
