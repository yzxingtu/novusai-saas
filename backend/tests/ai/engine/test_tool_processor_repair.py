"""Tests for _try_repair_json enhancements.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

import json

from app.ai.engine.tool_processor import ToolCallProcessor, _try_repair_json
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


class _FakeExecutionState:
    def __init__(self, intent_plan: list[IntentPlan]) -> None:
        self.intent_plan = intent_plan
        self.readonly_tool_cache: dict[str, tuple[ToolResult, int]] = {}
        self.search_query_cache: dict[str, tuple[ToolResult, int]] = {}
        self.cache_hits: list[str] = []

    def cache_for_kind(self, kind: str) -> dict[str, tuple[ToolResult, int]]:
        if kind == "search_query":
            return self.search_query_cache
        return self.readonly_tool_cache

    def register_cache_hit(self, kind: str) -> None:
        self.cache_hits.append(kind)


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


def test_parse_arguments_repairs_bare_locator_object() -> None:
    args, err = ToolCallProcessor.parse_arguments(
        '{"table_locator: div >:nth-of-type(2)}'
    )

    assert err is None
    assert args == {"table_locator": "div >:nth-of-type(2)"}


def test_parse_arguments_repairs_quoted_bare_locator_object() -> None:
    args, err = ToolCallProcessor.parse_arguments('"{\\"section_locator: 智能体管理}"')

    assert err is None
    assert args == {"section_locator": "智能体管理"}


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
            tool_calls=[
                {
                    "id": "tc_preview",
                    "type": "function",
                    "function": {
                        "name": "update_records",
                        "arguments": '{"table_name":"agents","confirmed":false}',
                    },
                }
            ],
        ),
        ChatMessage(
            role="tool",
            content=json.dumps({"requires_confirmation": True, "preview": {}}),
            tool_call_id="tc_preview",
        ),
    ]

    pending = ToolCallProcessor.find_pending_confirmation(messages)

    assert pending is not None
    assert pending["name"] == "update_records"
    assert pending["arguments"]["confirmed"] is True


def test_check_consent_treats_approved_pending_consent_as_auto_once() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[ToolDefinition(name="get_current_weather")],
        consent_modes={"get_current_weather": "ask"},
        approved_pending_consent_tools={"get_current_weather"},
    )

    assert processor.check_consent("get_current_weather") == "auto"
    assert processor.check_consent("get_current_weather") == "auto"


def test_check_consent_auto_approves_readonly_tool_in_trusted_auto_mode() -> None:
    processor = ToolCallProcessor(
        sandbox=None,  # type: ignore[arg-type]
        tools=[ToolDefinition(name="get_current_time")],
        consent_modes={"get_current_time": "ask"},
        interaction_mode="trusted_auto",
    )

    assert processor.check_consent("get_current_time", {}) == "auto"
