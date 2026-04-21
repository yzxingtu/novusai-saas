from app.ai.engine.tool_loop_session import (
    ToolLoopSession,
    apply_round_recovery_and_focus,
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
            None,
            ["ui_list_interactables", "ui_click", "ui_open_surface"],
            {
                "reason": "page_snapshot_only_round",
                "intent_kind": "page_navigation",
                "round_tool_names": ["ui_get_snapshot"],
                "workflow_stage": "verify_navigation_result",
                "workflow_phase": "verify",
                "workflow_goal": "navigation",
                "workflow_state": {"has_active_surface": True},
                "workflow_completion": {
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
        "page_navigation"
    )
    runtime_intent = input_variables["_runtime_intent_plan"][0]
    assert runtime_intent["status"] == "pending"
    assert runtime_intent["metadata"]["page_workflow_progress"]["status"] == (
        "verify_pending"
    )
    assert runtime_intent["metadata"]["page_no_progress_recovery"] == {
        "reason": "page_snapshot_only_round",
        "allowed_tool_names": [
            "ui_list_interactables",
            "ui_click",
            "ui_open_surface",
        ],
        "round_tool_names": ["ui_get_snapshot"],
    }
