from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.context.assembly_initial_support import (
    assemble_initial_context_state,
    resolve_knowledge_base_selection,
)
from app.ai.runtime.context_assembler import (
    ContextAssembler,
    ContextCapabilityBundleProjection,
)
from app.ai.runtime.context_capability_bridge import DefaultContextCapabilityBridge
from app.ai.runtime.contracts import ContextCapabilityInputs
from app.ai.runtime.types import CapabilityBundle, CapabilityDescriptor
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


class _PromptBridgeStub:
    @staticmethod
    def _build_system_message(agent, input_variables=None):
        _ = input_variables
        return ChatMessage(role="system", content=f"system:{agent.id}")

    @staticmethod
    def _build_web_research_continuation_context(
        messages,
        all_tools,
        input_variables=None,
    ):
        return {
            "message_count": len(messages),
            "tool_names": [getattr(tool, "name", "") for tool in all_tools],
            "input_variables": dict(input_variables or {}),
        }


def test_resolve_knowledge_base_selection_merges_and_drops() -> None:
    selection = resolve_knowledge_base_selection(
        request_kb_ids=[3, 5, 8],
        agent_kb_ids=[1, 5, 9],
        agent_kb_weights={1: 0.3, 5: 0.7, 9: 1.0},
    )

    assert selection.requested_kb_ids == [3, 5, 8]
    assert selection.merged_kb_ids == [5]
    assert selection.dropped_kb_ids == [3, 8]
    assert selection.agent_kb_weights == {1: 0.3, 5: 0.7, 9: 1.0}


def test_resolve_knowledge_base_selection_falls_back_to_agent_when_no_overlap() -> None:
    selection = resolve_knowledge_base_selection(
        request_kb_ids=[77],
        agent_kb_ids=[10, 11],
        agent_kb_weights={10: 1.0, 11: 0.5},
    )

    assert selection.requested_kb_ids == [77]
    assert selection.merged_kb_ids == [10, 11]
    assert selection.dropped_kb_ids == [77]


@pytest.mark.asyncio
async def test_assemble_initial_context_state_keeps_bundle_and_flags() -> None:
    capability_bridge = SimpleNamespace(
        resolve_runtime_model_capabilities=AsyncMock(
            return_value={"supports_audio": True}
        ),
        build_provisional_bundle=MagicMock(
            return_value=CapabilityBundle(
                tools=[ToolDefinition(name="web_search", description="Search")]
            )
        ),
    )
    agent = SimpleNamespace(id=7)
    request = SimpleNamespace(
        tenant_id=9,
        knowledge_base_ids=[2, 3],
        messages=[ChatMessage(role="user", content="hello")],
        input_variables={"page": "home"},
    )
    captured: dict[str, object] = {}

    def _plan_turn(**kwargs):
        captured["plan_kwargs"] = kwargs
        return [SimpleNamespace(kind="knowledge_query", shortcircuit=False)]

    def _intent_flags(intent_plan, active_request):
        captured["intent_plan"] = intent_plan
        captured["request"] = active_request
        return {
            "all_shortcircuit": False,
            "has_knowledge_intent": True,
            "has_memory_intent": False,
            "memory_context_enabled": False,
            "has_page_intent": False,
        }

    result = await assemble_initial_context_state(
        db=object(),
        agent=agent,
        request=request,
        skill_result=None,
        prompt_bridge=_PromptBridgeStub(),
        capability_bridge=capability_bridge,
        load_agent_kb_bindings_fn=AsyncMock(return_value=([1, 2], {1: 0.2, 2: 0.8})),
        intent_plan_callable=_plan_turn,
        intent_flag_resolver=_intent_flags,
    )

    capability_bridge.resolve_runtime_model_capabilities.assert_awaited_once_with(
        agent=agent
    )
    capability_bridge.build_provisional_bundle.assert_called_once()
    assert result.messages[0].content == "system:7"
    assert result.messages[1].content == "hello"
    assert result.kb_selection.requested_kb_ids == [2, 3]
    assert result.kb_selection.merged_kb_ids == [2]
    assert result.kb_selection.dropped_kb_ids == [3]
    assert result.runtime_model_capabilities == {"supports_audio": True}
    assert isinstance(result.provisional_capability_inputs, ContextCapabilityInputs)
    assert result.provisional_bundle.selected_tool_names == ["web_search"]
    assert result.intent_flags["has_knowledge_intent"] is True
    assert result.capability_injection_decision["all_shortcircuit"] is False
    assert result.capability_injection_decision["kb_injected"] is False
    assert captured["plan_kwargs"]["tools"][0].name == "web_search"
    assert captured["request"] is request


@pytest.mark.asyncio
async def test_assemble_initial_context_state_rebuilds_provisional_bundle_from_turn_activation() -> (
    None
):
    capability_bridge = DefaultContextCapabilityBridge(
        context_assembler=ContextAssembler(),
        bundle_projection=ContextCapabilityBundleProjection(),
    )
    capability_bridge.resolve_runtime_model_capabilities = AsyncMock(
        return_value={"supports_audio": False}
    )
    agent = SimpleNamespace(id=11)
    request = SimpleNamespace(
        tenant_id=9,
        knowledge_base_ids=[],
        messages=[
            ChatMessage(
                role="user",
                content="Please use Plugin Page Skill to inspect this page.",
            )
        ],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.dashboard",
                "ui_epoch": 5,
            }
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                description="Search the web",
                config={"auto_injected": True, "builtin_type": "web_search"},
                source_skill_name="web_search",
                source_skill_type="builtin",
            ),
            ToolDefinition(
                name="ui_get_snapshot",
                description="Get UI snapshot",
                source_skill_id=12,
                source_skill_name="Plugin Page Skill",
                source_skill_type="plugin",
                source_package_name="plugin.page",
            ),
            ToolDefinition(
                name="ui_click",
                description="Click UI element",
                source_skill_id=12,
                source_skill_name="Plugin Page Skill",
                source_skill_type="plugin",
                source_package_name="plugin.page",
            ),
            ToolDefinition(
                name="fetch_url",
                description="Fetch a webpage",
                source_skill_id=13,
                source_skill_name="Plugin Research Skill",
                source_skill_type="plugin",
                source_package_name="plugin.research",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="web_search",
                kind="capability_pack",
                source="system_baseline_builtin",
                metadata={
                    "auto_injected": True,
                    "resolved_tool_names": ["web_search"],
                    "resolved_tool_count": 1,
                    "has_execution_tools": True,
                },
            ),
            CapabilityDescriptor(
                name="Plugin Page Skill",
                kind="capability_pack",
                source="skill_package:plugin.page",
                metadata={
                    "resolved_tool_names": ["ui_get_snapshot", "ui_click"],
                    "resolved_tool_count": 2,
                    "has_execution_tools": True,
                },
            ),
            CapabilityDescriptor(
                name="Plugin Research Skill",
                kind="capability_pack",
                source="skill_package:plugin.research",
                metadata={
                    "resolved_tool_names": ["fetch_url"],
                    "resolved_tool_count": 1,
                    "has_execution_tools": True,
                },
            ),
        ],
    )
    planned_tool_name_calls: list[list[str]] = []

    def _plan_turn(**kwargs):
        tool_names = [tool.name for tool in kwargs["tools"]]
        planned_tool_name_calls.append(tool_names)
        if "ui_get_snapshot" in tool_names:
            return [SimpleNamespace(kind="page_summary", shortcircuit=False)]
        return [SimpleNamespace(kind="direct_reply", shortcircuit=False)]

    def _intent_flags(intent_plan, active_request):
        _ = active_request
        kinds = {
            str(getattr(intent, "kind", "") or "").strip() for intent in intent_plan
        }
        return {
            "all_shortcircuit": False,
            "has_knowledge_intent": False,
            "has_memory_intent": False,
            "memory_context_enabled": False,
            "has_page_intent": any(kind.startswith("page_") for kind in kinds),
            "has_web_research_intent": "web_research" in kinds,
        }

    result = await assemble_initial_context_state(
        db=object(),
        agent=agent,
        request=request,
        skill_result=skill_result,
        prompt_bridge=_PromptBridgeStub(),
        capability_bridge=capability_bridge,
        load_agent_kb_bindings_fn=AsyncMock(return_value=([], {})),
        intent_plan_callable=_plan_turn,
        intent_flag_resolver=_intent_flags,
    )

    assert planned_tool_name_calls == [
        ["web_search", "ui_get_snapshot", "ui_click", "fetch_url"],
        ["web_search", "ui_get_snapshot", "ui_click"],
    ]
    assert [tool.name for tool in result.provisional_bundle.tools] == [
        "web_search",
        "ui_get_snapshot",
        "ui_click",
    ]
    assert result.provisional_bundle.selected_tool_names == [
        "web_search",
        "ui_get_snapshot",
        "ui_click",
    ]
    assert result.provisional_bundle.selected_skill_names == ["Plugin Page Skill"]
    assert result.provisional_continuation_context["tool_names"] == [
        "web_search",
        "ui_get_snapshot",
        "ui_click",
    ]
