from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult


def _intent(intent_id: str, status: str, label: str) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind="user_request",
        family="general",
        order=1,
        user_visible_label=label,
        source_text="",
        status=status,
        requires_tools=False,
    )


def test_partial_exit_user_output_is_user_focused() -> None:
    intents = [
        _intent("intent-1", "completed", "Gather weather data"),
        _intent("intent-2", "completed", "Summarize the page"),
        _intent("intent-3", "pending", "Investigate remaining details"),
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="retry_budget_exhausted",
        provider_failure_kind="tool_timeout",
    )

    # Must not leak internal template markers or English metadata
    assert "[PARTIAL EXIT]" not in output
    assert "Failure kind" not in output
    assert "Reason:" not in output
    # Completed / unfinished labels should appear in natural text
    assert "Gather weather data" in output
    assert "Summarize the page" in output
    assert "Investigate remaining details" in output


def test_partial_exit_user_output_uses_partial_search_results_before_retry_exhausted_message() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "partial_result": (
                    "AI News Daily - https://example.com/ai-news；"
                    "OpenAI Updates - https://example.com/openai"
                )
            },
        )
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="retry_budget_exhausted",
        provider_failure_kind="none",
    )

    assert "AI News Daily" in output
    assert "OpenAI Updates" in output
    assert "目前拿到的结果" in output
    assert "还需要继续核验" in output
    assert "如果你愿意，我可以继续" not in output


def test_partial_exit_user_output_hides_unfinished_web_results_after_provider_failure() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "partial_result": (
                    "AI News Daily - https://example.com/ai-news；"
                    "OpenAI Updates - https://example.com/openai"
                )
            },
        )
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="provider_failure_after_partial_progress",
        provider_failure_kind="provider_http_5xx",
    )

    assert "AI News Daily" not in output
    assert "OpenAI Updates" not in output
    assert "目前拿到的结果" not in output
    assert "被系统中断了，请稍后再试。" in output


def test_update_intent_statuses_caches_partial_result_for_unfinished_search_intent() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tool-1",
                name="web_search",
                success=True,
                summary_payload={
                    "items": [
                        {
                            "title": "AI News Daily",
                            "url": "https://example.com/ai-news",
                        },
                        {
                            "title": "OpenAI Updates",
                            "url": "https://example.com/openai",
                        },
                    ]
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert "partial_result" in (updated[0].metadata or {})
    assert "AI News Daily" in updated[0].metadata["partial_result"]
    assert updated[0].allowed_tool_names == ["fetch_url"]
    assert updated[0].preferred_tool_names == ["fetch_url"]
    assert updated[0].completion_signals == ["fetch_url"]
    assert updated[0].metadata["requires_fetch_url"] is True
    assert updated[0].metadata["fetch_url_candidate_urls"] == [
        "https://example.com/ai-news",
        "https://example.com/openai",
    ]
    assert updated[0].metadata["fetch_url_attempted_urls"] == []
    assert updated[0].metadata["fetch_url_blocked_urls"] == []


def test_update_intent_statuses_marks_web_search_zero_results_as_completed() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="AI 新闻",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tool-1",
                name="web_search",
                success=True,
                output="No results found for: AI news",
                summary_payload={
                    "status": "no_results",
                    "result_count": 0,
                    "items": [],
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["web_search"]
    assert updated[0].cached_result is not None
    assert "没有找到" in updated[0].cached_result
    assert updated[0].metadata.get("requires_fetch_url") is None
    assert (
        updated[0].metadata["auto_fetch_gate_reason"] == "search_no_results_completed"
    )


def test_update_intent_statuses_uses_fetch_body_preview_for_web_research_result() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="放假时间",
            source_text="湖南学生放假时间",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output=(
                    "Content from https://finance.sina.com.cn/jjxw/2025-06-12/doc-inezupah3848475.shtml\n"
                    "Title: 放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网\n"
                    "Description: 近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。\n"
                    "Key sections: 放假通知！湖南12地明确！, VIP课程推荐\n\n"
                    "放假通知！湖南12地明确！\n"
                    "湖南12地公布2025年中小学暑假放假时间。\n"
                    "根据2024年校历安排，今年暑假从7月6日开始。\n"
                    "2025学年第一学期：2025年9月1日上课，2026年1月31日结束。\n"
                ),
                summary="放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "title": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                    "description": "近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。",
                    "summary": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert "今年暑假从7月6日开始" in updated[0].cached_result
    assert (
        updated[0].cached_result
        != "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网"
    )
