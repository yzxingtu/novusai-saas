from app.ai.engine.base import BaseEngine
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


def _page_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="ui_get_snapshot"),
        ToolDefinition(name="ui_read_region"),
        ToolDefinition(name="ui_read_table"),
        ToolDefinition(name="ui_list_interactables"),
        ToolDefinition(name="ui_click"),
        ToolDefinition(name="ui_open_surface"),
        ToolDefinition(name="ui_get_form_state"),
        ToolDefinition(name="ui_set_field"),
        ToolDefinition(name="ui_fill_form"),
        ToolDefinition(name="ui_submit_form"),
    ]


def _snapshot_result() -> ToolResult:
    return ToolResult(
        tool_call_id="call_1",
        name="ui_get_snapshot",
        success=True,
        output='{"ui_epoch": 9}',
    )


def _build_input_variables() -> dict:
    return {
        "page_context": {
            "page_key": "admin.dashboard",
            "ui_epoch": 9,
            "active_surface_id": "drawer-agent-edit",
            "surface_stack": [
                {"surface_id": "page-1", "kind": "page", "title": "Agent List"},
                {
                    "surface_id": "drawer-agent-edit",
                    "kind": "drawer",
                    "title": "Edit Agent",
                },
            ],
            "active_form_summary": {
                "form_session_id": "form-1",
                "can_submit": True,
                "stage": "ready_to_submit",
                "remaining_required_fields": [],
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
                "function": {"name": "ui_get_snapshot", "arguments": "{}"},
            }
        ],
        tool_results=[_snapshot_result()],
        tools=_page_tools(),
        input_variables=_build_input_variables(),
    )


def test_build_page_no_progress_recovery_for_navigation_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我打开智能体管理页面")

    assert hint is not None
    assert "Do NOT call ui_get_snapshot again" in hint
    assert preferred_tool_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_get_snapshot",
    ]
    assert diagnostics["intent_kind"] == "page_navigation"


def test_build_page_no_progress_recovery_for_screenshot_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我给当前页面截图")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_get_snapshot",
    ]
    assert diagnostics["intent_kind"] == "page_screenshot"


def test_build_page_no_progress_recovery_for_form_write_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我填写并提交表单")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_fill_form",
        "ui_set_field",
        "ui_submit_form",
    ]
    assert diagnostics["intent_kind"] == "page_form_write"


def test_build_page_no_progress_recovery_for_form_read_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("帮我读取当前表单状态")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_get_form_state",
        "ui_read_region",
        "ui_get_snapshot",
    ]
    assert diagnostics["intent_kind"] == "page_form_read"


def test_build_page_no_progress_recovery_for_row_detail_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("查看这条记录详情")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_read_region",
        "ui_read_table",
        "ui_get_snapshot",
    ]
    assert diagnostics["intent_kind"] == "page_row_detail"


def test_build_page_no_progress_recovery_for_pagination_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("翻到下一页")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_read_table",
        "ui_click",
        "ui_list_interactables",
    ]
    assert diagnostics["intent_kind"] == "page_pagination"


def test_build_page_no_progress_recovery_for_search_request() -> None:
    hint, preferred_tool_names, diagnostics = _recover("搜索记录并清空筛选")

    assert hint is not None
    assert preferred_tool_names == [
        "ui_read_region",
        "ui_list_interactables",
        "ui_click",
    ]
    assert diagnostics["intent_kind"] == "page_search"


def test_build_page_no_progress_recovery_skips_generic_page_summary_turn() -> None:
    hint, preferred_tool_names, diagnostics = _recover("读一下当前页面有什么")

    assert hint is None
    assert preferred_tool_names == []
    assert diagnostics == {}
