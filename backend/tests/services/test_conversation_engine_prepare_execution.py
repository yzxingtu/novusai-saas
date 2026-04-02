from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.context import get_context_engine
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.tool_invocation_planner import ToolInvocationPlan
from app.ai.engine.types import ExecutionRequest, ToolUsePolicy
from app.ai.runtime.types import CapabilityDescriptor
from app.ai.runtime.flags import (
    reset_shadow_rate_limiter_for_tests,
    should_run_shadow_probe,
)
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse


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
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="data_query", description="Query platform data"),
        ]
    )


def _build_plugin_page_web_skill_result() -> SkillResolveResult:
    return SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                description="Search the web",
                source_skill_id=11,
                source_skill_name="Plugin Research Skill",
                source_skill_type="plugin",
                source_package_name="plugin.research",
                source_plugin="plugin.research",
            ),
            ToolDefinition(
                name="fetch_url",
                description="Fetch the url",
                source_skill_id=11,
                source_skill_name="Plugin Research Skill",
                source_skill_type="plugin",
                source_package_name="plugin.research",
                source_plugin="plugin.research",
            ),
            ToolDefinition(
                name="get_page_context",
                description="Read page context",
                source_skill_id=12,
                source_skill_name="Plugin Page Skill",
                source_skill_type="plugin",
                source_package_name="plugin.page",
                source_plugin="plugin.page",
            ),
            ToolDefinition(
                name="invoke_page_operation",
                description="Operate page",
                source_skill_id=12,
                source_skill_name="Plugin Page Skill",
                source_skill_type="plugin",
                source_package_name="plugin.page",
                source_plugin="plugin.page",
            ),
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
    assert captured["kwargs"] == {"preferred_family": "web_research"}
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="auto",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="explicit_web_request",
    )


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
    assert captured["kwargs"] == {"preferred_family": "web_research"}
    assert [tool.name for tool in prep.tools] == [
        "web_search",
        "fetch_url",
    ]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="anchored_or_unfinished_web_continuation",
    )


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
    assert captured["kwargs"] == {"preferred_family": "web_research"}
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="anchored_or_unfinished_web_continuation",
    )


@pytest.mark.asyncio
async def test_prepare_execution_does_not_inherit_page_ops_for_generic_follow_up_without_anchor() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="Open the form."),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_page_1",
                        "type": "function",
                        "function": {
                            "name": "invoke_page_operation",
                            "arguments": '{"page_key":"demo.form","operation_name":"fill_form"}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="Form fill succeeded."),
            ChatMessage(role="assistant", content="Done."),
            ChatMessage(role="user", content="继续"),
        ],
        input_variables={
            "page_context": {
                "page_key": "demo.form",
                "page_data": {
                    "available_operations": [
                        {"name": "fill_form", "readonly": False},
                    ],
                },
            },
        },
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

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="get_page_context", description="Read page"),
            ToolDefinition(name="web_search", description="Search the web"),
        ]
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
            skill_result=skill_result,
        )

    assert captured["kwargs"] == {"preferred_family": None}
    assert [tool.name for tool in prep.tools] == []
    assert prep.tool_use_policy == ToolUsePolicy(
        family="none",
        mode="auto",
        allowed_tool_names=[],
        retry_on_contract_breach=True,
        reason="default_no_tool",
    )


@pytest.mark.asyncio
async def test_prepare_execution_selects_page_ops_for_local_page_content_request() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="看看本页面的内容")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                    ],
                },
            },
        },
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, **kwargs):
        captured["user_query"] = user_query
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            tools=[
                tool
                for tool in tools
                if tool.name in {"get_page_context", "invoke_page_operation"}
            ],
            skipped=False,
            total=len(tools),
            selected=2,
        )

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ]
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
            skill_result=skill_result,
        )

    assert captured["user_query"] == "看看本页面的内容"
    assert captured["kwargs"] == {"preferred_family": "page_ops"}
    assert [tool.name for tool in prep.tools] == [
        "get_page_context",
        "invoke_page_operation",
    ]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="page_ops",
        mode="required",
        allowed_tool_names=[
            "get_page_context",
            "invoke_page_operation",
        ],
        retry_on_contract_breach=True,
        reason="explicit_page_request",
    )


@pytest.mark.asyncio
async def test_prepare_execution_selects_page_ops_for_page_capability_request() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="通过页面感知能力添加一个测试的智能体 具体里面的内容你来决定",
            ),
        ],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.agents",
                "page_data": {
                    "available_operations": [
                        {"name": "create_record", "readonly": False},
                        {"name": "fill_form", "readonly": False},
                        {"name": "submit_form", "readonly": False},
                    ],
                },
            },
        },
    )

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "page_ops"
    assert "get_page_context" in prep.tool_use_policy.allowed_tool_names
    assert "pageop_create_record" in prep.tool_use_policy.allowed_tool_names
    assert "pageop_fill_form" in prep.tool_use_policy.allowed_tool_names
    assert "pageop_submit_form" in prep.tool_use_policy.allowed_tool_names


@pytest.mark.asyncio
async def test_prepare_execution_routes_weather_requests_to_weather_family(mock_db) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="请告诉我今天天气怎么样，并预报下周的走向。"),
        ],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="get_current_weather",
                description="Get current conditions for a city",
            ),
            ToolDefinition(
                name="get_weather_forecast",
                description="Get forecast for future days",
            ),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "weather"
    assert set(tool.name for tool in prep.tools) == {
        "get_current_weather",
        "get_weather_forecast",
    }
    assert prep.tool_use_policy.allowed_tool_names == [
        "get_current_weather",
        "get_weather_forecast",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_weather_tools_for_mixed_weather_and_health_turn() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="我有点头疼，今天北京天气怎么样")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                        {"name": "read_row_detail", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="get_current_weather", description="Get current weather"),
            ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
            ToolDefinition(name="data_query", description="Query platform data"),
            ToolDefinition(name="data_create", description="Create data"),
            ToolDefinition(name="data_update", description="Update data"),
            ToolDefinition(name="data_delete", description="Delete data"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "weather"
    assert prep.tool_use_policy.allowed_tool_names == [
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert [tool.name for tool in prep.tools] == [
        "get_current_weather",
        "get_weather_forecast",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_allows_page_and_weather_tools_for_mixed_request() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="先看看本页面，再查北京天气")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                        {"name": "read_row_detail", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="get_current_weather", description="Get current weather"),
            ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
            ToolDefinition(name="data_query", description="Query platform data"),
            ToolDefinition(name="data_create", description="Create data"),
            ToolDefinition(name="data_update", description="Update data"),
            ToolDefinition(name="data_delete", description="Delete data"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "page_ops"
    assert prep.tool_use_policy.allowed_tool_names == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert [tool.name for tool in prep.tools] == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert "[ORDERED CAPABILITY INTENT]" in prep.messages[0].content
    assert "1. page operations" in prep.messages[0].content
    assert "2. weather tools" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_allows_page_and_weather_tools_for_mixed_request_with_health_phrase() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="我有点头疼，先看看当前页面，再查北京天气")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                        {"name": "read_row_detail", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="get_current_weather", description="Get current weather"),
            ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
            ToolDefinition(name="data_query", description="Query platform data"),
            ToolDefinition(name="data_create", description="Create data"),
            ToolDefinition(name="data_update", description="Update data"),
            ToolDefinition(name="data_delete", description="Delete data"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "page_ops"
    assert prep.tool_use_policy.allowed_tool_names == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
        "get_weather_forecast",
    ]
    assert [tool.name for tool in prep.tools] == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
        "get_weather_forecast",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_restores_secondary_family_when_optimizer_drops_it() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="先看看本页面，再查北京天气")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                        {"name": "read_row_detail", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="get_current_weather", description="Get current weather"),
            ToolDefinition(name="get_weather_forecast", description="Get weather forecast"),
            ToolDefinition(name="data_query", description="Query platform data"),
        ]
    )

    def _fake_optimize(tools, user_query, **kwargs):
        _ = user_query, kwargs
        return SimpleNamespace(
            tools=[
                tool
                for tool in tools
                if tool.name
                in {
                    "get_page_context",
                    "invoke_page_operation",
                    "pageop_read_row_detail",
                    "pageop_read_visible_rows",
                }
            ],
            skipped=False,
            total=len(tools),
            selected=4,
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
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.family == "page_ops"
    assert prep.tool_use_policy.allowed_tool_names == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
    ]
    assert [tool.name for tool in prep.tools] == [
        "get_page_context",
        "invoke_page_operation",
        "pageop_read_row_detail",
        "pageop_read_visible_rows",
        "get_current_weather",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_prefers_web_research_on_first_turn_even_with_page_context() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查询一下 小猫为什么 爱吃鱼")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "capture_screenshot", "readonly": True},
                        {"name": "refresh_list", "readonly": True},
                        {"name": "search", "readonly": True},
                        {"name": "clear_search", "readonly": True},
                        {"name": "read_visible_rows", "readonly": True},
                        {"name": "next_page", "readonly": True},
                        {"name": "prev_page", "readonly": True},
                        {"name": "go_to_page", "readonly": True},
                        {"name": "set_page_size", "readonly": True},
                        {"name": "read_row_detail", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
            ToolDefinition(name="data_query", description="Query platform data"),
            ToolDefinition(name="data_create", description="Create data"),
            ToolDefinition(name="data_update", description="Update data"),
            ToolDefinition(name="data_delete", description="Delete data"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="auto",
        allowed_tool_names=[
            "web_search",
            "fetch_url",
            "get_page_context",
            "invoke_page_operation",
        ],
        retry_on_contract_breach=True,
        reason="explicit_web_request",
    )
    assert [tool.name for tool in prep.tools] == [
        "web_search",
        "fetch_url",
        "get_page_context",
        "invoke_page_operation",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_non_zero_selected_count_for_explicit_web_request() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查一下今天的开源模型发布")],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                    ],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="get_page_context", description="Read page context"),
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ]
    )

    def _fake_optimize(tools, user_query, **kwargs):
        _ = user_query, kwargs
        return SimpleNamespace(
            tools=[tool for tool in tools if tool.name in {"web_search", "fetch_url"}],
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
            skill_result=skill_result,
        )

    assert prep.optimize_event is not None
    assert prep.optimize_event["total"] == len(prep.all_tools)
    assert prep.optimize_event["total"] >= 4
    assert prep.optimize_event["selected"] == 2
    assert prep.optimize_event["selected"] > 0
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]


@pytest.mark.asyncio
async def test_prepare_execution_injects_absolute_date_anchor_for_date_sensitive_web_turn() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查阅一下，今天乌克兰的局势")],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.context.engine.utc_now",
            return_value=datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc),
        ),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_skill_result(),
        )

    assert "[RUNTIME CLOCK]" in prep.messages[0].content
    assert "2026-03-30" in prep.messages[0].content
    assert prep.diagnostics["web_research_date_anchor"] is True


@pytest.mark.asyncio
async def test_prepare_execution_prefers_current_time_tool_for_time_question() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="现在几点？")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="get_current_time", description="Get current time"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.context.engine.utc_now",
            return_value=datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc),
        ),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy == ToolUsePolicy(
        family="time_ops",
        mode="auto",
        allowed_tool_names=["get_current_time"],
        retry_on_contract_breach=True,
        reason="explicit_time_request",
    )
    assert [tool.name for tool in prep.tools] == ["get_current_time"]
    assert "[RUNTIME CLOCK]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_exposes_pruning_diagnostics() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="Summarize this note.")],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assert prep.prune_stats is not None
    assert prep.prune_stats["mode"] == "transient_tool_result_pruning"


@pytest.mark.asyncio
async def test_prepare_execution_calls_context_engine_compact_after_assemble() -> None:
    """_prepare_execution must invoke ContextEngine.compact() after assemble (lifecycle)."""
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="Hello.")],
        input_variables={},
    )
    mock_compact = AsyncMock()
    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch("app.ai.context.engine.ConversationContextEngine.compact", mock_compact),
    ):
        await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=SkillResolveResult(tools=[]),
        )
    mock_compact.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_execution_prunes_only_old_large_tool_results_from_prompt() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    old_tool_payload = "x" * 6000
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="Start."),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_old",
                        "function": {
                            "name": "data_query",
                            "arguments": '{"sql":"' + ("q" * 1400) + '"}',
                        },
                        "summary_payload": {"preview": "y" * 2048},
                    }
                ],
            ),
            ChatMessage(role="tool", content=old_tool_payload, tool_call_id="call_old"),
            ChatMessage(role="assistant", content="Old summary."),
            ChatMessage(role="user", content="Second turn."),
            ChatMessage(role="assistant", content="Middle reply."),
            ChatMessage(role="user", content="Third turn."),
            ChatMessage(role="assistant", content="Recent reply."),
            ChatMessage(role="user", content="What should we do next?"),
        ],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    tool_messages = [msg for msg in prep.messages if msg.role == "tool"]
    assert tool_messages
    assert tool_messages[0].content == "[Older tool result omitted from prompt]"
    assistant_tool_round = next(
        msg for msg in prep.messages if msg.role == "assistant" and msg.tool_calls
    )
    assert assistant_tool_round.tool_calls[0]["summary_payload"] == {
        "_pruned": "Older tool summary payload omitted"
    }
    assert assistant_tool_round.tool_calls[0]["function"]["arguments"].endswith(
        "...[truncated]"
    )
    assert prep.prune_stats["pruned_tool_message_count"] == 1
    assert prep.prune_stats["pruned_tool_call_count"] == 1


@pytest.mark.asyncio
async def test_prepare_execution_keeps_pending_confirmation_tool_rounds_intact() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    pending_payload = (
        '{"requires_confirmation": true, "action": "tool_consent", "tool_name": "data_delete"}'
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="Start."),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_pending",
                        "function": {
                            "name": "data_delete",
                            "arguments": '{"id": 1}',
                        },
                        "pending_confirmation": {"action": "delete", "table": "demo"},
                    }
                ],
            ),
            ChatMessage(
                role="tool",
                content=pending_payload,
                tool_call_id="call_pending",
            ),
            ChatMessage(role="assistant", content="Older assistant."),
            ChatMessage(role="user", content="Second turn."),
            ChatMessage(role="assistant", content="Middle reply."),
            ChatMessage(role="user", content="Third turn."),
            ChatMessage(role="assistant", content="Recent reply."),
            ChatMessage(role="user", content="Continue."),
        ],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    tool_messages = [msg for msg in prep.messages if msg.role == "tool"]
    assert tool_messages
    assert tool_messages[0].content == pending_payload
    assert prep.prune_stats["pruned_tool_message_count"] == 0


@pytest.mark.asyncio
async def test_prepare_execution_keeps_small_tool_payloads_unpruned() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="Start."),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_small",
                        "function": {
                            "name": "data_query",
                            "arguments": '{"sql":"select * from demo"}',
                        },
                        "summary_payload": {"preview": "small"},
                    }
                ],
            ),
            ChatMessage(role="tool", content="small output", tool_call_id="call_small"),
            ChatMessage(role="assistant", content="Old summary."),
            ChatMessage(role="user", content="Second turn."),
            ChatMessage(role="assistant", content="Middle reply."),
            ChatMessage(role="user", content="Third turn."),
            ChatMessage(role="assistant", content="Recent reply."),
            ChatMessage(role="user", content="Continue."),
        ],
        input_variables={},
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assistant_tool_round = next(
        msg for msg in prep.messages if msg.role == "assistant" and msg.tool_calls
    )
    assert assistant_tool_round.tool_calls[0]["summary_payload"] == {"preview": "small"}
    assert assistant_tool_round.tool_calls[0]["function"]["arguments"] == '{"sql":"select * from demo"}'
    assert prep.prune_stats["pruned_tool_call_count"] == 0


@pytest.mark.asyncio
async def test_prepare_execution_builds_compaction_snapshot_sidecar_when_threshold_exceeded() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    agent.context_config = {
        "compact_threshold_tokens": 20,
        "compact_keep_last_assistants": 1,
        "compact_max_summary_chars": 500,
    }
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=42,
        messages=[
            ChatMessage(role="user", content="用户先描述了一个很长很长的背景信息，需要系统记住业务上下文和限制条件。"),
            ChatMessage(role="assistant", content="助手先给出了较长的解释，说明之前已经执行过一些检索和整理工作。"),
            ChatMessage(role="user", content="然后用户继续补充了另外一段较长说明，希望后续回答都基于这个背景。"),
            ChatMessage(role="assistant", content="最近一轮助手回复，应该保留在最近上下文中。"),
            ChatMessage(role="user", content="请继续回答。"),
        ],
        input_variables={},
    )

    snap_store: dict[str, Any] = {}

    async def fake_get_snapshot(_cid: int) -> dict[str, Any] | None:
        return snap_store.get("snap")

    async def fake_upsert_snapshot(
        _cid: int,
        *,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any]:
        snap = {
            "summary": summary,
            "source_message_count": source_message_count,
            "source_token_estimate": source_token_estimate,
        }
        snap_store["snap"] = snap
        return snap

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.services.ai.conversation_service.ConversationService.get_context_compaction_snapshot",
            new=AsyncMock(side_effect=fake_get_snapshot),
        ),
        patch(
            "app.services.ai.conversation_service.ConversationService.upsert_context_compaction_snapshot",
            new=AsyncMock(side_effect=fake_upsert_snapshot),
        ) as upsert_snapshot,
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assert prep.context_compacted is True
    assert prep.compact_summary is not None
    assert "[COMPACTED CONTEXT SUMMARY]" in prep.messages[0].content
    assert prep.system_prompt_additions
    # Second persist skipped when snapshot unchanged (assemble + compact dedup).
    assert upsert_snapshot.await_count == 1


@pytest.mark.asyncio
async def test_context_engine_after_turn_refreshes_compaction_snapshot() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    base_engine = engine
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        conversation_id=42,
        messages=[ChatMessage(role="user", content="hello")],
        input_variables={},
    )
    agent = _build_agent()
    agent.context_config = {
        "compact_threshold_tokens": 10,
        "compact_keep_last_assistants": 1,
        "compact_max_summary_chars": 300,
    }
    context_engine = get_context_engine(
        db=MagicMock(),
        base_engine=base_engine,
    )
    result = SimpleNamespace(
        messages=[
            {"role": "system", "content": "You are assistant"},
            {"role": "user", "content": "第一轮用户问题，内容足够长以触发压缩。"},
            {"role": "assistant", "content": "第一轮助手回答，内容也足够长以触发压缩。"},
            {"role": "user", "content": "第二轮继续追问，仍然很长。"},
            {"role": "assistant", "content": "第二轮助手回答。"},
        ]
    )

    with patch.object(
        context_engine,
        "_persist_compaction_snapshot",
        new=AsyncMock(),
    ) as persist_snapshot:
        await context_engine.after_turn(agent, request, result)

    persist_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_execution_injects_long_term_memory_recall_when_enabled() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    agent.context_config = {
        "long_term_memory_enabled": True,
    }
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        long_term_memory_enabled=True,
        messages=[
            ChatMessage(role="user", content="以后帮我写邮件要正式一些。"),
        ],
        input_variables={},
    )
    provider = MagicMock()
    provider.profile = AsyncMock(return_value=None)
    provider.recall = AsyncMock(
        return_value=[
            SimpleNamespace(
                memory_type="preference",
                summary="用户偏好正式邮件语气",
                content="用户偏好正式邮件语气",
            )
        ]
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.context.engine.get_long_term_memory_provider",
            return_value=provider,
        ),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {"count": 1, "scope_type": "user_agent"}
    assert "[LONG-TERM MEMORY RECALL]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_injects_profile_snapshot_before_recall() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    agent.context_config = {
        "long_term_memory_enabled": True,
    }
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        long_term_memory_enabled=True,
        messages=[
            ChatMessage(role="user", content="继续按照我的习惯写。"),
        ],
        input_variables={},
    )
    provider = MagicMock()
    provider.profile = AsyncMock(
        return_value={
            "profile": {
                "preferences": ["邮件语气保持正式"],
                "constraints": ["不要使用口语化表达"],
            },
            "summary": "Preferences: 邮件语气保持正式",
        }
    )
    provider.recall = AsyncMock(return_value=[])

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.context.engine.get_long_term_memory_provider",
            return_value=provider,
        ),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {
        "count": 0,
        "profile_snapshot": True,
        "scope_type": "user_agent",
    }
    assert "[PROFILE SNAPSHOT]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_skips_runtime_capability_summary_when_dynamic_awareness_enabled() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[ChatMessage(role="user", content="请结合当前能力帮我查资料")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                description="Search the web",
                source_skill_name="Research Skill",
            ),
            ToolDefinition(
                name="fetch_url",
                description="Fetch url",
                source_skill_name="Research Skill",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Research Skill",
                kind="prompt_skill",
                source="skill_package:research",
                description="Search and fetch public information",
                metadata={"family": "web_research"},
            )
        ],
    )

    with (
        patch(
            "app.ai.context.engine.get_tenant_capability_awareness_settings",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    enable_dynamic_capability_awareness=True,
                    capability_description_style="detailed",
                    max_capability_items_per_category=20,
                )
            ),
        ),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert "[CAPABILITIES]" in prep.messages[0].content
    assert "[TOOL USAGE RULES]" in prep.messages[0].content
    assert "[CAPABILITY REPORTING]" not in prep.messages[0].content
    assert "[TURN CAPABILITIES]" not in prep.messages[0].content
    assert "You have 2 tool(s) available" not in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_keeps_runtime_capability_summary_when_dynamic_awareness_disabled() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[ChatMessage(role="user", content="请告诉我你这轮有哪些能力")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                description="Search the web",
                source_skill_name="Research Skill",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Research Skill",
                kind="prompt_skill",
                source="skill_package:research",
                description="Search public information",
                metadata={"family": "web_research"},
            )
        ],
    )

    with (
        patch(
            "app.ai.context.engine.get_tenant_capability_awareness_settings",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    enable_dynamic_capability_awareness=False,
                    capability_description_style="detailed",
                    max_capability_items_per_category=20,
                )
            ),
        ),
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert "[CAPABILITIES]" not in prep.messages[0].content
    assert "[TOOL AWARENESS]" in prep.messages[0].content
    assert "[CAPABILITY REPORTING]" in prep.messages[0].content
    assert "[TURN CAPABILITIES]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_assembles_pageaware_kb_memory_and_plugin_skill_capabilities() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    agent.rag_config = {"top_k": 3}
    agent.context_config = {
        "long_term_memory_enabled": True,
    }
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        long_term_memory_enabled=True,
        messages=[
            ChatMessage(role="user", content="请联网结合当前页面和知识库给我总结"),
        ],
        input_variables={
            "page_context": {
                "page_key": "admin.ai.conversations",
                "page_title": "AI Conversations",
                "page_data": {
                    "available_operations": [
                        {"name": "read_visible_rows", "readonly": True},
                    ],
                },
            },
        },
    )
    provider = MagicMock()
    provider.profile = AsyncMock(
        return_value={
            "profile": {
                "preferences": ["优先引用知识库内容"],
            },
        }
    )
    provider.recall = AsyncMock(
        return_value=[
            SimpleNamespace(
                memory_type="preference",
                summary="用户偏好先查看插件技能输出",
                content="用户偏好先查看插件技能输出",
            )
        ]
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
            messages + [ChatMessage(role="system", content="[KB HIT] chunk-1")],
            [{"kb_id": 101, "chunk_id": "chunk-1"}],
        )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([101], {101: 1.0})),
        ),
        patch(
            "app.ai.rag_injector.inject_rag_context",
            new=AsyncMock(side_effect=_fake_inject_rag_context),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.context.engine.get_long_term_memory_provider",
            return_value=provider,
        ),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=_build_plugin_page_web_skill_result(),
        )

    assert prep.capability_bundle is not None
    assert set(prep.capability_bundle.selected_skill_names) == {
        "Plugin Research Skill",
        "Plugin Page Skill",
    }
    context_source_kinds = {source.kind for source in prep.capability_bundle.context_sources}
    assert context_source_kinds >= {
        "skill",
        "page_context",
        "knowledge_base",
        "long_term_memory",
    }
    assert prep.diagnostics["selected_skill_names"] == [
        "Plugin Research Skill",
        "Plugin Page Skill",
    ]
    assert prep.diagnostics["selected_tool_names"]
    assert prep.rag_source_kinds == ["formal_kb"]
    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {
        "count": 1,
        "profile_snapshot": True,
        "scope_type": "user_agent",
    }
    assert "[TURN CAPABILITIES]" in prep.messages[0].content
    assert "Selected skills for this turn: Plugin Research Skill, Plugin Page Skill." in prep.messages[0].content
    assert "Knowledge-base context is available this turn." in prep.messages[0].content
    assert "Page context is available this turn." in prep.messages[0].content
    assert "[LONG-TERM MEMORY RECALL]" in prep.messages[0].content
    assert "[PROFILE SNAPSHOT]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_deduplicates_selected_skill_names_in_capability_bundle() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[ChatMessage(role="user", content="请继续联网调研")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(
                name="web_search",
                description="Search the web",
                source_skill_id=88,
                source_skill_name="Plugin Research Skill",
                source_skill_type="plugin",
                source_package_name="plugin.research",
            ),
        ],
        capability_descriptors=[
            CapabilityDescriptor(
                name="Plugin Research Skill",
                kind="prompt_skill",
                source="skill_package:plugin.research",
            ),
            CapabilityDescriptor(
                name="Plugin Research Skill",
                kind="prompt_skill",
                source="skill_package:plugin.research.v2",
            ),
        ],
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.capability_bundle is not None
    assert prep.capability_bundle.selected_skill_names == ["Plugin Research Skill"]
    assert prep.diagnostics["selected_skill_names"] == ["Plugin Research Skill"]
    assert prep.diagnostics["context_source_kinds"]


@pytest.mark.asyncio
async def test_prepare_execution_applies_execution_trust_policy_to_ask_tools() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        trust_policy_ref={
            "policy_ids": [1],
            "allowed_tool_names": ["web_search"],
            "tool_families": [],
            "risk_level_cap": "read",
        },
        messages=[ChatMessage(role="user", content="查一下最新公开资料")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="data_delete", description="Delete data"),
        ],
        tool_consent_modes={
            "web_search": "ask",
            "data_delete": "ask",
        },
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_consent_modes["web_search"] == "auto"
    assert prep.tool_consent_modes["data_delete"] == "ask"


@pytest.mark.asyncio
async def test_prepare_execution_does_not_bypass_risk_cap_for_page_ops() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        trust_policy_ref={
            "policy_ids": [2],
            "allowed_tool_names": [],
            "tool_families": ["page_ops"],
            "risk_level_cap": "read",
        },
        messages=[ChatMessage(role="user", content="继续")],
        input_variables={
            "page_context": {
                "page_key": "demo.form",
                "page_data": {
                    "available_operations": [{"name": "fill_form", "readonly": False}],
                },
            },
        },
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="invoke_page_operation", description="Operate page"),
        ],
        tool_consent_modes={
            "invoke_page_operation": "ask",
        },
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=skill_result,
        )

    assert prep.tool_consent_modes["invoke_page_operation"] == "ask"


@pytest.mark.asyncio
async def test_call_llm_routes_non_stream_to_runtime_query_engine_when_active() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    runtime_response = ChatResponse(
        message=ChatMessage(role="assistant", content="runtime reply"),
        total_tokens=11,
    )
    runtime_engine = SimpleNamespace(
        turn_record=SimpleNamespace(
            selected_tool_names=["web_search"],
            selected_skill_names=["research_skill"],
            protocol_path="responses",
            termination_reason="completed",
        ),
    )
    legacy_response = ChatResponse(
        message=ChatMessage(role="assistant", content="legacy reply"),
        total_tokens=9,
    )
    runtime_call = AsyncMock(return_value=(runtime_response, runtime_engine))
    legacy_call = AsyncMock(return_value=legacy_response)

    with (
        patch("app.ai.engine.conversation.get_runtime_mode", return_value="active"),
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
    ):
        result = await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="请联网查询最新资料")],
            tools=[ToolDefinition(name="web_search", description="Search web")],
            selected_skill_names=["research_skill"],
            context_sources=[],
        )

    assert result is runtime_response
    assert runtime_call.await_count == 1
    assert runtime_call.await_args.kwargs["shadow_mode"] is False
    assert legacy_call.await_count == 0


@pytest.mark.asyncio
async def test_call_llm_pageaware_only_keeps_legacy_for_non_page_tools() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    legacy_response = ChatResponse(
        message=ChatMessage(role="assistant", content="legacy reply"),
        total_tokens=5,
    )
    runtime_call = AsyncMock()
    legacy_call = AsyncMock(return_value=legacy_response)

    with (
        patch("app.ai.engine.conversation.get_runtime_mode", return_value="pageaware_only"),
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
    ):
        result = await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="只做普通问答")],
            tools=[ToolDefinition(name="web_search", description="Search web")],
        )

    assert result is legacy_response
    assert runtime_call.await_count == 0
    assert legacy_call.await_count == 1


@pytest.mark.asyncio
async def test_call_llm_shadow_mode_returns_legacy_and_records_compare() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    legacy_response = ChatResponse(
        message=ChatMessage(role="assistant", content="legacy reply"),
        total_tokens=8,
        metadata={"protocol_path": "chat_completions"},
    )
    runtime_response = ChatResponse(
        message=ChatMessage(role="assistant", content="runtime reply"),
        total_tokens=10,
    )
    runtime_engine = SimpleNamespace(
        turn_record=SimpleNamespace(
            selected_tool_names=["get_page_context"],
            selected_skill_names=["page_skill"],
            protocol_path="responses",
            termination_reason="protocol_fallback",
        ),
    )
    runtime_call = AsyncMock(return_value=(runtime_response, runtime_engine))
    legacy_call = AsyncMock(return_value=legacy_response)
    compare_mock = MagicMock()

    with (
        patch("app.ai.engine.conversation.get_runtime_mode", return_value="shadow"),
        patch("app.ai.engine.conversation.should_run_shadow_probe", return_value=(True, "enabled")),
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(ConversationEngine, "_record_runtime_shadow_compare", new=compare_mock),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
    ):
        result = await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="继续")],
            tools=[ToolDefinition(name="get_page_context", description="Read page context")],
            selected_skill_names=["page_skill"],
            context_sources=[],
            conversation_id=9001,
        )

    assert result is legacy_response
    assert legacy_call.await_count == 1
    assert runtime_call.await_count == 1
    assert runtime_call.await_args.kwargs["shadow_mode"] is True
    compare_mock.assert_called_once()


@pytest.mark.asyncio
async def test_call_llm_shadow_mode_skips_runtime_compare_when_guardrail_blocks() -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    agent = _build_agent()
    legacy_response = ChatResponse(
        message=ChatMessage(role="assistant", content="legacy reply"),
        total_tokens=8,
    )
    runtime_call = AsyncMock()
    legacy_call = AsyncMock(return_value=legacy_response)

    with (
        patch("app.ai.engine.conversation.get_runtime_mode", return_value="shadow"),
        patch(
            "app.ai.engine.conversation.should_run_shadow_probe",
            return_value=(False, "sampled_out"),
        ),
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
    ):
        result = await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="继续")],
            tools=[ToolDefinition(name="get_page_context", description="Read page context")],
            conversation_id=9002,
            tenant_id=1,
        )

    assert result is legacy_response
    assert legacy_call.await_count == 1
    assert runtime_call.await_count == 0


def test_shadow_probe_guardrails_cover_whitelist_sampling_and_rate_limit(monkeypatch) -> None:
    reset_shadow_rate_limiter_for_tests()
    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED", "1")

    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_WHITELIST", "tenant:99")
    allowed, reason = should_run_shadow_probe(
        agent_id=1,
        tenant_id=1,
        conversation_id=9001,
    )
    assert allowed is False
    assert reason == "not_in_whitelist"

    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_WHITELIST", "")
    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_SAMPLE_RATE", "0")
    allowed, reason = should_run_shadow_probe(
        agent_id=1,
        tenant_id=1,
        conversation_id=9001,
    )
    assert allowed is False
    assert reason == "sampled_out"

    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("CLAUDE_CODE_STYLE_RUNTIME_SHADOW_MAX_PER_MINUTE", "1")
    first_allowed, first_reason = should_run_shadow_probe(
        agent_id=1,
        tenant_id=1,
        conversation_id=9001,
    )
    second_allowed, second_reason = should_run_shadow_probe(
        agent_id=1,
        tenant_id=1,
        conversation_id=9001,
    )
    assert first_allowed is True
    assert first_reason == "enabled"
    assert second_allowed is False
    assert second_reason == "rate_limited"
