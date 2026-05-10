"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from app.ai.engine.stream_tool_call_helpers import (
    extract_action_buttons,
    finalize_stream_tool_calls,
)


def test_finalize_stream_tool_calls_skips_invalid_and_fills_default_args() -> None:
    finalized = finalize_stream_tool_calls(
        [
            {"id": "x", "function": {"name": "", "arguments": ""}},
            {"id": "y", "function": {"name": "get_current_time", "arguments": ""}},
        ]
    )
    assert len(finalized) == 1
    assert finalized[0]["id"] == "y"
    assert finalized[0]["function"]["arguments"] == "{}"


def test_extract_action_buttons_returns_cleaned_output_and_buttons() -> None:
    output = (
        'hello [ACTIONS][{"label":"A","value":"go","style":"primary"}][/ACTIONS] world'
    )
    cleaned, buttons = extract_action_buttons(output)
    assert cleaned == "hello  world".strip()
    assert buttons is not None
    assert buttons[0]["label"] == "A"
