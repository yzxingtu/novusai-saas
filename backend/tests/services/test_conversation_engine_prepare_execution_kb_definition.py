"""Test type: behavioral
Scope: ConversationEngine prepare-execution KB binding for definition questions.
Mocked dependencies: router and RAG loader seams; prepare-execution logic runs real.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.context_tools.tools import (
    TOOL_RECALL_LONG_TERM_MEMORY,
    TOOL_SAVE_LONG_TERM_MEMORY,
    TOOL_SEARCH_AGENT_KNOWLEDGE_BASE,
    build_context_tool_definitions,
)
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
            *build_context_tool_definitions(),
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
async def test_prepare_execution_exposes_context_tool_for_definition_question() -> None:
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

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([101], {101: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(),
        ) as inject_mock,
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    # After fix: plain question without semantic tool match stays direct_reply
    # with context tools as optional (mode="auto"), NOT promoted to required.
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.rag_source_kinds == []
    assert TOOL_SEARCH_AGENT_KNOWLEDGE_BASE in [tool.name for tool in prep.tools]
    assert TOOL_SAVE_LONG_TERM_MEMORY in [tool.name for tool in prep.tools]
    assert TOOL_RECALL_LONG_TERM_MEMORY in [tool.name for tool in prep.tools]
    assert TOOL_SEARCH_AGENT_KNOWLEDGE_BASE in prep.tool_use_policy.allowed_tool_names
    assert prep.tool_use_policy.family == "none"
    assert prep.tool_use_policy.mode == "auto"
    assert prep.tool_use_policy.reason == "direct_reply_optional_context_tools"
    assert prep.diagnostics["rag_attempted"] is False
    assert prep.diagnostics["rag_retrieval_status"] == "skipped_tool_managed"
    assert "knowledge_base" in prep.diagnostics["context_source_kinds"]
    assert (
        "knowledge_base"
        in prep.diagnostics["runtime_capability_summary"]["context_source_kinds"]
    )
    assert (
        "Knowledge-base context is available this turn." not in prep.messages[0].content
    )
    inject_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_execution_exposes_context_tool_for_plain_question() -> None:
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

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([101], {101: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(),
        ) as inject_mock,
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    # After fix: plain question without semantic tool match stays direct_reply
    # with context tools as optional (mode="auto"), NOT promoted to required.
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.rag_source_kinds == []
    assert TOOL_SEARCH_AGENT_KNOWLEDGE_BASE in [tool.name for tool in prep.tools]
    assert TOOL_SAVE_LONG_TERM_MEMORY in [tool.name for tool in prep.tools]
    assert TOOL_RECALL_LONG_TERM_MEMORY in [tool.name for tool in prep.tools]
    assert TOOL_SEARCH_AGENT_KNOWLEDGE_BASE in prep.tool_use_policy.allowed_tool_names
    assert prep.tool_use_policy.family == "none"
    assert prep.tool_use_policy.mode == "auto"
    assert prep.tool_use_policy.reason == "direct_reply_optional_context_tools"
    assert prep.diagnostics["intent_flags"]["has_bound_kb"] is True
    assert prep.diagnostics["intent_flags"]["has_knowledge_intent"] is False
    assert prep.diagnostics["rag_attempted"] is False
    assert prep.diagnostics["rag_retrieval_status"] == "skipped_tool_managed"
    assert "knowledge_base" in prep.diagnostics["context_source_kinds"]
    assert (
        "knowledge_base"
        in prep.diagnostics["runtime_capability_summary"]["context_source_kinds"]
    )
    inject_mock.assert_not_awaited()
