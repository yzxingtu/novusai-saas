"""Tests for _try_repair_json enhancements."""
from app.ai.engine.tool_processor import _try_repair_json, ToolCallProcessor


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
