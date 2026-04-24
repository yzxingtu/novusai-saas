"""
Test type: behavioral
Scope: Page no-progress recovery derives canonical page_workflow metadata without
re-emitting legacy page_* aliases into live recovery diagnostics.
"""

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


def _build_input_variables_without_form() -> dict:
    return {
        "page_context": {
            "page_key": "admin.ai.agents",
            "ui_epoch": 9,
            "active_surface_id": "page-agents",
            "surface_stack": [
                {"surface_id": "page-agents", "kind": "page", "title": "智能体管理"},
            ],
        }
    }


def _recover(user_text: str) -> tuple[list[str], dict]:
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


def _assert_page_workflow_metadata(diagnostics: dict, goal: str) -> None:
    assert diagnostics["intent_kind"] == "page_workflow"
    assert diagnostics["page_workflow_kind"] == "page_workflow"
    assert diagnostics["workflow_goal"] == goal
    assert diagnostics["page_workflow_goal"] == goal
    assert "intent_kind_alias" not in diagnostics
    assert "page_workflow_intent_alias" not in diagnostics


def test_build_page_no_progress_recovery_for_navigation_request() -> None:
    preferred_tool_names, diagnostics = _recover("帮我打开智能体管理页面")

    assert preferred_tool_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    _assert_page_workflow_metadata(diagnostics, "navigation")
    assert diagnostics["workflow_stage"] == "verify_navigation_result"
    assert diagnostics["workflow_phase"] == "verify"
    assert diagnostics["page_workflow_progress"]["status"] == "verify_pending"


def test_build_page_no_progress_recovery_for_failed_cross_page_click() -> None:
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="添加供应商")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "ui_click",
                    "arguments": '{"target_locator":"添加供应商"}',
                },
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="ui_click",
                success=False,
                error="未找到目标元素：添加供应商",
            )
        ],
        tools=_page_tools(),
        input_variables={
            "page_context": {
                **_build_input_variables()["page_context"],
                "page_data": {
                    "navigation_catalog": [
                        {
                            "title": "供应商管理",
                            "path": "/admin/suppliers",
                            "page_key": "admin.suppliers",
                            "keywords": ["供应商", "添加供应商"],
                        }
                    ]
                },
            }
        },
    )

    assert preferred_tool_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    _assert_page_workflow_metadata(diagnostics, "navigation")
    assert diagnostics["reason"] == "page_navigation_failed_no_progress"
    assert diagnostics["workflow_state"]["has_active_surface"] is True


def test_build_page_no_progress_recovery_skips_navigation_retry_when_snapshot_shows_open_form() -> (
    None
):
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="点击一下添加供应商")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "ui_get_snapshot", "arguments": '{"mode":"compact"}'},
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="ui_get_snapshot",
                success=True,
                output=(
                    '{"mode":"compact","ui_epoch":15,'
                    '"active_surface_id":"surface:page:13",'
                    '"surface_stack":[{"surface_id":"surface:page:13","kind":"page","title":"供应商管理"}],'
                    '"active_form_session_id":"surface-page-13__session_1",'
                    '"active_form_summary":{"form_session_id":"surface-page-13__session_1","entity_name":"providers","mode":"create","stage":"ready","remaining_required_fields":["name"],"can_submit":false}}'
                ),
            )
        ],
        tools=_page_tools(),
        input_variables={
            "page_context": {
                "page_key": "admin.ai.providers",
                "ui_epoch": 14,
                "active_surface_id": "surface:page:13",
                "surface_stack": [
                    {
                        "surface_id": "surface:page:13",
                        "kind": "page",
                        "title": "供应商管理",
                    }
                ],
            }
        },
    )

    assert preferred_tool_names == []
    assert diagnostics == {}


def test_build_page_no_progress_recovery_for_screenshot_request() -> None:
    preferred_tool_names, diagnostics = _recover("帮我给当前页面截图")

    assert preferred_tool_names == [
        "ui_get_snapshot",
    ]
    _assert_page_workflow_metadata(diagnostics, "page_screenshot")


def test_build_page_no_progress_recovery_for_form_write_request() -> None:
    preferred_tool_names, diagnostics = _recover("帮我填写并提交表单")

    assert preferred_tool_names == [
        "ui_fill_form",
        "ui_set_field",
        "ui_submit_form",
    ]
    _assert_page_workflow_metadata(diagnostics, "form_write")
    assert diagnostics["workflow_stage"] == "submit_active_form"
    assert diagnostics["workflow_phase"] == "submit"


def test_build_page_no_progress_recovery_for_form_write_without_active_form() -> None:
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[
            ChatMessage(role="user", content="帮我添加一个测试的智能体 在本页面")
        ],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "ui_get_form_state", "arguments": "{}"},
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="ui_get_form_state",
                success=False,
                error="未找到活动中的表单会话。",
                error_type="form_session_not_found",
            )
        ],
        tools=_page_tools(),
        input_variables=_build_input_variables_without_form(),
    )

    assert preferred_tool_names == [
        "ui_open_surface",
        "ui_click",
        "ui_list_interactables",
    ]
    _assert_page_workflow_metadata(diagnostics, "form_write")
    assert diagnostics["reason"] == "page_form_session_missing"
    assert diagnostics["workflow_stage"] == "discover_form_before_write"
    assert diagnostics["workflow_phase"] == "discover"
    assert diagnostics["workflow_state"]["has_active_form"] is False
    assert diagnostics["page_workflow_progress"]["status"] == "discover_pending"


def test_build_page_no_progress_recovery_for_form_read_request() -> None:
    preferred_tool_names, diagnostics = _recover("帮我读取当前表单状态")

    assert preferred_tool_names == [
        "ui_get_form_state",
        "ui_read_region",
    ]
    _assert_page_workflow_metadata(diagnostics, "form_read")


def test_build_page_no_progress_recovery_for_row_detail_request() -> None:
    preferred_tool_names, diagnostics = _recover("查看这条记录详情")

    assert preferred_tool_names == [
        "ui_read_region",
        "ui_read_table",
    ]
    _assert_page_workflow_metadata(diagnostics, "row_detail")
    assert diagnostics["workflow_stage"] == "read_detail_surface"
    assert diagnostics["workflow_phase"] == "read"


def test_build_page_no_progress_recovery_for_row_detail_without_overlay_prefers_open_first() -> (
    None
):
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="查看这条记录详情")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "ui_get_snapshot", "arguments": "{}"},
            }
        ],
        tool_results=[_snapshot_result()],
        tools=_page_tools(),
        input_variables=_build_input_variables_without_form(),
    )

    assert preferred_tool_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
    ]
    assert diagnostics["workflow_stage"] == "open_detail_surface"
    assert diagnostics["workflow_state"]["has_overlay_surface"] is False


def test_build_page_no_progress_recovery_for_pagination_request() -> None:
    preferred_tool_names, diagnostics = _recover("翻到下一页")

    assert preferred_tool_names == [
        "ui_click",
        "ui_set_field",
        "ui_read_table",
        "ui_fill_form",
        "ui_submit_form",
        "ui_list_interactables",
    ]
    _assert_page_workflow_metadata(diagnostics, "pagination")


def test_build_page_no_progress_recovery_for_search_request() -> None:
    preferred_tool_names, diagnostics = _recover("搜索记录并清空筛选")

    assert preferred_tool_names == [
        "ui_click",
        "ui_fill_form",
        "ui_set_field",
        "ui_submit_form",
        "ui_read_table",
        "ui_read_region",
        "ui_list_interactables",
    ]
    _assert_page_workflow_metadata(diagnostics, "search")
    assert diagnostics["reason"] == "page_snapshot_only_round"


def test_build_page_no_progress_recovery_for_discovery_only_search_round() -> None:
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="搜索记录并清空筛选")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "ui_list_interactables",
                    "arguments": '{"surface_id":"active"}',
                },
            }
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call_1",
                name="ui_list_interactables",
                success=True,
                output='{"items":[],"count":0}',
            )
        ],
        tools=_page_tools(),
        input_variables=_build_input_variables_without_form(),
    )

    assert preferred_tool_names == [
        "ui_click",
        "ui_read_table",
        "ui_read_region",
    ]
    assert diagnostics["reason"] == "page_discovery_only_round"


def test_build_page_no_progress_recovery_for_table_summary_request() -> None:
    preferred_tool_names, diagnostics = _recover("列出这个表格前5条标题和时间")

    assert preferred_tool_names == [
        "ui_read_table",
        "ui_read_region",
    ]
    _assert_page_workflow_metadata(diagnostics, "table_summary")
    assert diagnostics["workflow_goal"] == "table_summary"


def test_build_page_no_progress_recovery_promotes_runtime_page_summary_to_table_summary() -> (
    None
):
    preferred_tool_names, diagnostics = BaseEngine._build_page_no_progress_recovery(  # noqa: SLF001
        messages=[ChatMessage(role="user", content="列出这个表格前5条标题和时间")],
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "ui_get_snapshot", "arguments": "{}"},
            }
        ],
        tool_results=[_snapshot_result()],
        tools=_page_tools(),
        input_variables={
            **_build_input_variables_without_form(),
            "_runtime_intent_facts": {
                "active_intent_kind": "page_workflow",
                "page_workflow_goal": "page_summary",
            },
        },
    )

    assert preferred_tool_names == [
        "ui_read_table",
        "ui_read_region",
    ]
    _assert_page_workflow_metadata(diagnostics, "table_summary")


def test_build_page_no_progress_recovery_skips_generic_page_summary_turn() -> None:
    preferred_tool_names, diagnostics = _recover("读一下当前页面有什么")

    assert preferred_tool_names == []
    assert diagnostics == {}
