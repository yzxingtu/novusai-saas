"""
Test type: behavioral
Scope: system prompt helper rendering and live-turn runtime summary projection.
Mocked dependencies: none.
"""

from __future__ import annotations

from app.ai.engine.base import BaseEngine
from app.ai.engine.system_prompt_capability_hints import (
    build_runtime_capability_hint,
)
from app.ai.engine.system_prompt_helpers import (
    build_system_message,
    resolve_capability_injection_decision,
    should_skip_capability_summary,
)


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


def test_build_runtime_capability_hint_renders_live_selected_skills() -> None:
    """
    中文: 测试类型 behavioral；本轮选中技能通过运行时契约渲染。
    EN: Test type behavioral; live-turn selected skills render via the runtime contract.
    中文: 无 mock。
    EN: No mocks.
    """
    hint = build_runtime_capability_hint(
        runtime_capability_summary={
            "selected_skill_names": ["browser", "researcher"],
            "selection_semantics": "turn_selected_subset",
            "selection_live": True,
            "live_turn_bound": True,
        }
    )

    assert "runtime.selected_skills=browser, researcher" in hint


def test_skip_capability_summary_requires_injected_skill_awareness() -> None:
    """
    中文: 测试类型 behavioral；空的动态能力感知不会压掉选中技能摘要。
    EN: Test type behavioral; empty dynamic awareness does not suppress skills.
    中文: 无 mock。
    EN: No mocks.
    """
    intent_flags = {"all_shortcircuit": False}

    assert (
        should_skip_capability_summary(
            diagnostics={
                "dynamic_capability_awareness_enabled": True,
                "dynamic_capability_awareness_injected": False,
                "dynamic_capability_awareness_categories": ["skills"],
            },
            intent_flags=intent_flags,
            force_capability_summary=False,
        )
        is False
    )
    assert (
        should_skip_capability_summary(
            diagnostics={
                "dynamic_capability_awareness_enabled": True,
                "dynamic_capability_awareness_injected": True,
                "dynamic_capability_awareness_categories": ["knowledge_bases"],
            },
            intent_flags=intent_flags,
            force_capability_summary=False,
        )
        is False
    )
    assert (
        should_skip_capability_summary(
            diagnostics={
                "dynamic_capability_awareness_enabled": True,
                "dynamic_capability_awareness_injected": True,
                "dynamic_capability_awareness_categories": ["skills"],
            },
            intent_flags=intent_flags,
            force_capability_summary=False,
        )
        is True
    )


def test_trimmed_skill_awareness_does_not_suppress_selected_skill_summary() -> None:
    """
    中文: 测试类型 behavioral；被预算裁剪的动态技能块不能压掉旧技能摘要。
    EN: Test type behavioral; a trimmed dynamic skill block must keep skill summary fallback.
    中文: 无 mock。
    EN: No mocks.
    """
    assert (
        should_skip_capability_summary(
            diagnostics={
                "dynamic_capability_awareness_enabled": True,
                "dynamic_capability_awareness_injected": True,
                "dynamic_capability_awareness_categories": ["skills"],
                "context_budget": {
                    "trimmed_sections": ["dynamic_capability_awareness"],
                },
            },
            intent_flags={"all_shortcircuit": False},
            force_capability_summary=False,
        )
        is False
    )


def test_data_submit_completion_signals_use_allowed_record_tools() -> None:
    assert BaseEngine._intent_completion_signals(
        "data_ops",
        intent_kind="data_workflow",
        allowed_tool_names=[
            "crm_get_record_state",
            "crm_update_record",
            "crm_set_field",
            "crm_submit_record",
        ],
        preferred_tool_names=[
            "crm_update_record",
            "crm_set_field",
            "crm_submit_record",
        ],
        intent_metadata={
            "data_workflow_kind": "data_workflow",
            "data_workflow_goal": "form_write",
            "data_workflow_phase": "submit",
            "data_workflow_completion": {
                "mode": "verify_only",
                "completion_signals": ["crm_submit_record"],
                "action_signals": [],
                "verify_signals": ["crm_submit_record"],
            },
        },
    ) == [
        "crm_get_record_state",
        "crm_update_record",
        "crm_set_field",
        "crm_submit_record",
    ]


def test_data_workflow_completion_signals_use_allowed_record_tools() -> None:
    assert BaseEngine._intent_completion_signals(
        "data_ops",
        intent_kind="data_workflow",
        allowed_tool_names=[
            "crm_get_record_state",
            "crm_update_record",
            "crm_set_field",
            "crm_submit_record",
        ],
        preferred_tool_names=[
            "crm_update_record",
            "crm_set_field",
            "crm_submit_record",
        ],
        intent_metadata={
            "data_workflow_kind": "data_workflow",
            "data_workflow_goal": "form_write",
            "data_workflow_phase": "submit",
            "data_workflow_completion": {
                "mode": "verify_only",
                "completion_signals": ["crm_submit_record"],
                "action_signals": [],
                "verify_signals": ["crm_submit_record"],
            },
        },
    ) == [
        "crm_get_record_state",
        "crm_update_record",
        "crm_set_field",
        "crm_submit_record",
    ]


def test_resolve_capability_injection_decision_does_not_advertise_page_context() -> (
    None
):
    """
    Test type: structural
    Scope: page_context sources no longer set runtime prompt capability flags.
    """

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
    assert decision.get("page_injected", False) is False
    assert decision["kb_injected"] is False
    assert decision["memory_injected"] is False
    assert decision["skills_injected"] is False
