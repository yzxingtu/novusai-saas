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
    agent = SimpleNamespace(
        id=1,
        name="Writer",
        system_prompt="You are {{ agent_name }}.",
        rag_config=None,
        model=SimpleNamespace(
            supports_audio=False,
            supports_video=False,
            supports_vision=False,
        ),
    )
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
async def test_prepare_execution_builds_web_research_continuation_context_and_passes_optimizer_hints() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="你帮我联网搜索 张雪峰 为什么死了 然后多查看几个文章 然后总结给我"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"张雪峰 为什么死了","max_results":5}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="Search results for: 张雪峰 为什么死了"),
            ChatMessage(role="assistant", content="先给你一版总结"),
            ChatMessage(role="user", content="你要多结合几篇文章一起分析 而不是仅一篇文章"),
        ],
        input_variables={},
    )
    agent = SimpleNamespace(
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
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="data_query", description="Query platform data"),
        ]
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, used_tool_names=None, preferred_family=None, **kwargs):
        captured["user_query"] = user_query
        captured["used_tool_names"] = used_tool_names
        captured["preferred_family"] = preferred_family
        return SimpleNamespace(
            tools=tools,
            skipped=True,
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
            agent,
            request,
            skill_result=skill_result,
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is True
    assert prep.continuation_context.family == "web_research"
    assert "张雪峰 为什么死了" in prep.continuation_context.effective_user_query
    assert "更多来源" in prep.continuation_context.effective_user_query
    assert captured["preferred_family"] == "web_research"
    assert captured["used_tool_names"] == {"web_search"}


@pytest.mark.asyncio
async def test_prepare_execution_marks_initial_multi_source_web_research_as_active() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="你帮我联网搜索 张雪峰 为什么死了 然后多查看几个文章 然后总结给我",
            ),
        ],
        input_variables={},
    )
    agent = SimpleNamespace(
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
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="data_query", description="Query platform data"),
        ]
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, used_tool_names=None, preferred_family=None, **kwargs):
        captured["user_query"] = user_query
        captured["used_tool_names"] = used_tool_names
        captured["preferred_family"] = preferred_family
        return SimpleNamespace(
            tools=tools,
            skipped=True,
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
            agent,
            request,
            skill_result=skill_result,
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is True
    assert prep.continuation_context.family == "web_research"
    assert prep.continuation_context.origin == "initial"
    assert prep.continuation_context.requires_multi_source is True
    assert "更多来源" in prep.continuation_context.effective_user_query
    assert "交叉验证" in prep.continuation_context.effective_user_query
    assert captured["preferred_family"] == "web_research"
    assert captured["used_tool_names"] is None
