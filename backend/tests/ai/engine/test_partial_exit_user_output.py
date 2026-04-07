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


def test_partial_exit_user_output_uses_partial_search_results_before_retry_exhausted_message() -> None:
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


def test_update_intent_statuses_caches_partial_result_for_unfinished_search_intent() -> None:
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
