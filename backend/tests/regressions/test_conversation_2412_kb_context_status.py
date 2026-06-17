"""
Test type: behavioral
Regression for: conversation_id=2412
Original symptom: the user asked "看看绑定的知识库有什么内容"; the turn was a
knowledge_query with active KB id=1, but the prompt had no stable KB status and
the assistant claimed it could not inspect the bound knowledge base.
Scope: context assembly and RAG status contract for bound-KB/tool-managed turns.
Real dependencies: ConversationContextEngine, prompt contract renderer, runtime
capability finalization, and diagnostics shaping.
Mocked dependencies: tenant config, KB binding read model, intent fixture, model
capability lookup, and RAG retrieval transport guard.
Why this is not self-fulfilling: no LLM response is mocked; the test asserts
the runtime-provided context contract that tells the model to use context tools.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.runtime.context_capability_bridge import DefaultContextCapabilityBridge
from app.ai.types import ChatMessage
from app.services.ai.capability_awareness_config import (
    TenantCapabilityAwarenessSettings,
)


class _BaseEngineStub:
    @staticmethod
    def _build_system_message(agent, input_variables=None):
        _ = input_variables
        return ChatMessage(role="system", content=agent.system_prompt or "")


def _agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=59,
        name="猫娘智能体",
        system_prompt="你是一个有帮助的智能体。",
        rag_config=None,
        context_config=None,
        model=None,
    )


def _request() -> ExecutionRequest:
    return ExecutionRequest(
        agent_id=59,
        tenant_id=1,
        user_id=3,
        conversation_id=2412,
        messages=[ChatMessage(role="user", content="看看绑定的知识库有什么内容")],
        input_variables={},
        memory_enabled=False,
        long_term_memory_enabled=False,
    )


@pytest.mark.asyncio
async def test_conversation_2412_bound_kb_turn_gets_tool_managed_prompt_status() -> (
    None
):
    context_engine = ConversationContextEngine(
        db=object(),
        base_engine=_BaseEngineStub(),
    )

    with (
        patch(
            "app.ai.runtime.context_capability_bridge.get_tenant_capability_awareness_settings",
            new=AsyncMock(
                return_value=TenantCapabilityAwarenessSettings(
                    enable_dynamic_capability_awareness=False,
                )
            ),
        ),
        patch.object(
            DefaultContextCapabilityBridge,
            "resolve_runtime_model_capabilities",
            new=AsyncMock(return_value={"supports_audio": False}),
        ),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([1], {1: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(),
        ) as inject_mock,
        patch(
            "app.ai.context.engine_runtime_support.load_compaction_snapshot",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.ai.agent_kb_binding_service.AgentKBBindingService.get_agent_kb_bindings_with_metadata",
            new=AsyncMock(
                return_value=[
                    {
                        "kb_id": 1,
                        "kb_name": "测试知识库",
                        "kb_description": "用于测试知识库全流程的示例知识库",
                        "kb_document_count": 2,
                    }
                ]
            ),
        ),
    ):
        assembly = await context_engine.assemble(
            _agent(),
            _request(),
            skill_result=None,
        )

    system_prompt = assembly.messages[0].content
    assert "[RUNTIME KNOWLEDGE CONTEXT METADATA]" in system_prompt
    assert "测试知识库" in system_prompt
    assert '"document_count":2' in system_prompt
    assert '"status":"skipped_tool_managed"' in system_prompt
    assert 'Only retrieval.status="injected"' in system_prompt

    assert assembly.rag_sources is None
    assert assembly.diagnostics["effective_knowledge_base_ids"] == [1]
    assert assembly.diagnostics["rag_attempted"] is False
    assert assembly.diagnostics["rag_retrieval_status"] == "skipped_tool_managed"
    assert assembly.diagnostics["rag_no_hit_reason"] is None
    assert assembly.diagnostics["capability_injection_decision"]["kb_injected"] is (
        False
    )
    inject_mock.assert_not_awaited()

    knowledge_sources = [
        source
        for source in assembly.diagnostics["context_sources"]
        if source["kind"] == "knowledge_base"
    ]
    assert knowledge_sources == [
        {
            "kind": "knowledge_base",
            "name": "测试知识库",
            "active": True,
            "metadata": {
                "knowledge_base_ids": [1],
                "knowledge_base_count": 1,
                "knowledge_bases": [
                    {
                        "id": 1,
                        "name": "测试知识库",
                        "description": "用于测试知识库全流程的示例知识库",
                        "document_count": 2,
                    }
                ],
                "knowledge_base_names": ["测试知识库"],
                "requested_knowledge_base_ids": [],
                "dropped_knowledge_base_ids": [],
                "binding_restriction_applied": False,
                "rag_source_count": 0,
                "rag_source_kinds": [],
                "rag_attempted": False,
                "rag_retrieval_status": "skipped_tool_managed",
                "rag_no_hit_reason": None,
                "rag_matched_chunk_count": 0,
            },
        }
    ]
