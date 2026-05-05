"""
Test type: behavioral
Regression for: BUG-2026-05-05-2311
Original symptom: fresh conversation 2311 completed WebResearch for
"查一下大模型排行榜 2026 水平排行！" with trusted Artificial Analysis evidence,
but the assistant answer was raw English page copy plus standalone numeric
scores instead of a Chinese model-ranking answer.
Scope: recovery evidence rendering from completed llm_leaderboard fetch_url pages.
Mock strategy: no LLM/provider/tool executor mocks; inputs are recorded-shaped
ToolResult evidence matching the platform WebResearch fetch_url contract.
"""

from __future__ import annotations

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult

QUERY = "查一下大模型排行榜 2026  水平排行！"
ARTIFICIAL_ANALYSIS_URL = "https://artificialanalysis.ai/leaderboards/models"


def _llm_leaderboard_intent() -> IntentPlan:
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


def _artificial_analysis_fetch_result() -> ToolResult:
    title = (
        "LLM Leaderboard - Comparison of over 100 AI models from OpenAI, "
        "Google, DeepSeek & others"
    )
    description = (
        "Comparison and ranking the performance of over 100 AI models (LLMs) "
        "across key metrics including intelligence, price, performance and speed."
    )
    body = (
        "LLM Leaderboard - Comparison of over 100 AI models from OpenAI, "
        "Google, DeepSeek & others\n\n"
        "Intelligence\n\n"
        "GPT-5.5 (xhigh) and GPT-5.5 (high) are the highest intelligence models, "
        "followed by Claude Opus 4.7 (max) and Gemini 3.1 Pro Preview.\n\n"
        "Output Speed\n\n"
        "Mercury 2 and Granite 3.3 8B are the fastest models, followed by "
        "Qwen3.5 0.8B and Gemini 3.1 Flash-Lite Preview.\n\n"
        "Latency\n\n"
        "Qwen3.5 4B and NVIDIA Nemotron 3 Nano are the lowest latency models, "
        "followed by Qwen3.5 4B and Ministral 3 3B.\n\n"
        "Price\n\n"
        "Qwen3.5 0.8B and Qwen3.5 0.8B are the cheapest models, followed by "
        "Gemma 3n E4B and Qwen3.5 2B.\n\n"
        "Context Window\n\n"
        "Llama 4 Scout and Grok 4.20 0309 support the largest context windows, "
        "followed by Gemini 1.5 Pro (May) and Grok 4.1 Fast.\n\n"
        "Further Analysis\n\n"
        "GPT-5.5 (xhigh)\n922k\nOpenAI\n60\n$11.25\n82\n65.59\n71.66\n"
    )
    return ToolResult(
        tool_call_id="call-artificial-analysis",
        name="fetch_url",
        success=True,
        output=(
            f"Content from {ARTIFICIAL_ANALYSIS_URL}:\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"{body}"
        ),
        summary=f"{title} - {description}",
        result_link=ARTIFICIAL_ANALYSIS_URL,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "url": ARTIFICIAL_ANALYSIS_URL,
            "final_url": ARTIFICIAL_ANALYSIS_URL,
            "title": title,
            "description": description,
            "summary": f"{title} - {description}",
            "answer_quality": "body",
            "status": "completed",
            "provider": "fake-fetch",
            "relevance_status": "relevant",
            "relevance_score": 0.85,
            "relevance_profile": "llm_leaderboard",
            "relevance_reason": "query_relevance_passed",
            "web_research_evidence": {
                "query": QUERY,
                "status": "completed",
                "answer_quality": "body",
                "diagnostics": {
                    "evidence_status": "completed",
                    "answer_source": "fetched_body",
                    "relevance_profile": "llm_leaderboard",
                    "raw": {"query_profile": "llm_leaderboard"},
                },
                "fetched_pages": [
                    {
                        "url": ARTIFICIAL_ANALYSIS_URL,
                        "status": "completed",
                        "title": title,
                        "description": description,
                        "summary": f"{title} - {description}",
                        "body_text": body,
                        "answer_quality": "body",
                        "provider": "fake-fetch",
                        "relevance_status": "relevant",
                        "relevance_profile": "llm_leaderboard",
                    }
                ],
            },
        },
    )


def test_bug_2026_05_05_2311_renders_chinese_llm_leaderboard_answer() -> None:
    fetch_results = [_artificial_analysis_fetch_result()]
    updated = RecoveryManager.update_intent_statuses(
        [_llm_leaderboard_intent()],
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
    assert "2026 大模型能力排行参考" in output
    assert "GPT-5.5" in output
    assert "Claude Opus 4.7" in output
    assert "Gemini 3.1 Pro" in output
    assert "输出速度" in output
    assert "价格" in output
    assert "来源：Artificial Analysis" in output
    assert "Comparison and ranking the performance" not in output
    assert "65.59\n71.66" not in output
