"""
Test type: behavioral
Scope: system prompt helper rendering and live-turn runtime summary projection.
Mocked dependencies: none.
"""

from __future__ import annotations

from app.ai.engine.base import BaseEngine
from app.ai.engine.budget_helpers import budget_exit_response
from app.ai.engine.contract_diagnostics_helpers import (
    build_contract_recovery_system_message,
    merge_contract_diagnostics_into_turn_record,
)
from app.ai.engine.system_prompt_helpers import (
    build_system_message,
    deserialize_intent_plan,
    inject_runtime_summary,
    is_capability_reporting_query,
    resolve_capability_injection_decision,
)
from app.ai.engine.system_prompt_capability_hints import (
    build_runtime_capability_hint,
)
from app.ai.engine.types import IntentPlan
from app.ai.runtime.types import TurnRecord
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens


def test_build_system_message_renders_identity_and_variables() -> None:
    class _Agent:
        id = 123
        name = "KernelTestAgent"
        system_prompt = "Locale={{ locale }} Agent={{ agent_name }}"

    message = build_system_message(
        agent=_Agent(),
        input_variables={"locale": "zh-CN"},
    )
    assert message.role == "system"
    assert "KernelTestAgent" in message.content
    assert "Locale=zh-CN" in message.content


def test_base_engine_build_system_message_keeps_positional_facade() -> None:
    class _Agent:
        id = 456
        name = "FacadeAgent"
        system_prompt = "Locale={{ locale }} Agent={{ agent_name }}"

    message = BaseEngine._build_system_message(_Agent(), {"locale": "en-US"})

    assert message.role == "system"
    assert "FacadeAgent" in message.content
    assert "Locale=en-US" in message.content


def test_inject_runtime_summary_is_idempotent_for_same_signature() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [ToolDefinition(name="web_search")]
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="web_research",
            source_text="latest ai news",
        )
    ]

    injected_first = inject_runtime_summary(
        messages=messages,
        tools=tools,
        intent_plan=intents,
        execution_path="normal",
    )
    first_content = messages[0].content
    first_signature = (messages[0].metadata or {}).get("runtime_summary_signature")

    injected_second = inject_runtime_summary(
        messages=messages,
        tools=tools,
        intent_plan=intents,
        execution_path="normal",
    )

    assert injected_first is False
    assert injected_second is False
    assert messages[0].content == first_content
    assert (messages[0].metadata or {}).get(
        "runtime_summary_signature"
    ) == first_signature


def test_inject_runtime_summary_omits_retired_runtime_narration() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [
        ToolDefinition(name="web_search"),
        ToolDefinition(name="fetch_url"),
        ToolDefinition(name="ui_click"),
        ToolDefinition(name="ui_read_table"),
        ToolDefinition(name="ui_list_interactables"),
    ]
    before_tokens = estimate_tokens(messages[0].content)
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="page_workflow",
            family="page_ops",
            order=1,
            user_visible_label="page_workflow",
            source_text="搜索当前页面中的记录",
            allowed_tool_names=["ui_click", "ui_read_table", "ui_list_interactables"],
            preferred_tool_names=[
                "ui_click",
                "ui_read_table",
                "ui_list_interactables",
            ],
            metadata={
                "page_workflow_kind": "page_workflow",
                "page_workflow_goal": "search",
            },
        )
    ]
    inject_runtime_summary(
        messages=messages,
        tools=tools,
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher"],
            "selection_semantics": "turn_selected_subset",
            "selection_live": True,
            "live_turn_bound": True,
        },
        intent_plan=intents,
        execution_path="normal",
    )

    content = messages[0].content
    assert "[TOOL USAGE RULES]" not in content
    assert "[RESEARCH STATE]" not in content
    assert "[PAGE OPERATIONS]" not in content
    assert "[ORDERED CAPABILITY INTENT]" not in content
    assert "Budgets:" not in content
    assert "Prefer the smallest tool sequence" not in content
    assert "Stop after reporting completed work" not in content
    assert "Knowledge-base context is available this turn." not in content
    assert "Page context is available this turn." not in content
    assert "Memory context may already be attached this turn." not in content
    assert "runtime.path=normal" in content
    assert "runtime.intents=page_workflow" in content
    assert (
        "runtime.tools=web_search, fetch_url, ui_click, ui_read_table, "
        "ui_list_interactables" in content
    )
    assert "runtime.selected_skills=browser, researcher" in content
    assert estimate_tokens(content) - before_tokens <= 120


def test_build_runtime_capability_hint_ignores_inventory_shaped_summary() -> None:
    hint = build_runtime_capability_hint(
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher"],
            "selection_semantics": "capability_reporting_inventory",
            "selection_live": False,
            "live_turn_bound": False,
        }
    )

    assert hint == ""


def test_inject_runtime_summary_ignores_inventory_shaped_selected_skills() -> None:
    messages = [ChatMessage(role="system", content="SYS")]
    tools = [ToolDefinition(name="web_search")]

    injected = inject_runtime_summary(
        messages=messages,
        tools=tools,
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher"],
            "selection_semantics": "capability_reporting_inventory",
            "selection_live": False,
            "live_turn_bound": False,
        },
        execution_path="normal",
    )

    assert injected is False
    assert "runtime.path=normal" in messages[0].content
    assert "runtime.selected_skills=" not in messages[0].content


def test_contract_diagnostics_helpers_populate_turn_record_metadata() -> None:
    turn_record = TurnRecord()
    merged = merge_contract_diagnostics_into_turn_record(
        turn_record,
        breach_type="assistant_claimed_tool_call_without_tool_event",
        diagnostics={
            "tool_leak_detected": True,
            "assistant_claimed_tool_call_without_tool_event": True,
            "unfinished_intents": ["web_research"],
            "leaked_tool_names": ["fetch_url"],
        },
        recovered_via_retry=True,
    )
    assert isinstance(merged, TurnRecord)
    assert (
        merged.metadata["contract_breach_type"]
        == "assistant_claimed_tool_call_without_tool_event"
    )
    assert merged.metadata["tool_leak_detected"] is True
    assert merged.metadata["recovered_via_retry"] is True
    assert merged.metadata["leaked_tool_names"] == ["fetch_url"]


def test_base_engine_wrappers_delegate_to_extracted_helpers() -> None:
    message = build_contract_recovery_system_message(
        breach_type="assistant_claimed_tool_call_without_tool_event",
        diagnostics={
            "unfinished_intents": ["web_research"],
            "completed_intents": [],
            "leaked_tool_names": ["web_search"],
        },
    )
    assert message.role == "system"
    assert message.internal_only is True
    assert BaseEngine._is_capability_reporting_query("你能做什么")
    assert is_capability_reporting_query("what can you do this turn")
    assert BaseEngine._intent_completion_signals(
        "web_research",
        allowed_tool_names=["fetch_url", "web_search"],
        preferred_tool_names=[],
    ) == ["fetch_url"]
    response = BaseEngine._budget_exit_response(total_tokens=42)
    helper_response = budget_exit_response(total_tokens=42)
    assert response.total_tokens == 42
    assert response.message.role == "assistant"
    assert helper_response.message.content == ""


def test_page_submit_completion_signals_follow_state_machine_contract() -> None:
    assert BaseEngine._intent_completion_signals(
        "page_ops",
        intent_kind="page_workflow",
        allowed_tool_names=[
            "ui_get_form_state",
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ],
        preferred_tool_names=[
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ],
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "form_write",
            "page_workflow_phase": "submit",
            "page_workflow_completion": {
                "mode": "verify_only",
                "completion_signals": ["ui_submit_form"],
                "action_signals": [],
                "verify_signals": ["ui_submit_form"],
            },
        },
    ) == ["ui_submit_form"]


def test_page_workflow_completion_signals_follow_canonical_goal_metadata() -> None:
    assert BaseEngine._intent_completion_signals(
        "page_ops",
        intent_kind="page_workflow",
        allowed_tool_names=[
            "ui_get_form_state",
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ],
        preferred_tool_names=[
            "ui_fill_form",
            "ui_set_field",
            "ui_submit_form",
        ],
        intent_metadata={
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": "form_write",
            "page_workflow_phase": "submit",
            "page_workflow_completion": {
                "mode": "verify_only",
                "completion_signals": ["ui_submit_form"],
                "action_signals": [],
                "verify_signals": ["ui_submit_form"],
            },
        },
    ) == ["ui_submit_form"]


def test_deserialize_intent_plan_filters_invalid_entries() -> None:
    raw = [
        {
            "intent_id": "intent-1",
            "kind": "web_research",
            "family": "web_research",
            "order": 1,
            "user_visible_label": "web_research",
            "source_text": "latest ai news",
        },
        "not-a-dict",
    ]

    intents = deserialize_intent_plan(raw)

    assert len(intents) == 1
    assert intents[0].intent_id == "intent-1"


def test_resolve_capability_injection_decision_sets_context_flags() -> None:
    class _Source:
        def __init__(self, kind: str, active: bool = True) -> None:
            self.kind = kind
            self.active = active

    decision = resolve_capability_injection_decision(
        diagnostics={},
        intent_flags={
            "all_shortcircuit": False,
            "has_page_intent": True,
            "has_knowledge_intent": False,
            "has_memory_intent": False,
            "memory_context_enabled": False,
        },
        context_sources=[_Source("page_context")],
        capability_summary_injected=True,
    )

    assert decision["all_shortcircuit"] is False
    assert decision["page_injected"] is True
    assert decision["kb_injected"] is False
    assert decision["memory_injected"] is False
    assert decision["skills_injected"] is False


