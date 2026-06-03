"""Tool argument recovery tests."""

# Test type: structural

from app.ai.engine.tool_processor import ToolCallProcessor


class TestParseArguments:
    """parse_arguments 应在异常 JSON 输入时返回显式错误码。"""

    def test_valid_json_returns_dict_and_none(self) -> None:
        args, err = ToolCallProcessor.parse_arguments('{"mode":"compact"}')
        assert err is None
        assert args == {"mode": "compact"}

    def test_empty_string_returns_empty_dict_and_none(self) -> None:
        args, err = ToolCallProcessor.parse_arguments("")
        assert err is None
        assert args == {}

    def test_invalid_json_returns_invalid_tool_arguments_json(self) -> None:
        args, err = ToolCallProcessor.parse_arguments("{invalid json}")
        assert err == "invalid_tool_arguments_json"
        assert args is None

    def test_truncated_json_returns_error(self) -> None:
        args, err = ToolCallProcessor.parse_arguments('{"page_key":')
        assert err == "invalid_tool_arguments_json"
        assert args is None

    def test_dict_input_passthrough(self) -> None:
        raw = {"a": 1, "b": "x"}
        args, err = ToolCallProcessor.parse_arguments(raw)
        assert err is None
        assert args is raw
