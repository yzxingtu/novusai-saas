"""
Test type: structural / behavioral
Scope: context-engine capability awareness, runtime inventory, and prompt additions.
Mocked dependencies: Static config, KB/RAG IO, model-capability lookup, and intent
planner fixtures are mocked so tests cover downstream context assembly behavior.
"""

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


def _build_shortcircuit_intent_plan(kind: str = "direct_reply") -> list[IntentPlan]:
    return [
        IntentPlan(
            intent_id="intent-shortcircuit",
            kind=kind,
            family="none",
            order=1,
            user_visible_label=kind,
            source_text="capability self-report",
            requires_tools=False,
            allow_text_response=True,
            shortcircuit=True,
            metadata={},
        )
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
    """
    中文: 测试类型 behavioral；验证 mapping 形态的技能描述会被注入能力块。
    EN: Test type behavioral; mapping-shaped skill descriptions reach the block.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 固定输入，prompt 渲染走真实逻辑。
    EN: Config, KB, RAG, and model-capability IO are fixed fixtures; rendering is real.
    """
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

    assert "[RUNTIME CAPABILITIES]" in assembly.messages[0].content
    assert "Mapping Skills" in assembly.messages[0].content
    assert "mapped_tool: Mapping item" in assembly.messages[0].content
    assert any(
        "[RUNTIME CAPABILITIES]" in addition
        for addition in (assembly.system_prompt_additions or [])
    )
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_injected"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == ["skills"]
    assert "dynamic_capability_awareness_error" not in assembly.diagnostics


@pytest.mark.asyncio
async def test_context_engine_injects_live_selected_skill_capability_descriptions() -> (
    None
):
    """
    中文: 测试类型 behavioral；本轮显式选择的 live skill 会通过真实 builder 注入能力块。
    EN: Test type behavioral; live selected skills reach the capability block through the real builder.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 与 intent fixture；builder 与 activation 走真实逻辑。
    EN: Config, KB, RAG, model-capability IO, and intent fixture are mocked; builder and activation are real.
    """
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="capability_pack",
            source="skill_package:mapper",
            description="Map intents to capabilities",
            metadata={"family": "general", "has_execution_tools": True},
        ),
        CapabilityDescriptor(
            name="catalog_only",
            kind="capability_pack",
            source="skill_package:catalog",
            description="Catalog metadata only",
            metadata={"family": "general", "has_execution_tools": False},
        ),
    )

    assembly = await _assemble_context(
        request=_build_request(
            messages=[ChatMessage(role="user", content="帮我规划这轮任务")],
            selected_skill_names=["intent_mapper"],
        ),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    assert "[RUNTIME CAPABILITIES]" in assembly.messages[0].content
    assert "General Skills" in assembly.messages[0].content
    assert "intent_mapper: Map intents to capabilities" in assembly.messages[0].content
    assert "catalog_only" not in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == ["skills"]


@pytest.mark.asyncio
async def test_context_engine_does_not_inject_unactivated_skill_inventory() -> None:
    """
    中文: 测试类型 behavioral；普通回合不会把全量授权技能库存注入 system prompt。
    EN: Test type behavioral; ordinary turns do not inject the full authorized skill inventory.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 与 intent fixture；builder 与 activation 走真实逻辑。
    EN: Config, KB, RAG, model-capability IO, and intent fixture are mocked; builder and activation are real.
    """
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="capability_pack",
            source="skill_package:mapper",
            description="Map intents to capabilities",
            metadata={"family": "general", "has_execution_tools": True},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(
            messages=[ChatMessage(role="user", content="帮我写一段欢迎语")],
        ),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    assert "[RUNTIME CAPABILITIES]" not in assembly.messages[0].content
    assert (
        "intent_mapper: Map intents to capabilities" not in assembly.messages[0].content
    )
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_injected"] is False
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == []


@pytest.mark.asyncio
async def test_context_engine_injects_self_report_skills_despite_shortcircuit() -> None:
    """
    中文: 测试类型 behavioral；能力自报短路回合仍注入当前可描述的技能能力。
    EN: Test type behavioral; capability self-report shortcircuit turns still inject skill descriptions.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 与 direct-reply intent fixture；builder 与 activation 走真实逻辑。
    EN: Config, KB, RAG, model-capability IO, and direct-reply intent fixture are mocked; builder and activation are real.
    """
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="capability_pack",
            source="skill_package:mapper",
            description="Map intents to capabilities",
            metadata={"family": "general", "has_execution_tools": True},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(
            messages=[ChatMessage(role="user", content="你有哪些能力")],
        ),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
        intent_plan=_build_shortcircuit_intent_plan(),
    )

    assert assembly.diagnostics["intent_plan"][0]["shortcircuit"] is True
    assert "[RUNTIME CAPABILITIES]" in assembly.messages[0].content
    assert "intent_mapper: Map intents to capabilities" in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_injected"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == ["skills"]


@pytest.mark.asyncio
async def test_context_engine_injects_limited_knowledge_base_capabilities() -> None:
    """
    中文: 测试类型 behavioral；租户风格和最大条目数会塑造注入的知识库能力文本。
    EN: Test type behavioral; tenant style and item limits shape injected KB text.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 固定输入，prompt 渲染走真实逻辑。
    EN: Config, KB, RAG, and model-capability IO are fixed fixtures; rendering is real.
    """
    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(
            capability_description_style="concise",
            max_capability_items_per_category=1,
        ),
        kb_ids=[101, 202],
        kb_bindings=[
            {
                "kb_id": 101,
                "kb_name": "产品文档库",
                "kb_description": "包含产品手册与 API 文档",
                "kb_document_count": 12,
            },
            {
                "kb_id": 202,
                "kb_name": "内部政策库",
                "kb_description": "包含审批制度",
                "kb_document_count": 8,
            },
        ],
        intent_plan=_build_intent_plan("knowledge_query"),
    )

    assert "[RUNTIME CAPABILITIES]" in assembly.messages[0].content
    assert "产品文档库" in assembly.messages[0].content
    assert "包含产品手册与 API 文档" not in assembly.messages[0].content
    assert "内部政策库" not in assembly.messages[0].content
    assert "Additional items omitted by tenant limit: 1" in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_injected"] is True
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == [
        "knowledge_bases"
    ]
    assert "knowledge_base" in assembly.diagnostics["context_source_kinds"]


@pytest.mark.asyncio
async def test_context_engine_does_not_inject_capability_block_when_disabled() -> None:
    """
    中文: 测试类型 behavioral；关闭租户能力感知后不会注入运行时能力块。
    EN: Test type behavioral; disabled tenant awareness leaves capability text absent.
    中文: Mock 的是配置、知识库、RAG、模型能力 IO 固定输入，prompt 渲染走真实逻辑。
    EN: Config, KB, RAG, and model-capability IO are fixed fixtures; rendering is real.
    """
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="capability_pack",
            source="skill_package:mapper",
            description="Map intents to capabilities",
            metadata={"family": "general", "has_execution_tools": True},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(
            enable_dynamic_capability_awareness=False,
        ),
        intent_plan=_build_intent_plan("assistant_response"),
    )

    assert "[RUNTIME CAPABILITIES]" not in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is False
    assert assembly.diagnostics["dynamic_capability_awareness_injected"] is False
    assert assembly.diagnostics["dynamic_capability_awareness_categories"] == []


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
