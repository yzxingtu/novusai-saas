from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan


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
