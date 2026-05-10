"""Custom recovery manager coverage for consent-pause semantics.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.types import ChatMessage


def _intent(
    intent_id: str,
    label: str,
    *,
    status: str = "pending",
    requires_tools: bool = True,
) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind="user_request",
        family="general",
        order=1,
        user_visible_label=label,
        source_text="",
        status=status,
        requires_tools=requires_tools,
    )


def test_update_intent_statuses_marks_pending_consent() -> None:
    intents = [
        _intent("intent-consent", "Approve Delete", status="pending"),
        _intent("intent-later", "Finish other work", status="pending"),
    ]
    messages = [
        ChatMessage(
            role="assistant",
            content="Need your confirmation before proceeding.",
            metadata={"pending_consent": {"tool_name": "delete_record"}},
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=messages,
        tool_results=None,
    )

    assert updated[0].status == "awaiting_consent"
    assert updated[0].metadata["pending_consent"]["tool_name"] == "delete_record"
    assert updated[1].status == "pending"


def test_decide_pauses_for_pending_consent_intent() -> None:
    intent = _intent("intent-consent", "Approve Delete", status="awaiting_consent")
    intent.metadata["pending_consent"] = {"tool_name": "delete_record"}

    decision = RecoveryManager.decide([intent], budget=None)

    assert decision is not None
    assert decision.action == "pause_for_consent"
    assert decision.target_intent_id == "intent-consent"
    assert decision.metadata["pending_consent"]["tool_name"] == "delete_record"
    assert decision.unfinished_intent_ids == ["intent-consent"]


def test_build_partial_output_is_user_friendly_text() -> None:
    intents = [
        _intent("intent-weather", "天气", status="completed"),
        _intent("intent-page", "页面内容", status="pending"),
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="elapsed_budget_exceeded",
    )

    assert "[PARTIAL EXIT]" not in output
    assert "Failure kind" not in output
    assert "天气" in output
    assert "页面内容" in output
