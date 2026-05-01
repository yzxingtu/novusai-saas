from app.ai.engine.base_helpers import (
    messages_to_dicts,
    truncate_tool_calls_after_navigation,
)
from app.ai.types import ChatMessage


def test_truncate_tool_calls_after_navigation_is_noop_after_data_ops_retirement() -> None:
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

    truncated, trimmed = truncate_tool_calls_after_navigation(
        tool_calls,
        navigation_operation_names={"crm_update_record"},
    )

    assert trimmed is False
    assert [tool_call["id"] for tool_call in truncated] == ["c1", "c2", "c3"]


def test_messages_to_dicts_serializes_chat_messages() -> None:
    messages = [
        ChatMessage(role="system", content="SYS"),
        ChatMessage(role="user", content="hello", metadata={"trace_id": "abc"}),
    ]

    payload = messages_to_dicts(messages)

    assert payload[0]["role"] == "system"
    assert payload[1]["metadata"] == {"trace_id": "abc"}
