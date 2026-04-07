from app.ai.engine.base import BaseEngine
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


def _page_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="get_page_context"),
        ToolDefinition(name="pageop_list_available_menus"),
        ToolDefinition(name="pageop_navigate_menu"),
        ToolDefinition(name="invoke_page_operation"),
        ToolDefinition(name="pageop_capture_screenshot"),
        ToolDefinition(name="pageop_get_editor_html"),
        ToolDefinition(name="pageop_replace_content"),
        ToolDefinition(name="pageop_create_record"),
        ToolDefinition(name="pageop_fill_form"),
        ToolDefinition(name="pageop_validate_form"),
        ToolDefinition(name="pageop_submit_form"),
        ToolDefinition(name="pageop_read_row_detail"),
        ToolDefinition(name="pageop_read_visible_rows"),
        ToolDefinition(name="pageop_go_to_page"),
        ToolDefinition(name="pageop_prev_page"),
        ToolDefinition(name="pageop_next_page"),
        ToolDefinition(name="pageop_set_page_size"),
        ToolDefinition(name="pageop_search"),
        ToolDefinition(name="pageop_clear_search"),
        ToolDefinition(name="pageop_refresh_list"),
    ]


def _repeated_page_context_result() -> ToolResult:
    return ToolResult(
        tool_call_id="call_1",
        name="get_page_context",
        success=True,
        output=(
            "Page context was already returned earlier in this turn. "
            "Reuse the previous get_page_context result unless the page actually changed."
        ),
    )


def _build_input_variables() -> dict:
    return {
        "page_context": {
            "page_key": "admin.dashboard",
            "page_data": {
                "available_operations": [
                    {"name": "navigate_menu"},
                    {"name": "list_available_menus"},
                    {"name": "capture_screenshot"},
                    {"name": "create_record"},
                    {"name": "fill_form"},
                    {"name": "validate_form"},
                    {"name": "submit_form"},
                    {"name": "read_row_detail"},
                    {"name": "read_visible_rows"},
                    {"name": "go_to_page"},
                    {"name": "prev_page"},
                    {"name": "next_page"},
                    {"name": "set_page_size"},
                    {"name": "search"},
                    {"name": "clear_search"},
                    {"name": "refresh_list"},
                    {"name": "get_editor_html"},
                    {"name": "replace_content"},
                ],
                "available_menus": [
                    {
                        "title": "智能体管理",
                        "page_key": "admin.ai.agents",
                        "path": "/admin/ai/agents",
                        "keywords": ["智能体", "agent", "AI助手", "assistant"],
                    }
                ],
            },
        }
    }


def _recover(user_text: str) -> tuple[str | None, list[str], dict]:
    return BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content=user_text)],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_page_context", "arguments": "{}"},
            }
        ],
        tool_results=[_repeated_page_context_result()],
        tools=_page_tools(),
        input_variables=_build_input_variables(),
    )


def test_build_page_no_progress_recovery_for_navigation_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我新增 AI 助手")

    assert hint is not None
    assert "Do NOT call get_page_context again" in hint
    assert preferred_tool_names == [
        "pageop_list_available_menus",
        "pageop_navigate_menu",
        "invoke_page_operation",
    ]
    assert diagnostics["intent_kind"] == "page_navigation"


def test_build_page_no_progress_recovery_for_screenshot_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我给当前页面截图")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_capture_screenshot",
        "invoke_page_operation",
    ]
    assert diagnostics["intent_kind"] == "page_screenshot"


def test_build_page_no_progress_recovery_for_editor_write_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我替换当前编辑器正文")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_replace_content",
    ]
    assert diagnostics["intent_kind"] == "page_editor_write"


def test_build_page_no_progress_recovery_for_form_write_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我新增记录并提交表单")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_create_record",
        "pageop_fill_form",
        "pageop_validate_form",
        "pageop_submit_form",
    ]
    assert diagnostics["intent_kind"] == "page_form_write"


def test_build_page_no_progress_recovery_for_row_detail_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("查看这条记录详情")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
    ]
    assert diagnostics["intent_kind"] == "page_row_detail"


def test_build_page_no_progress_recovery_for_pagination_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("翻到下一页")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_go_to_page",
        "pageop_prev_page",
        "pageop_next_page",
        "pageop_set_page_size",
    ]
    assert diagnostics["intent_kind"] == "page_pagination"


def test_build_page_no_progress_recovery_for_search_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("搜索记录并清空筛选")

    assert hint is not None
    assert preferred_tool_names == [
        "pageop_search",
        "pageop_clear_search",
        "pageop_refresh_list",
    ]
    assert diagnostics["intent_kind"] == "page_search"


def test_build_page_no_progress_recovery_skips_generic_page_summary_turn() -> None:
    hint, preferred_tool_names, diagnostics = _recover("读一下当前页面有什么")

    assert hint is None
    assert preferred_tool_names == []
    assert diagnostics == {}
