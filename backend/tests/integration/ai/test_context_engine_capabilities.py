from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.capabilities.description_builder import CapabilityDescriptionBuilder
from app.ai.context.contributors.memory import MemoryContextContribution
from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.types import (
    ExecutionRequest,
    IntentPlan,
)
from app.ai.runtime.context_capability_bridge import DefaultContextCapabilityBridge
from app.ai.runtime.types import CapabilityDescriptor
from app.ai.skills.resolver import SkillResolveResult
from app.ai.types import ChatMessage
from app.services.ai.capability_awareness_config import (
    TenantCapabilityAwarenessSettings,
)


class _BaseEngineStub:
    @staticmethod
    def _build_system_message(agent, input_variables=None):
        _ = input_variables
        return ChatMessage(role="system", content=agent.system_prompt or "")

    @staticmethod
    def _extract_last_user_text(messages):
        for message in reversed(messages):
            if message.role == "user":
                return message.content or ""
        return ""

    @staticmethod
    def _extract_recent_successful_tool_names(messages):
        _ = messages
        return []

    @staticmethod
    def _looks_like_generic_follow_up(text):
        _ = text
        return False


def _build_agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Researcher",
        system_prompt="You are helpful.",
        rag_config=None,
        context_config=None,
        model=None,
    )


def _build_request(**overrides) -> ExecutionRequest:
    payload = {
        "agent_id": 1,
        "tenant_id": 7,
        "user_id": 3,
        "messages": [ChatMessage(role="user", content="请总结一下当前能力")],
        "input_variables": {},
        "memory_enabled": False,
        "long_term_memory_enabled": False,
    }
    payload.update(overrides)
    return ExecutionRequest(**payload)


def _build_skill_result(*descriptors: CapabilityDescriptor) -> SkillResolveResult:
    return SkillResolveResult(capability_descriptors=list(descriptors))


def _build_intent_plan(*kinds: str) -> list[IntentPlan]:
    def _family_for_kind(kind: str) -> str:
        if kind == "knowledge_query":
            return "knowledge"
        return "none"

    return [
        IntentPlan(
            intent_id=f"intent-{index}",
            kind=kind,
            family=_family_for_kind(kind),
            order=index,
            user_visible_label=kind,
            source_text="test intent",
            shortcircuit=False,
            metadata={},
        )
        for index, kind in enumerate(kinds, start=1)
    ]


async def _assemble_context(
    *,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    settings: TenantCapabilityAwarenessSettings,
    kb_ids: list[int] | None = None,
    kb_bindings: list[dict[str, object]] | None = None,
    intent_plan: list[IntentPlan] | None = None,
):
    context_engine = ConversationContextEngine(
        db=object(),
        base_engine=_BaseEngineStub(),
    )

    async def _fake_inject_rag_context(
        _db,
        _agent,
        messages,
        _tenant_id,
        **_kwargs,
    ):
        return messages, []

    with (
        patch(
            "app.ai.runtime.context_capability_bridge.get_tenant_capability_awareness_settings",
            new=AsyncMock(return_value=settings),
        ),
        patch.object(
            DefaultContextCapabilityBridge,
            "resolve_runtime_model_capabilities",
            new=AsyncMock(return_value={"supports_audio": False}),
        ),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=(kb_ids or [], {})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(side_effect=_fake_inject_rag_context),
        ),
        patch(
            "app.services.ai.agent_kb_binding_service.AgentKBBindingService.get_agent_kb_bindings_with_metadata",
            new=AsyncMock(return_value=kb_bindings or []),
        ),
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=list(intent_plan or []),
        ),
    ):
        return await context_engine.assemble(
            _build_agent(),
            request,
            skill_result=skill_result,
        )


def _build_mapping_skill_descriptions(*_args, **_kwargs):
    class MappingDescriptor:
        def __init__(self):
            self.category = "skills"
            self.title = "Mapping Skills"

        def items(self):
            return ["mapped_tool: Mapping item"]

    return [MappingDescriptor()]


@pytest.mark.asyncio
async def test_context_engine_ignores_invalid_runtime_context_for_page_turns() -> None:
    """
    Test type: structural
    Scope: page-shaped user text does not synthesize current-page runtime tools.
    """
    assembly = await _assemble_context(
        request=_build_request(
            messages=[ChatMessage(role="user", content="帮我看一下当前页面")],
        ),
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("record_summary"),
    )

    assert assembly.capability_bundle is not None
    assert assembly.capability_bundle.selected_skill_names == []
    assert assembly.diagnostics["selected_skill_names"] == []
    assert not any(
        tool.name.startswith("ui_") for tool in assembly.capability_bundle.tools
    )
    assert "page_context" not in assembly.diagnostics["context_source_kinds"]


@pytest.mark.asyncio
async def test_context_engine_only_surfaces_session_memory_context_source_when_injected() -> (
    None
):
    inactive_assembly = await _assemble_context(
        request=_build_request(memory_enabled=True, session_memory_injected=False),
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    inactive_kinds = {
        source.kind
        for source in (
            inactive_assembly.capability_bundle or SimpleNamespace(context_sources=[])
        ).context_sources
    }
    assert "session_memory" not in inactive_kinds

    active_assembly = await _assemble_context(
        request=_build_request(memory_enabled=True, session_memory_injected=True),
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    active_sources = list(
        (
            active_assembly.capability_bundle or SimpleNamespace(context_sources=[])
        ).context_sources
    )
    session_sources = [
        source for source in active_sources if source.kind == "session_memory"
    ]
    assert len(session_sources) == 1
    assert session_sources[0].active is True
    assert session_sources[0].metadata.get("injected") is True


@pytest.mark.asyncio
async def test_context_engine_enables_long_term_memory_recall_on_generic_turns() -> (
    None
):
    memory_contribution = MemoryContextContribution(
        memory_recalled=True,
        memory_recall_slice={"count": 2, "scope_type": "user_agent"},
        memory_injected=True,
    )

    with patch(
        "app.ai.context.contributors.memory.MemoryContributor.contribute",
        new=AsyncMock(return_value=memory_contribution),
    ) as contribute_mock:
        assembly = await _assemble_context(
            request=_build_request(
                memory_enabled=True,
                long_term_memory_enabled=True,
            ),
            skill_result=None,
            settings=TenantCapabilityAwarenessSettings(),
            intent_plan=_build_intent_plan("assistant_response"),
        )

    contribute_kwargs = contribute_mock.await_args.kwargs
    assert contribute_kwargs["enabled"] is True
    assert contribute_kwargs["should_run_memory_profile"] is False
    assert contribute_kwargs["should_run_memory_vector_recall"] is True
    assert assembly.memory_recalled is True
    assert assembly.capability_bundle is not None
    assert {
        source.kind
        for source in assembly.capability_bundle.context_sources
        if source.active
    } >= {"long_term_memory"}


@pytest.mark.asyncio
async def test_context_engine_handles_mapping_description_inputs() -> None:
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="capability_pack",
            source="skill_package:mapper",
            description="Map intents to capabilities",
            metadata={"family": "general"},
        )
    )

    with patch.object(
        CapabilityDescriptionBuilder,
        "build_skill_descriptions",
        new=_build_mapping_skill_descriptions,
    ):
        assembly = await _assemble_context(
            request=_build_request(),
            skill_result=skill_result,
            settings=TenantCapabilityAwarenessSettings(),
            intent_plan=_build_intent_plan("assistant_response"),
        )

    assert "[CAPABILITIES]" not in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == ["skills"]
    assert "dynamic_capability_awareness_error" not in assembly.diagnostics


@pytest.mark.asyncio
async def test_context_engine_tracks_knowledge_base_capabilities_without_prompt_injection() -> (
    None
):
    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
        kb_ids=[101],
        kb_bindings=[
            {
                "kb_id": 101,
                "kb_name": "产品文档库",
                "kb_description": "包含产品手册与 API 文档",
                "kb_document_count": 12,
            }
        ],
        intent_plan=_build_intent_plan("knowledge_query"),
    )

    assert "[CAPABILITIES]" not in assembly.messages[0].content
    assert not any(
        "[CAPABILITIES]" in addition
        for addition in (assembly.system_prompt_additions or [])
    )
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == [
        "knowledge_bases"
    ]
    assert "knowledge_base" in assembly.diagnostics["context_source_kinds"]


@pytest.mark.asyncio
async def test_context_engine_injects_visible_output_locale_for_non_page_turns() -> (
    None
):
    request = _build_request(
        messages=[
            ChatMessage(
                role="user",
                content="How is the weather in Shanghai today?",
            )
        ],
        input_variables={},
    )

    assembly = await _assemble_context(
        request=request,
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    additions = " ".join(assembly.system_prompt_additions or [])
    assert "VISIBLE OUTPUT LANGUAGE" in additions
    assert "English" in additions
    assert "zh_CN" not in additions
