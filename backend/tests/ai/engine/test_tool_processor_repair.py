"""Tests for _try_repair_json enhancements."""
import json

from app.ai.engine.tool_processor import _try_repair_json, ToolCallProcessor
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage


def test_trailing_comma() -> None:
    assert _try_repair_json('{"a": 1,}') == {"a": 1}


def test_unescaped_newline() -> None:
    assert _try_repair_json('{"a": "x\ny"}') == {"a": "x\ny"}


def test_truncation() -> None:
    r = _try_repair_json('{"a": "unclosed')
    assert r == {"a": "unclosed"}


def test_parse_arguments_valid() -> None:
    args, err = ToolCallProcessor.parse_arguments(
        '{"table_name": "agents", "data": {"name": "test"}}'
    )
    assert err is None
    assert args is not None
    assert args["table_name"] == "agents"


def test_embedded_quotes() -> None:
    """DeepSeek may embed unescaped quotes inside string values."""
    raw = '{"data": {"name": "她叫"小喵"的猫", "age": 3}}'
    r = _try_repair_json(raw)
    assert r is not None
    assert r["data"]["age"] == 3
    assert "小喵" in r["data"]["name"]


def test_newlines_and_embedded_quotes() -> None:
    """Combined: literal newlines + embedded quotes."""
    raw = '{"data": {"prompt": "line1\nShe says "hello"\nline3", "ok": true}}'
    r = _try_repair_json(raw)
    assert r is not None
    assert r["data"]["ok"] is True


def test_multiline_chinese_system_prompt() -> None:
    """Simulate the typical DeepSeek failure: long Chinese system_prompt with
    literal newlines and embedded quotes."""
    raw = (
        '{"table_name": "agents", "data": {"name": "猫娘助手", '
        '"system_prompt": "你是一只可爱的猫娘。\n\n'
        "## 核心人设\n"
        '你是一只名叫"小喵"的猫娘\n'
        "- 说话时在句尾加喵~\n"
        '- 会撒娇打滚", "model_id": 2, "temperature": 0.8}}'
    )
    r = _try_repair_json(raw)
    assert r is not None
    assert r["table_name"] == "agents"
    assert r["data"]["model_id"] == 2
    assert r["data"]["temperature"] == 0.8


def test_brute_force_fallback() -> None:
    """When nothing else works, brute-force should at least produce a result."""
    raw = '{"a": "line1\nline2\nline3"}'
    r = _try_repair_json(raw)
    assert r is not None
    assert "a" in r


def test_find_pending_confirmation_injects_confirmed_for_preview_flow() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "tc_preview",
                "type": "function",
                "function": {
                    "name": "data_update",
                    "arguments": '{"table_name":"agents","confirmed":false}',
                },
            }],
        ),
        ChatMessage(
            role="tool",
            content=json.dumps({"requires_confirmation": True, "preview": {}}),
            tool_call_id="tc_preview",
        ),
    ]

    pending = ToolCallProcessor.find_pending_confirmation(messages)

    assert pending is not None
    assert pending["name"] == "data_update"
    assert pending["arguments"]["confirmed"] is True


def test_find_pending_confirmation_keeps_consent_tool_args_clean() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "tc_consent",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query":"OpenAI 最新新闻","max_results":1}',
                },
            }],
        ),
        ChatMessage(
            role="tool",
            content=json.dumps(
                {
                    "requires_confirmation": True,
                    "consent_required": True,
                    "action": "tool_consent",
                    "tool_name": "web_search",
                    "arguments": {
                        "query": "OpenAI 最新新闻",
                        "max_results": 1,
                    },
                },
                ensure_ascii=False,
            ),
            tool_call_id="tc_consent",
        ),
    ]

    pending = ToolCallProcessor.find_pending_confirmation(messages)

    assert pending is not None
    assert pending["name"] == "web_search"
    assert pending["arguments"] == {
        "query": "OpenAI 最新新闻",
        "max_results": 1,
    }
    assert "confirmed" not in pending["arguments"]


def test_build_follow_up_message_supports_non_attachment_tools() -> None:
    result = ToolResult(
        tool_call_id="tc_weather",
        name="get_current_weather",
        success=True,
        output="Current weather for Beijing: 18°C",
        llm_follow_up_message="Weather data retrieved successfully. Answer directly and do not call the same tool again.",
    )

    follow_up = ToolCallProcessor.build_follow_up_message(result)

    assert follow_up is not None
    assert follow_up.role == "user"
    assert follow_up.internal_only is True
    assert "do not call the same tool again" in (follow_up.content or "")
    assert follow_up.attachments is None
