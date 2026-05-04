"""
Deterministic query-to-evidence relevance gates for WebResearch.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
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
_RANK_MARKER_RE = re.compile(
    r"(?i)(?:^|[\s\n，。；;:：])(?:#?\d{1,2}[.)、]|第[一二三四五六七八九十\d]{1,3}|top\s*\d{1,3})"
)
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


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
    if any(host == low or host.endswith(f".{low}") for low in _LOW_TRUST_HOST_SUFFIXES):
        return "low"
    return "neutral"


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
