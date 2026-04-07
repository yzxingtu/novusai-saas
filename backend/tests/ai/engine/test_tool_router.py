from app.ai.engine.tool_router import ToolRouter
from app.ai.engine.types import ExecutionBudget, IntentPlan
from app.ai.tools.types import ToolDefinition


def _budget(max_candidate_tools: int = 8) -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=8000,
        max_completion_tokens=2000,
        max_tool_rounds=3,
        max_elapsed_ms=60000,
        max_retry_per_intent=1,
        max_candidate_tools=max_candidate_tools,
        max_tool_result_bytes=40000,
        finalization_grace_ms=15000,
    )


def _page_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="get_page_context"),
        ToolDefinition(name="invoke_page_operation"),
        ToolDefinition(name="pageop_capture_screenshot"),
        ToolDefinition(name="pageop_create_record"),
        ToolDefinition(name="pageop_edit_record"),
        ToolDefinition(name="pageop_fill_form"),
        ToolDefinition(name="pageop_validate_form"),
        ToolDefinition(name="pageop_submit_form"),
        ToolDefinition(name="pageop_get_editor_html"),
        ToolDefinition(name="pageop_get_editor_text"),
        ToolDefinition(name="pageop_replace_content"),
        ToolDefinition(name="pageop_replace_section"),
        ToolDefinition(name="pageop_append_content"),
        ToolDefinition(name="pageop_insert_content"),
        ToolDefinition(name="pageop_update_title"),
        ToolDefinition(name="pageop_search"),
        ToolDefinition(name="pageop_clear_search"),
        ToolDefinition(name="pageop_refresh_list"),
        ToolDefinition(name="pageop_go_to_page"),
        ToolDefinition(name="pageop_prev_page"),
        ToolDefinition(name="pageop_next_page"),
        ToolDefinition(name="pageop_set_page_size"),
        ToolDefinition(name="pageop_read_row_detail"),
        ToolDefinition(name="pageop_read_visible_rows"),
    ]


def _intent(kind: str) -> IntentPlan:
    return IntentPlan(
        intent_id=f"intent-{kind}",
        kind=kind,
        family="page_ops",
        order=1,
        user_visible_label=kind,
        source_text=kind,
    )


def test_tool_router_prioritizes_screenshot_tools_over_generic_page_read() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_screenshot")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="帮我截图当前页面",
    )

    assert [tool.name for tool in decision.candidate_tools] == [
        "pageop_capture_screenshot",
        "invoke_page_operation",
    ]
    assert decision.intent_preferred_tools["intent-page_screenshot"] == [
        "pageop_capture_screenshot",
        "invoke_page_operation",
    ]


def test_tool_router_keeps_form_write_chain_when_many_page_operations_exist() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_form_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="帮我新增一条记录并提交表单",
    )

    assert decision.intent_allowed_tools["intent-page_form_write"] == [
        "pageop_create_record",
        "pageop_edit_record",
        "pageop_fill_form",
        "pageop_validate_form",
        "pageop_submit_form",
    ]


def test_tool_router_keeps_editor_tools_when_many_page_operations_exist() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_editor_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.editor"}},
        user_text="帮我替换这一段正文并更新标题",
    )

    assert decision.intent_allowed_tools["intent-page_editor_write"] == [
        "pageop_replace_content",
        "pageop_replace_section",
        "pageop_append_content",
        "pageop_insert_content",
        "pageop_update_title",
    ]


def test_tool_router_prefers_row_detail_tools_for_detail_request() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_row_detail")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="查看这条记录详情",
    )

    assert decision.intent_preferred_tools["intent-page_row_detail"] == [
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
    ]


def test_tool_router_prefers_pagination_tools_for_page_jump_request() -> None:
    decision = ToolRouter.route(
        intents=[_intent("page_pagination")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="跳到下一页",
    )

    assert decision.intent_allowed_tools["intent-page_pagination"] == [
        "pageop_go_to_page",
        "pageop_prev_page",
        "pageop_next_page",
        "pageop_set_page_size",
    ]
