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


def _workflow_intent(goal: str) -> IntentPlan:
    return IntentPlan(
        intent_id=f"intent-page-workflow-{goal}",
        kind="page_workflow",
        family="page_ops",
        order=1,
        user_visible_label="page_workflow",
        source_text=goal,
        metadata={
            "page_workflow_goal": goal,
            "page_workflow_kind": "page_workflow",
        },
    )


def _web_intent(*, metadata: dict | None = None) -> IntentPlan:
    return IntentPlan(
        intent_id="intent-web",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="web_research",
        source_text="web_research",
        metadata=dict(metadata or {}),
    )


def test_tool_router_prioritizes_screenshot_tools_over_generic_page_read() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("page_screenshot")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="帮我截图当前页面",
    )

    assert [tool.name for tool in decision.candidate_tools] == [
        "ui_get_snapshot",
    ]
    assert decision.intent_preferred_tools["intent-page-workflow-page_screenshot"] == [
        "ui_get_snapshot",
    ]


def test_tool_router_prefers_surface_discovery_before_form_write_when_form_not_open() -> (
    None
):
    decision = ToolRouter.route(
        intents=[_workflow_intent("form_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={
            "page_context": {"page_key": "admin.ai.agents", "ui_epoch": 5}
        },
        user_text="帮我新增一条记录并提交表单",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-form_write"] == [
        "ui_list_interactables",
        "ui_open_surface",
        "ui_click",
        "ui_get_form_state",
        "ui_fill_form",
        "ui_submit_form",
    ]


def test_tool_router_supports_canonical_page_workflow_goal_metadata() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("form_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={
            "page_context": {"page_key": "admin.ai.agents", "ui_epoch": 5}
        },
        user_text="帮我新增一条记录并提交表单",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-form_write"] == [
        "ui_list_interactables",
        "ui_open_surface",
        "ui_click",
        "ui_get_form_state",
        "ui_fill_form",
        "ui_submit_form",
    ]


def test_tool_router_prefers_form_surface_discovery_before_form_read_when_form_not_open() -> (
    None
):
    decision = ToolRouter.route(
        intents=[_workflow_intent("form_read")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={
            "page_context": {"page_key": "admin.ai.agents", "ui_epoch": 5}
        },
        user_text="先打开编辑表单并读取字段",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-form_read"] == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_get_form_state",
        "ui_read_region",
        "ui_get_snapshot",
    ]


def test_tool_router_prefers_snapshot_verification_when_navigation_surface_is_already_open() -> (
    None
):
    plan = ToolRouter.page_intent_tool_plan(
        "page_workflow",
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "navigation",
        },
        input_variables={
            "page_context": {
                "page_key": "admin.suppliers",
                "ui_epoch": 7,
                "active_surface_id": "drawer-create-supplier",
                "surface_stack": [
                    {"surface_id": "page-suppliers", "kind": "page"},
                    {
                        "surface_id": "drawer-create-supplier",
                        "kind": "drawer",
                    },
                ],
            }
        },
    )

    assert plan.workflow_stage == "verify_navigation_result"
    assert plan.workflow_phase == "verify"
    assert plan.preferred_names == [
        "ui_get_snapshot",
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    assert plan.workflow_state.has_overlay_surface is True
    assert plan.workflow_state.active_surface_kind == "drawer"


def test_tool_router_navigation_plan_is_page_key_agnostic() -> None:
    def _plan_for(page_key: str):
        return ToolRouter.page_intent_tool_plan(
            "page_workflow",
            intent_metadata={
                "page_workflow_kind": "page_workflow",
                "page_workflow_goal": "navigation",
            },
            input_variables={
                "page_context": {
                    "page_key": page_key,
                    "ui_epoch": 7,
                    "active_surface_id": "drawer-active",
                    "surface_stack": [
                        {"surface_id": "page-root", "kind": "page"},
                        {"surface_id": "drawer-active", "kind": "drawer"},
                    ],
                }
            },
        )

    conversations_plan = _plan_for("admin.ai.conversations")
    generic_plan = _plan_for("admin.runtime.records")

    assert conversations_plan.workflow_stage == generic_plan.workflow_stage
    assert conversations_plan.workflow_phase == generic_plan.workflow_phase
    assert conversations_plan.preferred_names == generic_plan.preferred_names
    assert conversations_plan.allowed_names == generic_plan.allowed_names
    assert conversations_plan.workflow_state.active_surface_kind == "drawer"
    assert generic_plan.workflow_state.active_surface_kind == "drawer"


def test_tool_router_keeps_form_write_mutation_chain_when_active_form_exists() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("form_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "active_form_session_id": "form-agent-create",
                "active_form_summary": {
                    "form_session_id": "form-agent-create",
                    "mode": "create",
                    "stage": "ready_to_submit",
                    "can_submit": True,
                },
            }
        },
        user_text="帮我新增一条记录并提交表单",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-form_write"] == [
        "ui_get_form_state",
        "ui_fill_form",
        "ui_set_field",
        "ui_submit_form",
        "ui_open_surface",
    ]
    plan = ToolRouter.page_intent_tool_plan(
        "page_workflow",
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "form_write",
        },
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "active_form_session_id": "form-agent-create",
                "active_form_summary": {
                    "form_session_id": "form-agent-create",
                    "mode": "create",
                    "stage": "ready_to_submit",
                    "can_submit": True,
                },
            }
        },
    )
    assert plan.workflow_phase == "submit"


def test_tool_router_opens_row_detail_surface_before_read_when_no_overlay_exists() -> (
    None
):
    plan = ToolRouter.page_intent_tool_plan(
        "page_workflow",
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "row_detail",
        },
        input_variables={
            "page_context": {
                "page_key": "admin.ai.logs",
                "ui_epoch": 3,
                "active_surface_id": "page-logs",
                "surface_stack": [
                    {"surface_id": "page-logs", "kind": "page"},
                ],
            }
        },
    )

    assert plan.workflow_stage == "open_detail_surface"
    assert plan.workflow_phase == "navigate_or_open"
    assert plan.allowed_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
        "ui_get_snapshot",
    ]
    assert plan.workflow_state.surface_stack_depth == 1


def test_tool_router_keeps_editor_tools_when_many_page_operations_exist() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("editor_write")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={
            "page_context": {
                "page_key": "admin.ai.editor",
                "ui_epoch": 2,
            }
        },
        user_text="帮我替换这一段正文并更新标题",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-editor_write"] == [
        "ui_open_surface",
        "ui_fill_form",
        "ui_submit_form",
    ]


def test_tool_router_prefers_row_detail_tools_for_detail_request() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("row_detail")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs", "ui_epoch": 2}},
        user_text="查看这条记录详情",
    )

    assert decision.intent_preferred_tools["intent-page-workflow-row_detail"] == [
        "ui_click",
        "ui_open_surface",
        "ui_read_region",
        "ui_read_table",
        "ui_get_snapshot",
        "ui_list_interactables",
    ]


def test_tool_router_prefers_pagination_tools_for_page_jump_request() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("pagination")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs", "ui_epoch": 2}},
        user_text="跳到下一页",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-pagination"] == [
        "ui_click",
        "ui_set_field",
        "ui_read_table",
        "ui_fill_form",
        "ui_submit_form",
        "ui_list_interactables",
    ]


def test_tool_router_prefers_table_read_tools_for_table_summary_request() -> None:
    decision = ToolRouter.route(
        intents=[_workflow_intent("table_summary")],
        tools=_page_tools(),
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs", "ui_epoch": 2}},
        user_text="帮我列出这个表格前5条标题和时间",
    )

    assert decision.intent_allowed_tools["intent-page-workflow-table_summary"] == [
        "ui_read_table",
        "ui_get_snapshot",
        "ui_read_region",
    ]
    assert decision.intent_preferred_tools["intent-page-workflow-table_summary"] == [
        "ui_read_table",
        "ui_get_snapshot",
        "ui_read_region",
    ]


def test_tool_router_pins_explicit_url_web_research_to_fetch_url() -> None:
    decision = ToolRouter.route(
        intents=[
            _web_intent(
                metadata={
                    "explicit_url": "https://example.com",
                    "fetch_only": True,
                    "prefer_fetch_url": True,
                }
            )
        ],
        tools=[
            ToolDefinition(name="web_search"),
            ToolDefinition(name="fetch_url"),
        ],
        budget=_budget(),
        input_variables={"page_context": {"page_key": "admin.ai.logs"}},
        user_text="请抓取 https://example.com",
    )

    assert [tool.name for tool in decision.candidate_tools] == ["fetch_url"]
    assert decision.intent_allowed_tools["intent-web"] == ["fetch_url"]
    assert decision.intent_preferred_tools["intent-web"] == ["fetch_url"]
