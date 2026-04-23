from app.ai.engine.tool_loop_session import (
    ToolLoopSession,
    apply_round_recovery_and_focus,
    build_tool_loop_session,
)
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=name)


def test_apply_round_recovery_and_focus_freezes_page_subset_without_system_hint() -> (
    None
):
    tools = [
        _tool("ui_get_snapshot"),
        _tool("ui_list_interactables"),
        _tool("ui_click"),
        _tool("ui_open_surface"),
    ]
    session = ToolLoopSession(
        current_response=ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            tool_calls=[],
        ),
        tools_full=tools,
        all_tools_full=tools,
        effective_policy=ToolUsePolicy(),
        ordered_requested_families=[],
        has_fetch_url_in_toolset=False,
        total_tokens=0,
        completion_tokens_used=0,
        tracked_tool_rounds=0,
        tracked_tool_result_bytes=0,
    )
    messages = [ChatMessage(role="user", content="打开供应商页面")]
    input_variables = {
        "_runtime_intent_plan": [
            {
                "intent_id": "intent-1",
                "kind": "page_navigation",
                "family": "page_ops",
                "order": 1,
                "user_visible_label": "page_navigation",
                "source_text": "打开供应商页面",
                "status": "pending",
                "requires_tools": True,
                "allow_text_response": False,
                "continuation": False,
                "shortcircuit": False,
                "cached_result": None,
                "allowed_tool_names": [
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                    "ui_get_snapshot",
                ],
                "preferred_tool_names": [
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                    "ui_get_snapshot",
                ],
                "completion_signals": ["ui_get_snapshot"],
                "completed_by_tool_names": [],
                "metadata": {
                    "page_workflow_stage": "verify_navigation_result",
                    "page_workflow_phase": "verify",
                    "page_workflow_goal": "navigation",
                },
            }
        ]
    }

    apply_round_recovery_and_focus(
        session=session,
        messages=messages,
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "ui_get_snapshot", "arguments": "{}"},
            }
        ],
        round_tool_results=[
            ToolResult(
                tool_call_id="call-1",
                name="ui_get_snapshot",
                success=True,
                output='{"ui_epoch": 9}',
            )
        ],
        all_tools=tools,
        input_variables=input_variables,
        build_page_no_progress_recovery=lambda **_kwargs: (
            ["ui_list_interactables", "ui_click", "ui_open_surface"],
            {
                "reason": "page_snapshot_only_round",
                "intent_kind": "page_workflow",
                "page_workflow_kind": "page_workflow",
                "round_tool_names": ["ui_get_snapshot"],
                "workflow_stage": "verify_navigation_result",
                "workflow_phase": "verify",
                "workflow_goal": "navigation",
                "page_workflow_stage": "verify_navigation_result",
                "page_workflow_phase": "verify",
                "page_workflow_goal": "navigation",
                "workflow_state": {"has_active_surface": True},
                "workflow_completion": {
                    "mode": "verify_only",
                    "completion_signals": ["ui_get_snapshot"],
                    "action_signals": [],
                    "verify_signals": ["ui_get_snapshot"],
                },
                "page_workflow_state": {"has_active_surface": True},
                "page_workflow_completion": {
                    "mode": "verify_only",
                    "completion_signals": ["ui_get_snapshot"],
                    "action_signals": [],
                    "verify_signals": ["ui_get_snapshot"],
                },
                "page_workflow_progress": {
                    "status": "verify_pending",
                    "continuation_required": True,
                    "mode": "verify_only",
                    "workflow_stage": "verify_navigation_result",
                    "workflow_phase": "verify",
                    "workflow_goal": "navigation",
                    "completion_signals": ["ui_get_snapshot"],
                    "action_signals": [],
                    "verify_signals": ["ui_get_snapshot"],
                    "matched_completion_signals": [],
                    "matched_action_signals": [],
                    "matched_verify_signals": [],
                },
            },
        ),
        messages_have_blocking_pending_interaction=lambda _messages: False,
        first_incomplete_requested_family=lambda _ordered, _completed: None,
        allowed_tool_names_for_family=lambda _family, _tools, _input: [],
        conversation_id=42,
    )

    assert session.forced_tool_names == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    assert len(messages) == 1
    assert input_variables["_runtime_intent_facts"]["active_intent_kind"] == (
        "page_workflow"
    )
    assert "page_workflow_intent_alias" not in input_variables["_runtime_intent_facts"]
    runtime_intent = input_variables["_runtime_intent_plan"][0]
    assert runtime_intent["status"] == "pending"
    assert runtime_intent["allowed_tool_names"] == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    assert runtime_intent["preferred_tool_names"] == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
    ]
    assert runtime_intent["metadata"]["page_workflow_progress"]["status"] == (
        "verify_pending"
    )
    assert runtime_intent["metadata"]["page_workflow_kind"] == "page_workflow"
    assert "page_workflow_intent_alias" not in runtime_intent["metadata"]
    assert runtime_intent["metadata"]["page_no_progress_recovery"] == {
        "reason": "page_snapshot_only_round",
        "allowed_tool_names": [
            "ui_list_interactables",
            "ui_click",
            "ui_open_surface",
        ],
        "round_tool_names": ["ui_get_snapshot"],
    }


def test_build_tool_loop_session_uses_prepared_runtime_intent_plan() -> None:
    response = ChatResponse(message=ChatMessage(role="assistant", content="done"))
    session = build_tool_loop_session(
        response=response,
        tools=[_tool("ui_get_snapshot")],
        all_tools=[_tool("ui_get_snapshot"), _tool("web_search")],
        request=type(
            "Request",
            (),
            {
                "tool_use_policy": None,
                "intent_plan": [],
                "input_variables": {
                    "_runtime_intent_plan": [
                        {
                            "intent_id": "intent-1",
                            "kind": "page_summary",
                            "family": "page_ops",
                            "order": 1,
                            "user_visible_label": "page_summary",
                            "source_text": "看看当前页面",
                        },
                        {
                            "intent_id": "intent-2",
                            "kind": "web_research",
                            "family": "web_research",
                            "order": 2,
                            "user_visible_label": "web_research",
                            "source_text": "再搜一下官网",
                        },
                    ]
                },
            },
        )(),
        continuation_context=None,
        tool_use_policy=None,
        execution_budget=None,
        starting_total_tokens=None,
        starting_completion_tokens=None,
        ordered_requested_families_from_intents=lambda **kwargs: [
            (
                intent.get("family")
                if isinstance(intent, dict)
                else getattr(intent, "family", None)
            )
            for intent in kwargs["intents"]
        ],
    )

    assert session.ordered_requested_families == ["page_ops", "web_research"]
