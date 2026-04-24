"""Test type: behavioral
Scope: tool-loop recovery projection and retired progress-hint behavior.
Mocked dependencies: none.
"""

from app.ai.engine.tool_loop_session import (
    ToolLoopSession,
    append_ordered_progress_hint,
    apply_round_recovery_and_focus,
    build_tool_loop_session,
    project_page_recovery_into_runtime_intent_plan,
)
from app.ai.engine.types import ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=name)


class _IntentStub:
    def __init__(
        self,
        *,
        intent_id: str,
        kind: str,
        family: str = "page_ops",
        status: str = "pending",
        metadata: dict | None = None,
        source_text: str = "",
    ) -> None:
        self.intent_id = intent_id
        self.kind = kind
        self.family = family
        self.status = status
        self.metadata = dict(metadata or {})
        self.source_text = source_text
        self.allowed_tool_names: list[str] = []
        self.preferred_tool_names: list[str] = []
        self.cached_result = None
        self.completed_by_tool_names: list[str] = []

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "kind": self.kind,
            "family": self.family,
            "status": self.status,
            "metadata": dict(self.metadata),
            "source_text": self.source_text,
            "allowed_tool_names": list(self.allowed_tool_names),
            "preferred_tool_names": list(self.preferred_tool_names),
            "completed_by_tool_names": list(self.completed_by_tool_names),
        }


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


def test_append_ordered_progress_hint_is_retired_noop() -> None:
    session = ToolLoopSession(
        current_response=ChatResponse(
            message=ChatMessage(role="assistant", content="done")
        ),
        tools_full=[_tool("ui_get_snapshot"), _tool("web_search")],
        all_tools_full=[_tool("ui_get_snapshot"), _tool("web_search")],
        effective_policy=ToolUsePolicy(),
        ordered_requested_families=["page_ops", "web_research"],
        has_fetch_url_in_toolset=False,
        total_tokens=0,
        completion_tokens_used=0,
        tracked_tool_rounds=0,
        tracked_tool_result_bytes=0,
        completed_families={"page_ops"},
    )
    messages = [ChatMessage(role="user", content="先看当前页面，再查一下官网")]

    append_ordered_progress_hint(
        session=session,
        messages=messages,
        all_tools=session.all_tools_full,
        input_variables={"page_context": {"page_key": "synthetic.runtime.records"}},
        build_ordered_capability_hint=lambda *_args: "Use the next tool family.",
    )

    assert [message.role for message in messages] == ["user"]
    assert session.issued_progress_hint_keys == set()


def test_project_page_recovery_targets_canonical_workflow_goal_before_legacy_kind() -> (
    None
):
    navigation_intent = _IntentStub(
        intent_id="intent-nav",
        kind="page_navigation",
        metadata={"page_workflow_goal": "navigation"},
        source_text="打开供应商页面",
    )
    search_intent = _IntentStub(
        intent_id="intent-search",
        kind="page_search",
        metadata={"page_workflow_goal": "search"},
        source_text="搜索发票",
    )
    input_variables: dict[str, object] = {}

    project_page_recovery_into_runtime_intent_plan(
        intent_plan=[navigation_intent, search_intent],
        input_variables=input_variables,
        recovery_diagnostics={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "search",
            "page_workflow_progress": {
                "status": "needs_retry",
                "continuation_required": True,
            },
        },
        recovery_tool_names=["ui_read_region"],
    )

    assert navigation_intent.allowed_tool_names == []
    assert search_intent.allowed_tool_names == ["ui_read_region"]
    assert search_intent.metadata["page_workflow_goal"] == "search"


def test_project_page_recovery_uses_legacy_kind_only_as_bounded_fallback() -> None:
    legacy_navigation_intent = _IntentStub(
        intent_id="intent-nav",
        kind="page_navigation",
        metadata={},
        source_text="打开供应商页面",
    )
    input_variables: dict[str, object] = {}

    project_page_recovery_into_runtime_intent_plan(
        intent_plan=[legacy_navigation_intent],
        input_variables=input_variables,
        recovery_diagnostics={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "navigation",
            "page_workflow_progress": {
                "status": "needs_retry",
                "continuation_required": True,
            },
        },
        recovery_tool_names=["ui_click"],
    )

    assert legacy_navigation_intent.allowed_tool_names == ["ui_click"]
    assert legacy_navigation_intent.metadata["page_workflow_goal"] == "navigation"
