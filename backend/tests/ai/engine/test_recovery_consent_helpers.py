from __future__ import annotations

from app.ai.engine.recovery_consent_helpers import (
    ensure_latest_assistant_pending_consent,
    extract_pending_consent_payload,
    pending_consent_payload_from_decision,
    pending_consent_payload_from_tool_calls,
)
from app.ai.engine.types import RecoveryDecision
from app.ai.types import ChatMessage


def test_pending_consent_payload_from_tool_calls_ignores_resolved_entries() -> None:
    payload = pending_consent_payload_from_tool_calls(
        [
            {"pending_consent": {"resolved": True, "tool_name": "x"}},
            {"pending_consent": {"resolved": False, "tool_name": "y"}},
        ]
    )
    assert payload == {"resolved": False, "tool_name": "y"}


def test_extract_pending_consent_payload_reads_message_metadata_first() -> None:
    messages = [
        ChatMessage(role="assistant", content="", metadata={"pending_consent": {"resolved": False, "tool_name": "a"}})
    ]
    assert extract_pending_consent_payload(messages) == {
        "resolved": False,
        "tool_name": "a",
    }


def test_pending_consent_payload_from_decision_reads_metadata() -> None:
    decision = RecoveryDecision(
        action="pause_for_consent",
        metadata={"pending_consent": {"resolved": False, "tool_name": "fetch_url"}},
    )
    assert pending_consent_payload_from_decision(decision) == {
        "resolved": False,
        "tool_name": "fetch_url",
    }


def test_ensure_latest_assistant_pending_consent_updates_last_assistant_message() -> None:
    messages = [
        ChatMessage(role="user", content="u"),
        ChatMessage(role="assistant", content="a"),
    ]
    ensure_latest_assistant_pending_consent(
        messages,
        {"resolved": False, "tool_name": "fetch_url"},
    )
    assert messages[-1].metadata is not None
    assert messages[-1].metadata["pending_consent"]["tool_name"] == "fetch_url"
