from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.capabilities.description_builder import CapabilityDescriptionBuilder
from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.types import ExecutionRequest
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


async def _assemble_context(
    *,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    settings: TenantCapabilityAwarenessSettings,
    kb_ids: list[int] | None = None,
    kb_bindings: list[dict[str, object]] | None = None,
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
            "app.ai.context.engine.get_tenant_capability_awareness_settings",
            new=AsyncMock(return_value=settings),
        ),
        patch(
            "app.ai.context.engine.resolve_runtime_model_capabilities",
            new=AsyncMock(return_value={}),
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
async def test_context_engine_injects_skill_capabilities_block() -> None:
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="web_search",
            kind="prompt_skill",
            source="skill_package:web",
            description="Search the public web for recent information",
            metadata={"family": "web_research"},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
    )

    assert "[CAPABILITIES]" in assembly.messages[0].content
    assert "## Web Research Skills" in assembly.messages[0].content
    assert "web_search: Search the public web for recent information" in (
        assembly.messages[0].content
    )
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is True


@pytest.mark.asyncio
async def test_context_engine_handles_mapping_description_inputs() -> None:
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="intent_mapper",
            kind="prompt_skill",
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
        )

    assert "## Mapping Skills" in assembly.messages[0].content
    assert "- mapped_tool: Mapping item" in assembly.messages[0].content


@pytest.mark.asyncio
async def test_context_engine_injects_knowledge_base_capabilities_block() -> None:
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
    )

    assert "## Knowledge Bases" in assembly.messages[0].content
    assert "产品文档库: 包含产品手册与 API 文档 (12 documents)" in (
        assembly.messages[0].content
    )


@pytest.mark.asyncio
async def test_context_engine_injects_skill_and_knowledge_base_capabilities() -> None:
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="data_query",
            kind="prompt_skill",
            source="skill_package:data",
            description="Query internal business data",
            metadata={"family": "data_intelligence"},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
        kb_ids=[101],
        kb_bindings=[
            {
                "kb_id": 101,
                "kb_name": "客户案例库",
                "kb_description": "沉淀客户案例与最佳实践",
                "kb_document_count": 6,
            }
        ],
    )

    assert "## Data Intelligence Skills" in assembly.messages[0].content
    assert "## Knowledge Bases" in assembly.messages[0].content
    assert any(
        "[CAPABILITIES]" in addition
        for addition in (assembly.system_prompt_additions or [])
    )


@pytest.mark.asyncio
async def test_context_engine_injects_page_context_capabilities() -> None:
    request = _build_request(
        input_variables={
            "page_context": {
                "page_key": "admin.users",
                "page_title": "用户管理",
                "page_data": {
                    "available_operations": [
                        {"name": "create_user", "readonly": False},
                        {"name": "delete_user", "readonly": False},
                    ]
                },
            }
        }
    )
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="web_search",
            kind="prompt_skill",
            source="skill_package:web",
            description="Search the public web",
            metadata={"family": "web_research"},
        )
    )

    assembly = await _assemble_context(
        request=request,
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(),
        kb_ids=[101],
        kb_bindings=[
            {
                "kb_id": 101,
                "kb_name": "帮助中心",
                "kb_description": "使用说明",
                "kb_document_count": 3,
            }
        ],
    )

    assert "## Current Page Context" in assembly.messages[0].content
    assert "Current page: 用户管理" in assembly.messages[0].content
    assert "Available operations: create_user, delete_user" in (
        assembly.messages[0].content
    )


@pytest.mark.asyncio
async def test_context_engine_injects_locale_hint_from_page_context() -> None:
    request = _build_request(
        input_variables={
            "page_context": {
                "page_key": "tenant.dashboard",
                "page_title": "仪表盘",
                "page_data": {
                    "locale": "zh_CN",
                },
            }
        }
    )

    assembly = await _assemble_context(
        request=request,
        skill_result=None,
        settings=TenantCapabilityAwarenessSettings(),
    )

    additions = " ".join(assembly.system_prompt_additions or [])
    assert "zh_CN" in additions or "zh-CN" in additions
    assert "Chinese" in additions


@pytest.mark.asyncio
async def test_context_engine_skips_capability_block_when_disabled() -> None:
    skill_result = _build_skill_result(
        CapabilityDescriptor(
            name="web_search",
            kind="prompt_skill",
            source="skill_package:web",
            description="Search the public web",
            metadata={"family": "web_research"},
        )
    )

    assembly = await _assemble_context(
        request=_build_request(),
        skill_result=skill_result,
        settings=TenantCapabilityAwarenessSettings(
            enable_dynamic_capability_awareness=False,
        ),
    )

    assert "[CAPABILITIES]" not in assembly.messages[0].content
    assert assembly.diagnostics["dynamic_capability_awareness_enabled"] is False
