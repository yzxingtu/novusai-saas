"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from app.ai.engine.recovery_consent_helpers import (
    extract_pending_consent_payload,
    pending_consent_payload_from_tool_calls,
)
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
        ChatMessage(
            role="assistant",
            content="",
            metadata={"pending_consent": {"resolved": False, "tool_name": "a"}},
        )
    ]
    assert extract_pending_consent_payload(messages) == {
        "resolved": False,
        "tool_name": "a",
    }
