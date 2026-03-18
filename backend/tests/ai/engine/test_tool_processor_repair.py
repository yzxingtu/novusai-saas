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
