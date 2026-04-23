"""Tool argument recovery and UI page hint tests."""

from app.ai.engine.base import BaseEngine
from app.ai.engine.tool_processor import ToolCallProcessor
from app.ai.tools.types import ToolDefinition


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


class TestPageOperationsHint:
    """页面运行时散文提示已退役。"""

    def test_returns_empty_hint_even_with_page_context_and_ui_tools(self) -> None:
        hint = BaseEngine._build_page_operations_hint(
            {
                "page_context": {
                    "page_key": "admin.ai.agents",
                    "active_surface_id": "drawer-1",
                    "surface_stack": [
                        {"surface_id": "page-1", "kind": "page", "title": "Agents"},
                        {"surface_id": "drawer-1", "kind": "drawer", "title": "Edit"},
                    ],
                    "active_form_summary": {
                        "form_session_id": "form-1",
                        "can_submit": True,
                        "stage": "ready_to_submit",
                    },
                }
            },
            [
                ToolDefinition(name="ui_get_snapshot", description="snapshot"),
                ToolDefinition(name="ui_read_region", description="read region"),
                ToolDefinition(name="ui_read_table", description="read table"),
                ToolDefinition(name="ui_list_interactables", description="list"),
                ToolDefinition(name="ui_click", description="click"),
                ToolDefinition(name="ui_open_surface", description="open"),
                ToolDefinition(name="ui_get_form_state", description="form state"),
                ToolDefinition(name="ui_set_field", description="set field"),
                ToolDefinition(name="ui_fill_form", description="fill form"),
                ToolDefinition(name="ui_submit_form", description="submit"),
            ],
        )

        assert hint == ""

    def test_returns_empty_hint_without_valid_page_context(self) -> None:
        hint = BaseEngine._build_page_operations_hint(
            {"page_context": {"page_title": "missing-key"}},
            [ToolDefinition(name="ui_get_snapshot", description="snapshot")],
        )
        assert hint == ""

    def test_ignores_suggested_submit_only_hints_without_active_form(self) -> None:
        hint = BaseEngine._build_page_operations_hint(
            {
                "page_context": {
                    "page_key": "admin.ai.agents",
                    "ui_epoch": 2,
                    "suggested_tools": {
                        "primary": ["ui_submit_form", "ui_fill_form"],
                        "secondary": ["ui_get_form_state"],
                    },
                }
            },
            [
                ToolDefinition(name="ui_get_snapshot", description="snapshot"),
                ToolDefinition(name="ui_click", description="click"),
                ToolDefinition(name="ui_fill_form", description="fill form"),
                ToolDefinition(name="ui_submit_form", description="submit"),
            ],
        )

        assert hint == ""
