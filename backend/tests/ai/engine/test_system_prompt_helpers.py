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


def test_build_runtime_capability_hint_renders_discoverable_inventory() -> None:
    hint = build_runtime_capability_hint(
        runtime_capability_summary={
            "selected_skill_names": [],
            "inventory_skill_names": ["browser", "researcher"],
            "inventory_tool_names": ["browser_search"],
            "knowledge_base_names": ["产品文档库"],
            "memory_available": True,
            "selection_semantics": "turn_selected_subset",
            "selection_live": True,
            "live_turn_bound": True,
        }
    )

    assert '["browser","researcher"]' in hint
    assert '["browser_search"]' in hint
    assert '["产品文档库"]' in hint
    assert "memory_available=true" in hint
    assert "Only tools listed in runtime.tools are callable" in hint


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

    assert "[RUNTIME CAPABILITIES METADATA]" in hint
    assert '"browser","researcher"' in hint
    assert "runtime.selected_skills=" not in hint


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


def test_resolve_capability_injection_decision_uses_bound_kb_flag() -> None:
    """
    Test type: behavioral
    Scope: bound KB state, not knowledge intent classification, drives KB
    injection diagnostics.
    """

    class _Source:
        def __init__(self, kind: str, active: bool = True) -> None:
            self.kind = kind
            self.active = active

    decision = resolve_capability_injection_decision(
        diagnostics={},
        intent_flags={
            "all_shortcircuit": False,
            "has_bound_kb": True,
            "has_knowledge_intent": False,
            "has_memory_intent": False,
            "memory_context_enabled": False,
        },
        context_sources=[_Source("knowledge_base")],
        capability_summary_injected=True,
    )

    assert decision["kb_injected"] is True
