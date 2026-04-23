from __future__ import annotations

from types import SimpleNamespace

from app.ai.engine.stream_tool_call_helpers import (
    extract_action_buttons,
    finalize_stream_tool_calls,
    merge_stream_tool_calls,
    normalize_stream_tool_call,
)


def test_normalize_stream_tool_call_supports_object_shape() -> None:
    call = SimpleNamespace(
        index=0,
        id="call-1",
        type="function",
        function=SimpleNamespace(name="web_search", arguments='{"q":"ai"}'),
    )
    normalized = normalize_stream_tool_call(call)
    assert normalized is not None
    assert normalized["id"] == "call-1"
    assert normalized["function"]["name"] == "web_search"


def test_merge_stream_tool_calls_merges_by_index_and_appends_arguments() -> None:
    merged = merge_stream_tool_calls(
        [],
        [
            {"index": 0, "id": "call-1", "function": {"name": "fetch_", "arguments": "{"}},
            {"index": 0, "id": "call-1", "function": {"name": "fetch_url", "arguments": '"url":"a"}'}},
        ],
    )
    assert len(merged) == 1
    assert merged[0]["function"]["name"].startswith("fetch_")
    assert "url" in merged[0]["function"]["arguments"]


def test_merge_stream_tool_calls_prefers_latest_complete_json_snapshot() -> None:
    merged = merge_stream_tool_calls(
        [],
        [
            {
                "index": 0,
                "id": "call-1",
                "function": {
                    "name": "web_search",
                    "arguments": '{"max_results":5,"query":"北京 今天天气2026-0422 中国网"}',
                },
            },
            {
                "index": 0,
                "id": "call-1",
                "function": {
                    "name": "web_search",
                    "arguments": '{"max_results":5,"query":"北京 今天天气 2026-04-22 中国天气网"}',
                },
            },
        ],
    )

    assert len(merged) == 1
    assert merged[0]["function"]["arguments"] == (
        '{"max_results":5,"query":"北京 今天天气 2026-04-22 中国天气网"}'
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
    output = 'hello [ACTIONS][{"label":"A","value":"go","style":"primary"}][/ACTIONS] world'
    cleaned, buttons = extract_action_buttons(output)
    assert cleaned == "hello  world".strip()
    assert buttons is not None
    assert buttons[0]["label"] == "A"
