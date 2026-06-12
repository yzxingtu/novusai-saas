"""Test type: behavioral
Scope: ConversationEngine prepare-execution KB binding for definition questions.
Mocked dependencies: router and RAG loader seams; prepare-execution logic runs real.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


class _FakeRouter:
    def __init__(self, db):
        self.db = db

    async def route(self, agent, request, estimated_tokens, tools=None):
        _ = agent, request, estimated_tokens, tools
        return None


def _build_agent() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Researcher",
        system_prompt="You are {{ agent_name }}.",
        rag_config=None,
        context_config=None,
        model=SimpleNamespace(
            supports_audio=False,
            supports_video=False,
            supports_vision=False,
        ),
    )


def _build_skill_result() -> SkillResolveResult:
    return SkillResolveResult(
        tools=[
            ToolDefinition(name="query_records", description="Query platform data"),
        ]
    )


@pytest.fixture(autouse=True)
def _stub_missing_tool_runtime_summary_prompt(monkeypatch):
    import app.ai.engine.base_execution_support as base_execution_support

    original = base_execution_support.render_prompt_contract

    def _render(name, *args, **kwargs):
        if name == "tool_runtime_summary":
            _ = args, kwargs
            return "[TOOL RUNTIME SUMMARY]"
        return original(name, *args, **kwargs)

    monkeypatch.setattr(base_execution_support, "render_prompt_contract", _render)


@pytest.mark.asyncio
async def test_prepare_execution_injects_bound_kb_for_definition_question() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[ChatMessage(role="user", content="NovusAI 是什么？")],
        input_variables={},
    )

    async def _fake_inject_rag_context(
        _db,
        _agent,
        messages,
        _tenant_id,
        kb_ids=None,
        rag_config=None,
        kb_weights=None,
    ):
        _ = _db, _agent, _tenant_id, rag_config, kb_weights
        assert kb_ids == [101]
        return (
            messages
            + [ChatMessage(role="system", content="[KB HIT] novusai-overview")],
            [{"kb_id": 101, "chunk_id": "novusai-overview"}],
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([101], {101: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(side_effect=_fake_inject_rag_context),
        ) as inject_mock,
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == ["knowledge_query"]
    assert prep.execution_path == "normal"
    assert prep.rag_source_kinds == ["formal_kb"]
    assert "knowledge_base" in prep.diagnostics["context_source_kinds"]
    assert (
        "knowledge_base"
        in prep.diagnostics["runtime_capability_summary"]["context_source_kinds"]
    )
    assert (
        "Knowledge-base context is available this turn." not in prep.messages[0].content
    )
    inject_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_execution_injects_bound_kb_for_plain_question() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[ChatMessage(role="user", content="仓库地址是多少")],
        input_variables={},
    )

    async def _fake_inject_rag_context(
        _db,
        _agent,
        messages,
        _tenant_id,
        kb_ids=None,
        rag_config=None,
        kb_weights=None,
    ):
        _ = _db, _agent, _tenant_id, rag_config, kb_weights
        assert kb_ids == [101]
        return (
            messages
            + [ChatMessage(role="system", content="[KB HIT] repository-url")],
            [{"kb_id": 101, "chunk_id": "repository-url"}],
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([101], {101: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(side_effect=_fake_inject_rag_context),
        ) as inject_mock,
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.execution_path == "fast"
    assert prep.rag_source_kinds == ["formal_kb"]
    assert prep.diagnostics["intent_flags"]["has_bound_kb"] is True
    assert prep.diagnostics["intent_flags"]["has_knowledge_intent"] is False
    assert prep.diagnostics["rag_attempted"] is True
    assert "knowledge_base" in prep.diagnostics["context_source_kinds"]
    assert (
        "knowledge_base"
        in prep.diagnostics["runtime_capability_summary"]["context_source_kinds"]
    )
    inject_mock.assert_awaited_once()
