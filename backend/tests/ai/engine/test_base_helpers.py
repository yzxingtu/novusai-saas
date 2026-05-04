"""
Test type: structural
Scope: split base helper facade contracts after runtime refactors.
"""

from app.ai.engine.base_helpers import (
    keep_tool_calls_for_round,
    messages_to_dicts,
)
from app.ai.types import ChatMessage


def test_keep_tool_calls_for_round_is_noop_after_data_ops_retirement() -> None:
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {
                "name": "crm_update_record",
                "arguments": "{bad json 1",
            },
        },
        {
            "id": "c2",
            "type": "function",
            "function": {
                "name": "crm_update_record",
                "arguments": "{bad json 2",
            },
        },
        {
            "id": "c3",
            "type": "function",
            "function": {
                "name": "crm_update_record",
                "arguments": "{bad json 3",
            },
        },
    ]

    prepared_tool_calls, changed = keep_tool_calls_for_round(tool_calls)

    assert changed is False
    assert [tool_call["id"] for tool_call in prepared_tool_calls] == ["c1", "c2", "c3"]


def test_messages_to_dicts_serializes_chat_messages() -> None:
    messages = [
        ChatMessage(role="system", content="SYS"),
        ChatMessage(role="user", content="hello", metadata={"trace_id": "abc"}),
    ]

    payload = messages_to_dicts(messages)

    assert payload[0]["role"] == "system"
    assert payload[1]["metadata"] == {"trace_id": "abc"}
