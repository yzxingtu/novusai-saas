"""
Test type: behavioral
Regression for: BUG-2026-05-05-2308
Original symptom: conversation 2308 marked WebResearch recovery_evidence as
successful, but the assistant content was only English Vogue/Marie Claire source
snippets instead of a Chinese ranked answer for the user's fashion-ranking query.
Scope: recovery evidence rendering from completed fashion-trend fetch_url pages.
Mock strategy: no LLM/provider/tool executor mocks; inputs are recorded-shaped
ToolResult evidence matching the platform WebResearch fetch_url contract.
"""

from __future__ import annotations

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult


QUERY = "查一下 2026年最热门的 女性裙子款式排行！"


def _fashion_web_research_intent() -> IntentPlan:
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


def _fetch_result(
    *,
    tool_call_id: str,
    url: str,
    title: str,
    description: str,
    body: str,
) -> ToolResult:
    return ToolResult(
        tool_call_id=tool_call_id,
        name="fetch_url",
        success=True,
        output=(
            f"Content from {url}:\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"{body}"
        ),
        summary=description,
        result_link=url,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "url": url,
            "final_url": url,
            "title": title,
            "description": description,
            "summary": description,
            "answer_quality": "body",
            "status": "completed",
            "provider": "fake-fetch",
            "relevance_status": "relevant",
            "relevance_score": 0.75,
            "relevance_profile": "fashion_trend_ranking",
            "relevance_reason": "query_relevance_passed",
            "web_research_evidence": {
                "query": QUERY,
                "status": "completed",
                "answer_quality": "body",
                "diagnostics": {
                    "evidence_status": "completed",
                    "answer_source": "fetched_body",
                    "relevance_profile": "fashion_trend_ranking",
                    "raw": {"query_profile": "fashion_trend_ranking"},
                },
                "fetched_pages": [
                    {
                        "url": url,
                        "status": "completed",
                        "title": title,
                        "description": description,
                        "summary": description,
                        "body_text": body,
                        "answer_quality": "body",
                        "provider": "fake-fetch",
                        "relevance_status": "relevant",
                        "relevance_profile": "fashion_trend_ranking",
                    }
                ],
            },
        },
    )


def _conversation_2308_fashion_fetch_results() -> list[ToolResult]:
    return [
        _fetch_result(
            tool_call_id="call-vogue",
            url="https://www.vogue.com/article/spring-2026-dress-trends",
            title="10 Spring 2026 Dress Trends That Swept the Runways",
            description=(
                "From leggy minis to vibrant florals, these are the spring "
                "dress trends to know now."
            ),
            body=(
                "Vogue's spring 2026 dress trends include leggy minis, "
                "vibrant florals, lace dresses, slip dresses, shirt dresses, "
                "tank dresses, ruffles and cape dresses."
            ),
        ),
        _fetch_result(
            tool_call_id="call-marie-claire",
            url="https://www.marieclaire.com/fashion/summer-fashion/summer-fashion-trends-2026/",
            title="8 Essential Summer 2026 Fashion Trends Defining the Season",
            description=(
                "Here, the fashion trends shaping summer 2026, including "
                "dress and skirt styles."
            ),
            body=(
                "The summer 2026 fashion trends include dress and skirt styles "
                "women are wearing now. 1. A-line skirts. 2. Maxi dresses. "
                "3. Slip dresses. 4. Sheer skirts. 5. Draped dresses. "
                "6. Lace details. 7. Floral dresses. 8. Tailored shirt dresses."
            ),
        ),
    ]


def test_bug_2026_05_05_2308_renders_chinese_fashion_ranking_not_english_snippets() -> (
    None
):
    fetch_results = _conversation_2308_fashion_fetch_results()
    updated = RecoveryManager.update_intent_statuses(
        [_fashion_web_research_intent()],
        messages=[],
        tool_results=fetch_results,
    )
    output = RecoveryManager.build_completed_output(
        updated,
        tool_results=fetch_results,
        reason="partial_exit_recovery",
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["fetch_url"]
    assert "2026 女性裙装热门款式参考排行" in output
    assert "1. " in output
    assert "A字裙" in output
    assert "长款连衣裙" in output
    assert "吊带裙" in output
    assert "透视薄纱裙" in output
    assert "来源：Vogue、Marie Claire" in output
    assert "From leggy minis" not in output
    assert "Here, the fashion trends shaping summer 2026" not in output
