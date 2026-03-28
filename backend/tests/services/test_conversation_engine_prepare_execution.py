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
        model=SimpleNamespace(
            supports_audio=False,
            supports_video=False,
            supports_vision=False,
        ),
    )


def _build_skill_result() -> SkillResolveResult:
    return SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="data_query", description="Query platform data"),
        ]
    )


@pytest.mark.asyncio
async def test_prepare_execution_skips_tools_when_sandbox_is_missing() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=None)
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="优化一下这段文字")],
        input_variables={},
    )
    agent = _build_agent()
    skill_result = SkillResolveResult(
        tools=[ToolDefinition(name="web_search", description="Search the web")]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=skill_result,
        )

    assert prep.tools == []
    assert request.input_variables["runtime_model_capabilities"] == {
        "supports_audio": False,
        "supports_video": False,
        "supports_vision": False,
    }


@pytest.mark.asyncio
async def test_prepare_execution_uses_current_user_text_for_optimizer_before_research_starts() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="Search current public information about Sample Topic.",
            ),
        ],
        input_variables={},
    )
    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, **kwargs):
        captured["user_query"] = user_query
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            tools=tools[:2],
            skipped=False,
            total=len(tools),
            selected=2,
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch("app.ai.tools.optimizer.optimize_tools", side_effect=_fake_optimize),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is False
    assert prep.continuation_context.family is None
    assert prep.continuation_context.origin == "none"
    assert prep.continuation_context.research_target_text == (
        "Search current public information about Sample Topic."
    )
    assert captured["user_query"] == "Search current public information about Sample Topic."
    assert captured["kwargs"] == {}
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]


@pytest.mark.asyncio
async def test_prepare_execution_preserves_active_web_research_state_without_optimizer_bias() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="Search current public information about Sample Topic.",
            ),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"sample topic public info","max_results":5}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="Search results for: sample topic public info"),
            ChatMessage(role="assistant", content="Initial notes."),
            ChatMessage(
                role="user",
                content="Continue reviewing the same public webpages.",
            ),
        ],
        input_variables={},
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, **kwargs):
        captured["user_query"] = user_query
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            tools=tools,
            skipped=False,
            total=len(tools),
            selected=len(tools),
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch("app.ai.tools.optimizer.optimize_tools", side_effect=_fake_optimize),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is True
    assert prep.continuation_context.family == "web_research"
    assert prep.continuation_context.origin == "continuation"
    assert prep.continuation_context.current_user_text == (
        "Continue reviewing the same public webpages."
    )
    assert prep.continuation_context.research_target_text == "sample topic public info"
    assert prep.continuation_context.search_query_count == 1
    assert prep.continuation_context.fetched_url_count == 0
    assert prep.continuation_context.recent_successful_tool_names == ["web_search"]
    assert prep.continuation_context.recent_web_queries == ["sample topic public info"]
    assert prep.continuation_context.research_instruction_texts == [
        "Search current public information about Sample Topic.",
        "Continue reviewing the same public webpages.",
    ]
    assert captured["user_query"] == "Continue reviewing the same public webpages."
    assert captured["kwargs"] == {}
    assert [tool.name for tool in prep.tools] == [
        "web_search",
        "fetch_url",
        "data_query",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_generic_follow_up_in_research_state() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="Search current public information about Sample Topic.",
            ),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"sample topic public info","max_results":5}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="Search results for: sample topic public info"),
            ChatMessage(role="assistant", content="Initial notes."),
            ChatMessage(role="user", content="Continue."),
        ],
        input_variables={},
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, **kwargs):
        captured["user_query"] = user_query
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            tools=tools,
            skipped=False,
            total=len(tools),
            selected=len(tools),
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch("app.ai.tools.optimizer.optimize_tools", side_effect=_fake_optimize),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is True
    assert prep.continuation_context.current_user_text == "Continue."
    assert prep.continuation_context.research_target_text == "sample topic public info"
    assert prep.continuation_context.search_query_count == 1
    assert prep.continuation_context.fetched_url_count == 0
    assert captured["user_query"] == "Continue."
    assert captured["kwargs"] == {}
