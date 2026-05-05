"""中文: BUG-2026-05-05-2327 的 AI 新闻摘要质量回归测试。

EN: AI-news digest quality regression coverage for BUG-2026-05-05-2327.

Test type: behavioral
Regression for: BUG-2026-05-05-2327
Original symptom: fresh smoke conversation 2327 completed, but the final answer
used generic channel/homepage descriptions from CCTV and AI News Today instead
of concrete fetched news items.
Scope: RecoveryManager structured WebResearch renderer for accepted ai_news
fetch evidence.
Mock strategy: ToolResult payloads are recorded-shape evidence fixtures from the
platform WebResearch runtime; no LLM output, intent routing, or renderer
decision is mocked.
"""

from __future__ import annotations

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult

QUERY = "查一下今日AI 新闻"
CCTV_URL = "https://5gai.cctv.com/AI/index.shtml"
AI_NEWS_TODAY_URL = "https://ainewstoday.net/"


def _ai_news_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-1",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="web_research",
        source_text=QUERY,
        status="pending",
        requires_tools=True,
        allowed_tool_names=["web_search", "fetch_url"],
        completion_signals=["fetch_url"],
    )


def _page_payload(
    *,
    url: str,
    title: str,
    description: str,
    summary: str,
    body: str,
) -> dict[str, object]:
    return {
        "url": url,
        "status": "completed",
        "title": title,
        "body_text": body,
        "summary": summary,
        "description": description,
        "answer_quality": "body",
        "provider": "builtin:fetch_url",
        "failure_kind": None,
        "relevance_status": "relevant",
        "relevance_score": 0.67,
        "relevance_profile": "ai_news",
        "relevance_reason": "query_relevance_passed",
        "relevance_matched_terms": ["ai", "人工智能", "最新", "2026"],
        "relevance_required_terms": [],
    }


def _fetch_result(
    *,
    page: dict[str, object],
    all_pages: list[dict[str, object]],
) -> ToolResult:
    url = str(page["url"])
    title = str(page["title"])
    description = str(page["description"])
    summary = str(page["summary"])
    body = str(page["body_text"])
    return ToolResult(
        tool_call_id=f"web-research-1:fetch_url:{url}",
        name="fetch_url",
        success=True,
        output=f"Content from {url}:\nTitle: {title}\nDescription: {description}\n\n{body}",
        summary=summary,
        result_link=url,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "url": url,
            "final_url": url,
            "title": title,
            "description": description,
            "summary": summary,
            "answer_quality": "body",
            "evidence_quality": "body",
            "answer_source": "fetched_body",
            "status": "completed",
            "provider": "builtin:fetch_url",
            "relevance_status": "relevant",
            "relevance_score": 0.67,
            "relevance_profile": "ai_news",
            "relevance_reason": "query_relevance_passed",
            "web_research_evidence": {
                "query": QUERY,
                "status": "completed",
                "search_provider": "builtin:web_search",
                "fetch_provider": "builtin:fetch_url",
                "search_results": [],
                "fetched_pages": all_pages,
                "citations": [
                    {
                        "title": str(item["title"]),
                        "url": str(item["url"]),
                        "provider": "builtin:fetch_url",
                        "source": "page",
                        "rank": None,
                    }
                    for item in all_pages
                ],
                "answer_quality": "body",
                "failure_kind": None,
                "diagnostics": {
                    "evidence_status": "completed",
                    "answer_source": "fetched_body",
                    "relevance_profile": "ai_news",
                    "raw": {
                        "query_profile": "ai_news",
                        "minimum_relevant_sources": 2,
                        "accepted_source_count": 2,
                    },
                },
            },
        },
    )


def test_2327_ai_news_digest_uses_concrete_body_items_not_site_descriptions() -> None:
    cctv_page = _page_payload(
        url=CCTV_URL,
        title="央视网数智频道-人工智能",
        description="聚焦数字中国建设，关注AI科技前沿，以数智传播全媒体服务助力中国式现代化行稳致远。",
        summary="央视网数智频道-人工智能 - 聚焦数字中国建设，关注AI科技前沿，以数智传播全媒体服务助力中国式现代化行稳致远。",
        body=(
            "AI与科学仪器融合已到关键节点\n\n"
            "高端科学仪器是国之重器，当前“人工智能（AI）+”正在推动科学仪器实现智能化、精准化发展。\n\n"
            "2026-04-28 11:39:17\n\n"
            "AI新模型拉响网络安全攻防警报\n\n"
            "当人工智能的“触手”伸向网络安全领域，一场前所未有的风暴悄然降临。\n\n"
            "2026-04-20 11:49:20"
        ),
    )
    ai_news_today_page = _page_payload(
        url=AI_NEWS_TODAY_URL,
        title="AI News Today | Daily trending Artificial Intelligence (AI) news source",
        description=(
            "AI News Today delivers AI news spanning AI innovations, enterprise AI, "
            "AI models, and robotics - keeping you informed on the latest artificial "
            "intelligence developments."
        ),
        summary=(
            "AI News Today | Daily trending Artificial Intelligence (AI) news source - "
            "AI News Today delivers AI news spanning AI innovations, enterprise AI, "
            "AI models, and robotics - keeping you informed on the latest artificial int... [truncated]"
        ),
        body=(
            "Why Amazon is Cutting 16,000 Jobs and What AI Has to Do With It\n\n"
            "Feb 2, 2026\n\n"
            "Google Veo 3 Is Transforming Ai Video Creation And Content Production\n\n"
            "Uk Sovereign Ai Fund Bet On Ineffable Intelligence\n\n"
            "Apr 29, 2026"
        ),
    )
    pages = [cctv_page, ai_news_today_page]
    fetch_results = [
        _fetch_result(page=cctv_page, all_pages=pages),
        _fetch_result(page=ai_news_today_page, all_pages=pages),
    ]

    updated = RecoveryManager.update_intent_statuses(
        [_ai_news_intent()],
        messages=[],
        tool_results=fetch_results,
    )
    output = RecoveryManager.build_completed_output(
        updated,
        tool_results=fetch_results,
        reason="partial_exit_recovery",
    )

    assert updated[0].status == "completed"
    assert "今日 AI 新闻摘要" in output
    assert "AI与科学仪器融合已到关键节点" in output
    assert (
        "Google Veo 3 Is Transforming Ai Video Creation And Content Production"
        in output
    )
    assert (
        "Google Veo 3 Is Transforming Ai Video Creation And Content Production："
        "Uk Sovereign Ai Fund Bet On Ineffable Intelligence"
    ) not in output
    assert "聚焦数字中国建设" not in output
    assert "delivers AI news spanning" not in output
    assert "Daily trending Artificial Intelligence" not in output
