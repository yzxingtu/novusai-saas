"""
Test type: behavioral
Scope: ConversationEngine prepare-execution routing and invalid runtime metadata guard behavior.
Mock strategy: model router, KB loading, and optimizer edges are faked; prepare-execution
logic and tool-policy filtering run through the real implementation.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.context import get_context_engine
from app.ai.context.engine import ConversationContextEngine
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine, _SyncIOAdapter
from app.ai.engine.stream_runtime_contract import build_stream_runtime_contract
from app.ai.engine.types import ExecutionRequest, IntentPlan, ToolUsePolicy
from app.ai.runtime.context_capability_bridge import DefaultContextCapabilityBridge
from app.ai.runtime.contracts import ContextCapabilityAwareness
from app.ai.runtime.types import CapabilityDescriptor
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
            ToolDefinition(name="query_records", description="Query platform data"),
        ]
    )


def _build_plugin_research_skill_result() -> SkillResolveResult:
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
        ]
    )


def _build_structured_skill_result() -> SkillResolveResult:
    return SkillResolveResult(
        tools=[
            ToolDefinition(name="get_current_weather", description="Current weather"),
            ToolDefinition(name="get_weather_forecast", description="Forecast"),
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch the url"),
        ]
    )


def _build_intent_plan(*kinds: str) -> list[IntentPlan]:
    family_by_kind = {
        "web_research": "web_research",
        "weather_query": "weather",
        "time_query": "time_ops",
    }
    return [
        IntentPlan(
            intent_id=f"intent-{index}",
            kind=kind,
            family=(
                "memory"
                if kind.startswith("memory_")
                else family_by_kind.get(kind, "none")
            ),
            order=index,
            user_visible_label=kind,
            source_text="test intent",
            shortcircuit=kind.startswith("memory_"),
            metadata={},
        )
        for index, kind in enumerate(kinds, start=1)
    ]


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


@pytest.fixture(autouse=True)
def _stub_capability_awareness_runtime(monkeypatch):
    async def _resolve_runtime_model_capabilities(self, *, agent):
        model = getattr(agent, "model", None)
        if model is None:
            return {"supports_audio": False}
        return {
            "supports_audio": bool(getattr(model, "supports_audio", False)),
            "supports_video": bool(getattr(model, "supports_video", False)),
            "supports_vision": bool(getattr(model, "supports_vision", False)),
        }

    async def _compute_awareness(self, **_kwargs):
        return ContextCapabilityAwareness(enabled=True)

    monkeypatch.setattr(
        DefaultContextCapabilityBridge,
        "resolve_runtime_model_capabilities",
        _resolve_runtime_model_capabilities,
    )
    monkeypatch.setattr(
        DefaultContextCapabilityBridge,
        "compute_awareness",
        _compute_awareness,
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
async def test_prepare_execution_uses_current_user_text_for_optimizer_before_research_starts() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    assert prep.execution_path == "normal"
    assert [intent.kind for intent in prep.intent_plan] == ["web_research"]
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="native_web_search_first:web_research",
    )


@pytest.mark.asyncio
async def test_prepare_execution_selects_web_tools_for_news_queries() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="查今天新闻，给我 3 条来源。"),
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
            skill_result=_build_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == ["web_research"]
    assert {tool.name for tool in prep.tools} >= {"web_search", "fetch_url"}
    assert prep.tool_use_policy.family == "web_research"


@pytest.mark.asyncio
async def test_prepare_execution_preserves_active_web_research_state_without_optimizer_bias() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ChatMessage(
                role="tool", content="Search results for: sample topic public info"
            ),
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
    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()


@pytest.mark.asyncio
async def test_prepare_execution_keeps_generic_follow_up_in_research_state() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ChatMessage(
                role="tool", content="Search results for: sample topic public info"
            ),
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
    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()


@pytest.mark.asyncio
async def test_prepare_execution_does_not_inherit_data_ops_for_generic_follow_up_without_anchor() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
                            "name": "crm_update_record",
                            "arguments": '{"form_session_id":"fs_demo","fields":{"name":"Alice"}}',
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="Form fill succeeded."),
            ChatMessage(role="assistant", content="Done."),
            ChatMessage(role="user", content="继续"),
        ],
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
            ToolDefinition(name="crm_update_record", description="Fill active form"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
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

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is False
    assert prep.continuation_context.family is None
    assert prep.continuation_context.origin == "none"
    assert [tool.name for tool in prep.tools] == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics.get("continuation_source") is None


@pytest.mark.asyncio
async def test_prepare_execution_clears_page_continuation_for_long_no_tool_direct_reply() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="看看本页面的内容"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_page_1",
                        "type": "function",
                        "function": {
                            "name": "crm_lookup",
                            "arguments": "{}",
                        },
                        "success": True,
                    }
                ],
            ),
            ChatMessage(role="tool", content="page context payload"),
            ChatMessage(role="assistant", content="这里是第一页摘要。"),
            ChatMessage(
                role="user",
                content=(
                    "CASE-STREAM-UX-0418U 不要使用任何工具。"
                    "输出 40 行，每行格式为 LINE_XX_0418U，其中 XX 从 01 到 40。"
                    "不要使用代码块，不要省略。"
                ),
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is False
    assert prep.continuation_context.family is None
    assert prep.continuation_context.origin == "none"
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics.get("continuation_source") is None


@pytest.mark.asyncio
async def test_prepare_execution_does_not_restore_invalid_runtime_continuation() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(role="user", content="看看本页面的内容"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_page_1",
                        "type": "function",
                        "function": {
                            "name": "crm_lookup",
                            "arguments": "{}",
                        },
                        "success": True,
                    }
                ],
                metadata={
                    "turn_record": {
                        "active_intent_kind": "data_workflow",
                        "last_page_key": "admin.runtime.records",
                    }
                },
            ),
            ChatMessage(role="tool", content="page context payload"),
            ChatMessage(role="assistant", content="这里是第一页摘要。"),
            ChatMessage(role="user", content="继续看"),
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.continuation_context is not None
    assert prep.continuation_context.active is False
    assert prep.continuation_context.family is None
    assert prep.continuation_context.origin == "none"
    assert getattr(prep.continuation_context, "page_operation_names", []) == []
    assert getattr(prep.continuation_context, "page_context_attached", False) is False
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics["candidate_tool_names"] == []
    assert prep.diagnostics.get("continuation_source") is None


@pytest.mark.asyncio
async def test_prepare_execution_ignores_page_context_for_local_page_content_request() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="看看本页面的内容")],
    )

    captured: dict[str, object] = {}

    def _fake_optimize(tools, user_query, **kwargs):
        captured["user_query"] = user_query
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            tools=[
                tool
                for tool in tools
                if tool.name in {"crm_lookup", "crm_read_record", "crm_update_record"}
            ],
            skipped=False,
            total=len(tools),
            selected=3,
        )

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
            ToolDefinition(name="crm_update_record", description="Update CRM record"),
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

    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics["candidate_tool_names"] == []


@pytest.mark.asyncio
async def test_prepare_execution_ignores_page_capability_request() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="帮我添加一个测试智能体，具体内容你来决定",
            ),
        ],
    )

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_open_record", description="Open CRM record"),
            ToolDefinition(
                name="crm_get_record_state",
                description="Get CRM form state",
            ),
            ToolDefinition(name="crm_update_record", description="Update CRM form"),
            ToolDefinition(name="crm_submit_record", description="Submit CRM form"),
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

    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.tools == []
    assert prep.diagnostics["candidate_tool_names"] == []


@pytest.mark.asyncio
async def test_prepare_execution_does_not_discover_forms_from_page_context() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="帮我添加一个测试的智能体 在本页面",
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics["candidate_tool_names"] == []


@pytest.mark.asyncio
async def test_prepare_execution_routes_weather_requests_to_weather_family(
    mock_db,
) -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user", content="请告诉我今天天气怎么样，并预报下周的走向。"
            ),
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
    assert {tool.name for tool in prep.tools} == {"get_current_weather"}
    assert prep.tool_use_policy.allowed_tool_names == ["get_current_weather"]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_weather_tools_for_mixed_weather_and_health_turn() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="我有点头疼，今天北京天气怎么样")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
            ToolDefinition(name="crm_list_records", description="Read UI table"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
            ToolDefinition(name="query_records", description="Query platform data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
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
    assert prep.tool_use_policy.allowed_tool_names == ["get_current_weather"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_weather_only_for_mixed_page_and_weather_request() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="先看看本页面，再查北京天气")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
            ToolDefinition(name="crm_list_records", description="Read UI table"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
            ToolDefinition(name="query_records", description="Query platform data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
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
    assert prep.tool_use_policy.allowed_tool_names == ["get_current_weather"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]
    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["weather_query"]
    assert prep.diagnostics["capability_injection_decision"] == {
        "all_shortcircuit": True,
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": "all_shortcircuit",
    }


@pytest.mark.asyncio
async def test_prepare_execution_keeps_weather_only_for_mixed_page_health_phrase() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[
            ChatMessage(
                role="user", content="我有点头疼，先看看当前数据集，再查北京天气"
            )
        ],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
            ToolDefinition(name="crm_list_records", description="Read UI table"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
            ToolDefinition(name="query_records", description="Query platform data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
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
    assert prep.tool_use_policy.allowed_tool_names == ["get_current_weather"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]


@pytest.mark.asyncio
async def test_prepare_execution_does_not_restore_invalid_runtime_family_from_optimizer() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="先看看本页面，再查北京天气")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
            ToolDefinition(name="crm_list_records", description="Read UI table"),
            ToolDefinition(
                name="get_current_weather", description="Get current weather"
            ),
            ToolDefinition(
                name="get_weather_forecast", description="Get weather forecast"
            ),
            ToolDefinition(name="query_records", description="Query platform data"),
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
                    "crm_lookup",
                    "crm_read_record",
                    "crm_list_records",
                }
            ],
            skipped=False,
            total=len(tools),
            selected=3,
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

    assert prep.tool_use_policy.family == "weather"
    assert prep.tool_use_policy.allowed_tool_names == ["get_current_weather"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]


@pytest.mark.asyncio
async def test_prepare_execution_prefers_web_research_on_first_turn_even_with_page_context() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查询一下 小猫为什么 爱吃鱼")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_update_record", description="Update CRM record"),
            ToolDefinition(name="query_records", description="Query platform data"),
            ToolDefinition(name="create_records", description="Create data"),
            ToolDefinition(name="update_records", description="Update data"),
            ToolDefinition(name="delete_records", description="Delete data"),
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
        mode="required",
        allowed_tool_names=[
            "web_search",
            "fetch_url",
        ],
        retry_on_contract_breach=True,
        reason="native_web_search_first:web_research",
    )
    assert [tool.name for tool in prep.tools] == [
        "web_search",
        "fetch_url",
    ]


@pytest.mark.asyncio
async def test_prepare_execution_keeps_non_zero_selected_count_for_explicit_web_request() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role="user", content="联网查一下今天的开源模型发布")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="crm_lookup", description="Lookup CRM records"),
            ToolDefinition(name="crm_read_record", description="Read CRM record"),
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
async def test_prepare_execution_injects_absolute_date_anchor_for_date_sensitive_web_turn() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
        mode="required",
        allowed_tool_names=["get_current_time"],
        retry_on_contract_breach=True,
        reason="intent:time_query",
    )
    assert [tool.name for tool in prep.tools] == ["get_current_time"]
    assert "[RUNTIME CLOCK]" not in prep.messages[0].content
    assert prep.diagnostics["capability_injection_decision"] == {
        "all_shortcircuit": True,
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": "all_shortcircuit",
    }


@pytest.mark.asyncio
async def test_prepare_execution_exposes_pruning_diagnostics() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
async def test_prepare_execution_prunes_only_old_large_tool_results_from_prompt() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
                            "name": "query_records",
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
async def test_prepare_execution_keeps_pending_confirmation_tool_rounds_intact() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    pending_payload = '{"requires_confirmation": true, "action": "tool_consent", "tool_name": "delete_records"}'
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
                            "name": "delete_records",
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
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
                        "id": "call_small",
                        "function": {
                            "name": "query_records",
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
    assert (
        assistant_tool_round.tool_calls[0]["function"]["arguments"]
        == '{"sql":"select * from demo"}'
    )
    assert prep.prune_stats["pruned_tool_call_count"] == 0


@pytest.mark.asyncio
async def test_prepare_execution_builds_compaction_snapshot_sidecar_when_threshold_exceeded() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ChatMessage(
                role="user",
                content="用户先描述了一个很长很长的背景信息，需要系统记住业务上下文和限制条件。",
            ),
            ChatMessage(
                role="assistant",
                content="助手先给出了较长的解释，说明之前已经执行过一些检索和整理工作。",
            ),
            ChatMessage(
                role="user",
                content="然后用户继续补充了另外一段较长说明，希望后续回答都基于这个背景。",
            ),
            ChatMessage(
                role="assistant", content="最近一轮助手回复，应该保留在最近上下文中。"
            ),
            ChatMessage(role="user", content="请继续回答。"),
        ],
        input_variables={},
    )

    snap_store: dict[str, Any] = {}

    async def fake_get_snapshot(
        *,
        db: Any,
        tenant_id: int | None,
        conversation_id: int | None,
    ) -> dict[str, Any] | None:
        _ = db, tenant_id, conversation_id
        return snap_store.get("snap")

    async def fake_upsert_snapshot(
        *,
        db: Any,
        tenant_id: int | None,
        conversation_id: int | None,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any]:
        _ = db, tenant_id, conversation_id
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
        patch.object(
            ConversationContextEngine,
            "_build_compact_summary",
            return_value="Facade summary",
        ) as build_compact_summary,
        patch(
            "app.ai.context.engine_runtime_support.load_compaction_snapshot",
            new=AsyncMock(side_effect=fake_get_snapshot),
        ),
        patch(
            "app.ai.context.engine_runtime_support.persist_compaction_snapshot",
            new=AsyncMock(side_effect=fake_upsert_snapshot),
        ) as upsert_snapshot,
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=SkillResolveResult(tools=[]),
        )

    assert prep.context_compacted is True
    assert prep.compact_summary == "Facade summary"
    assert "[COMPACTED CONTEXT SUMMARY]" in prep.messages[0].content
    assert prep.system_prompt_additions
    build_compact_summary.assert_called_once()
    # Second persist skipped when snapshot unchanged (assemble + compact dedup).
    assert upsert_snapshot.await_count == 1


@pytest.mark.asyncio
async def test_context_engine_after_turn_refreshes_compaction_snapshot() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            {
                "role": "assistant",
                "content": "第一轮助手回答，内容也足够长以触发压缩。",
            },
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    request.messages = [
        ChatMessage(
            role="user",
            content="search online and keep my preferred writing style",
        )
    ]
    request.messages = [
        ChatMessage(role="user", content="search online email writing tips")
    ]
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
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=_build_intent_plan("memory_recall"),
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
            skill_result=_build_skill_result(),
        )

    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {"count": 1, "scope_type": "user_agent"}
    assert "[LONG-TERM MEMORY RECALL]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_injects_profile_snapshot_before_recall() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=_build_intent_plan("memory_recall"),
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
            skill_result=_build_skill_result(),
        )

    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {
        "count": 0,
        "profile_snapshot": True,
        "scope_type": "user_agent",
    }
    assert "[PROFILE SNAPSHOT]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_skips_memory_vector_recall_for_short_acknowledgement() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ChatMessage(role="user", content="好的"),
        ],
        input_variables={},
    )
    provider = MagicMock()
    provider.profile = AsyncMock(return_value=None)
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
            skill_result=_build_skill_result(),
        )

    provider.profile.assert_not_awaited()
    provider.recall.assert_not_awaited()
    assert prep.memory_recalled is False
    assert prep.memory_recall_slice is None


@pytest.mark.asyncio
async def test_prepare_execution_skips_runtime_capability_summary_when_dynamic_awareness_enabled() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
                kind="capability_pack",
                source="skill_package:research",
                description="Search and fetch public information",
                metadata={"family": "web_research"},
            )
        ],
    )

    with (
        patch.object(
            DefaultContextCapabilityBridge,
            "compute_awareness",
            new=AsyncMock(return_value=ContextCapabilityAwareness(enabled=True)),
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
    assert "[TOOL RUNTIME SUMMARY]" in prep.messages[0].content
    assert "[CAPABILITY REPORTING]" not in prep.messages[0].content
    assert "[TURN CAPABILITIES]" not in prep.messages[0].content
    assert "You have 2 tool(s) available" not in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_keeps_runtime_capability_summary_when_dynamic_awareness_disabled() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
                kind="capability_pack",
                source="skill_package:research",
                description="Search public information",
                metadata={"family": "web_research"},
            )
        ],
    )

    with (
        patch.object(
            DefaultContextCapabilityBridge,
            "compute_awareness",
            new=AsyncMock(return_value=ContextCapabilityAwareness(enabled=False)),
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
    assert "[TOOL RUNTIME SUMMARY]" in prep.messages[0].content
    assert "[TURN CAPABILITIES]" not in prep.messages[0].content
    assert "runtime.selected_skills=" not in prep.messages[0].content
    assert prep.diagnostics["runtime_capability_summary"]["selected_skill_names"] == []
    assert (
        prep.diagnostics["runtime_capability_summary"]["selection_semantics"]
        == "capability_reporting_inventory"
    )
    assert prep.diagnostics["runtime_capability_summary"]["selection_live"] is False
    assert prep.diagnostics["runtime_capability_summary"]["live_turn_bound"] is False
    assert prep.diagnostics["turn_skill_activation"] == {
        "applied": True,
        "reason": "capability_reporting_query",
        "tool_count": 1,
        "selected_tool_names": ["web_search"],
        "skill_count": 1,
        "selected_skill_names": ["Research Skill"],
        "inventory_tool_count": 1,
        "inventory_selected_tool_names": ["web_search"],
        "inventory_skill_count": 1,
        "inventory_selected_skill_names": ["Research Skill"],
    }
    assert "knowledge_base_hint" not in prep.diagnostics["runtime_capability_summary"]
    assert "page_context_hint" not in prep.diagnostics["runtime_capability_summary"]
    assert "memory_hint" not in prep.diagnostics["runtime_capability_summary"]
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"][
            "selection_semantics"
        ]
        == "capability_reporting_inventory"
    )
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"]["selection_live"]
        is False
    )
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"]["live_turn_bound"]
        is False
    )


@pytest.mark.asyncio
async def test_prepare_execution_combined_kb_request_does_not_emit_retired_data_policy() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    agent = _build_agent()
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        messages=[
            ChatMessage(
                role="user",
                content="请统计最近7天创建的终端用户数量，再根据已绑定知识库概括产品主要功能",
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

    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="web_search", description="Search the web"),
            ToolDefinition(name="fetch_url", description="Fetch a webpage"),
            ToolDefinition(name="query_records", description="Query platform data"),
        ]
    )

    async def _fake_inject_rag_context(
        _db,
        _agent,
        messages,
        _tenant_id,
        **_kwargs,
    ):
        return (
            messages + [ChatMessage(role="system", content="[KB HIT] product-doc")],
            [{"kb_id": 101, "chunk_id": "product-doc"}],
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
        patch("app.ai.tools.optimizer.optimize_tools", side_effect=_fake_optimize),
    ):
        prep = await engine._prepare_execution(
            agent,
            request,
            skill_result=skill_result,
        )

    assert prep.tool_use_policy.mode in {"auto", "required"}
    assert "knowledge_base" in prep.diagnostics["context_source_kinds"]


@pytest.mark.asyncio
async def test_prepare_execution_assembles_kb_memory_and_plugin_skill_without_page_context() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ChatMessage(role="user", content="请联网结合知识库给我总结"),
        ],
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
        patch(
            "app.services.ai.agent_kb_binding_service.AgentKBBindingService.get_agent_kb_bindings_with_metadata",
            new=AsyncMock(
                return_value=[
                    {
                        "knowledge_base_id": 101,
                        "name": "KB-101",
                        "weight": 1.0,
                    }
                ]
            ),
        ),
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=_build_intent_plan(
                "memory_recall",
                "knowledge_query",
                "web_research",
            ),
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
            skill_result=_build_plugin_research_skill_result(),
        )

    assert prep.capability_bundle is not None
    assert prep.capability_bundle.selected_skill_names == ["Plugin Research Skill"]
    context_source_kinds = {
        source.kind for source in prep.capability_bundle.context_sources
    }
    assert context_source_kinds >= {
        "skill",
        "knowledge_base",
        "long_term_memory",
    }
    assert "page_context" not in context_source_kinds
    assert prep.diagnostics["selected_skill_names"] == ["Plugin Research Skill"]
    assert prep.diagnostics["selected_tool_names"]
    assert prep.rag_source_kinds == ["formal_kb"]
    assert prep.memory_recalled is True
    assert prep.memory_recall_slice == {
        "count": 1,
        "profile_snapshot": True,
        "scope_type": "user_agent",
    }
    system_content = prep.messages[0].content
    assert "[LONG-TERM MEMORY RECALL]" in system_content
    assert "[PROFILE SNAPSHOT]" in system_content


@pytest.mark.asyncio
async def test_prepare_execution_deduplicates_selected_skill_names_in_capability_bundle() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
                kind="capability_pack",
                source="skill_package:plugin.research",
            ),
            CapabilityDescriptor(
                name="Plugin Research Skill",
                kind="capability_pack",
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
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
            ToolDefinition(name="delete_records", description="Delete data"),
        ],
        tool_consent_modes={
            "web_search": "ask",
            "delete_records": "ask",
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
    assert "delete_records" not in prep.tool_consent_modes


@pytest.mark.asyncio
async def test_prepare_execution_trusted_auto_bypasses_readonly_weather_consent() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        interaction_mode="trusted_auto",
        trust_policy_ref={
            "policy_ids": [1],
            "allowed_tool_names": [],
            "tool_families": [],
            "risk_level_cap": "read",
        },
        messages=[ChatMessage(role="user", content="帮我查一下西安现在的天气")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="get_current_weather", description="Current weather"),
        ],
        tool_consent_modes={
            "get_current_weather": "ask",
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

    assert prep.tool_consent_modes["get_current_weather"] == "auto"


@pytest.mark.asyncio
async def test_prepare_execution_trusted_auto_bypasses_readonly_even_without_trust_policy_ref() -> (
    None
):
    """trust_policy_ref=None must not block the readonly whitelist in trusted_auto."""
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        interaction_mode="trusted_auto",
        trust_policy_ref=None,  # <-- the key difference
        messages=[ChatMessage(role="user", content="今天天气怎么样")],
        input_variables={},
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="get_current_weather", description="Current weather"),
        ],
        tool_consent_modes={
            "get_current_weather": "ask",
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

    assert prep.tool_consent_modes["get_current_weather"] == "auto"


@pytest.mark.asyncio
async def test_prepare_execution_does_not_bypass_risk_cap_for_data_ops() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        trust_policy_ref={
            "policy_ids": [2],
            "allowed_tool_names": [],
            "tool_families": ["data_ops"],
            "risk_level_cap": "read",
        },
        messages=[ChatMessage(role="user", content="继续")],
    )
    skill_result = SkillResolveResult(
        tools=[
            ToolDefinition(name="crm_update_record", description="Update CRM form"),
        ],
        tool_consent_modes={
            "crm_update_record": "ask",
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

    assert prep.tool_consent_modes["crm_update_record"] == "ask"


@pytest.mark.asyncio
async def test_call_llm_routes_non_stream_to_runtime_query_engine_when_active() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
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
    assert runtime_call.await_args.kwargs["skip_metering_preflight"] is False
    assert legacy_call.await_count == 0


@pytest.mark.asyncio
async def test_call_llm_uses_runtime_query_engine_only() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    agent = _build_agent()
    runtime_response = ChatResponse(
        message=ChatMessage(role="assistant", content="runtime reply"),
        total_tokens=7,
    )
    runtime_engine = SimpleNamespace(
        turn_record=SimpleNamespace(protocol_path="responses")
    )
    runtime_call = AsyncMock(return_value=(runtime_response, runtime_engine))
    legacy_call = AsyncMock()

    with (
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
    ):
        result = await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="只做普通问答")],
            tools=[ToolDefinition(name="web_search", description="Search web")],
        )

    assert result is runtime_response
    assert runtime_call.await_count == 1
    assert runtime_call.await_args.kwargs["skip_metering_preflight"] is False
    assert legacy_call.await_count == 0


@pytest.mark.asyncio
async def test_call_llm_runtime_errors_do_not_fallback_to_legacy() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    agent = _build_agent()
    runtime_call = AsyncMock(side_effect=RuntimeError("runtime-v2 failed"))
    legacy_call = AsyncMock()

    with (
        patch.object(ConversationEngine, "_call_runtime_query_turn", new=runtime_call),
        patch.object(BaseEngine, "_call_llm", new=legacy_call),
        pytest.raises(RuntimeError, match="runtime-v2 failed"),
    ):
        await engine._call_llm(
            agent=agent,
            messages=[ChatMessage(role="user", content="继续")],
            tools=[ToolDefinition(name="crm_lookup", description="Lookup CRM records")],
            selected_skill_names=["page_skill"],
            context_sources=[],
            conversation_id=9001,
        )

    assert runtime_call.await_count == 1
    assert legacy_call.await_count == 0


@pytest.mark.asyncio
async def test_sync_io_adapter_fast_text_round_passes_low_reasoning_override() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    engine._call_llm = AsyncMock(
        return_value=ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=3,
        )
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        user_role="tenant_admin",
        billing_context={},
        messages=[ChatMessage(role="user", content="你好")],
    )
    sync_adapter = _SyncIOAdapter(
        engine=engine,
        agent=_build_agent(),
        request=request,
        prep=SimpleNamespace(
            all_tools=[],
            route_result=None,
            execution_path="fast",
        ),
        selected_skill_names=[],
        context_sources=[],
        runtime_contract=build_stream_runtime_contract(engine),
    )

    await sync_adapter.call_llm(
        messages=[ChatMessage(role="user", content="你好")],
        tools=[],
        tool_use_policy=ToolUsePolicy(),
    )

    assert engine._call_llm.await_count == 1
    kwargs = engine._call_llm.await_args.kwargs
    assert kwargs["execution_path"] == "fast"
    assert kwargs["extra_kwargs"] == {"_runtime_reasoning_effort_override": "low"}


@pytest.mark.asyncio
async def test_prepare_execution_builds_deep_structured_plan_for_666_style_turn() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="请帮我查一下今天北京的天气，然后联网查一下长沙去北京的高铁票，再帮我阅读一下本页面都有什么内容",
            )
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
            skill_result=_build_structured_skill_result(),
        )

    assert [intent.family for intent in prep.intent_plan] == [
        "weather",
        "web_research",
    ]
    assert [intent.kind for intent in prep.intent_plan] == [
        "weather_query",
        "web_research",
    ]
    assert prep.execution_path == "normal"
    assert prep.execution_budget is not None
    assert prep.execution_budget.max_candidate_tools == 7
    assert prep.execution_budget.candidate_tools_count == len(prep.tools)
    assert [tool.name for tool in prep.tools] == [
        "get_current_weather",
        "web_search",
        "fetch_url",
    ]
    assert prep.active_intent_id == "intent-1"
    assert prep.tool_use_policy.family == "weather"
    assert prep.tool_use_policy.reason == "intent:weather_query"


@pytest.mark.asyncio
async def test_prepare_execution_preserves_native_first_for_web_first_multi_intent_turn() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[
            ChatMessage(
                role="user",
                content="联网查今天 OpenAI 新闻，再告诉我北京天气",
            )
        ],
    )

    with (
        patch(
            "app.ai.rag_injector.load_agent_kb_bindings",
            new=AsyncMock(return_value=([], {})),
        ),
        patch("app.ai.routing.router.ModelRouter", new=_FakeRouter),
        patch(
            "app.ai.engine.intent_planner.IntentPlanner.plan_turn",
            return_value=_build_intent_plan("web_research", "weather_query"),
        ),
    ):
        prep = await engine._prepare_execution(
            _build_agent(),
            request,
            skill_result=_build_structured_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == [
        "web_research",
        "weather_query",
    ]
    assert prep.active_intent_id == "intent-1"
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="required",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="native_web_search_first:web_research",
    )


@pytest.mark.asyncio
async def test_prepare_execution_current_weather_only_avoids_forecast_tool() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我查一下北京现在的天气")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["weather_query"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]
    assert prep.intent_plan[0].allowed_tool_names == ["get_current_weather"]
    assert prep.execution_budget is not None
    assert prep.execution_budget.max_tool_rounds == 2
    assert prep.diagnostics["capability_injection_decision"] == {
        "all_shortcircuit": True,
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": "all_shortcircuit",
    }


@pytest.mark.asyncio
async def test_prepare_execution_page_summary_turn_uses_no_page_tools() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我阅读一下本页面都有什么内容")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.intent_plan[0].allowed_tool_names == []
    assert prep.tool_use_policy == ToolUsePolicy()
    assert prep.diagnostics["capability_injection_decision"] == {
        "all_shortcircuit": True,
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": "all_shortcircuit",
    }


@pytest.mark.asyncio
async def test_prepare_execution_record_search_turn_uses_web_search_not_page_tools() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我搜索一下包含'供应商'的记录")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.execution_path == "normal"
    assert [tool.name for tool in prep.tools] == [
        "web_search",
        "fetch_url",
    ]
    assert prep.execution_budget is not None
    assert prep.execution_budget.max_candidate_tools == 7
    assert prep.execution_budget.candidate_tools_count == len(prep.tools)
    assert prep.execution_budget.first_exceeded_reason() is None


@pytest.mark.asyncio
async def test_prepare_execution_record_search_with_weather_keyword_uses_weather_only() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我搜索一下包含'天气'的记录")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert prep.execution_path == "fast"
    assert [intent.kind for intent in prep.intent_plan] == ["weather_query"]
    assert [tool.name for tool in prep.tools] == ["get_current_weather"]
    assert prep.execution_budget is not None
    assert prep.execution_budget.max_candidate_tools == 3
    assert prep.execution_budget.first_exceeded_reason() is None


@pytest.mark.asyncio
async def test_prepare_execution_no_tool_turn_keeps_inventory_truth_out_of_live_selection() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="你好，简单介绍一下你自己。")],
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
            skill_result=_build_plugin_research_skill_result(),
        )

    assert prep.tools == []
    assert prep.diagnostics["selected_tool_names"] == []
    assert prep.diagnostics["selected_skill_names"] == []
    assert prep.diagnostics["turn_skill_activation"] == {
        "applied": False,
        "reason": "no_turn_skill_activation",
        "tool_count": 0,
        "selected_tool_names": [],
        "skill_count": 0,
        "selected_skill_names": [],
        "inventory_tool_count": 2,
        "inventory_selected_tool_names": [
            "web_search",
            "fetch_url",
        ],
        "inventory_skill_count": 1,
        "inventory_selected_skill_names": [
            "Plugin Research Skill",
        ],
    }
    assert prep.diagnostics["runtime_capability_summary"]["selected_skill_names"] == []
    assert (
        prep.diagnostics["runtime_capability_summary"]["selection_semantics"]
        == "turn_selected_subset"
    )
    assert prep.diagnostics["runtime_capability_summary"]["selection_live"] is True
    assert prep.diagnostics["runtime_capability_summary"]["live_turn_bound"] is True
    assert prep.diagnostics["runtime_capability_manifest"]["skills"] == []


@pytest.mark.asyncio
async def test_prepare_execution_does_not_project_invalid_runtime_tools_to_live_tools() -> (
    None
):
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我阅读一下本页面都有什么内容")],
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
            skill_result=_build_plugin_research_skill_result(),
        )

    assert prep.capability_bundle is not None
    assert prep.tools == []
    assert prep.capability_bundle.selected_skill_names == []
    assert prep.diagnostics["selected_skill_names"] == []
    assert prep.diagnostics["turn_skill_activation"]["selected_tool_names"] == []
    assert prep.diagnostics["turn_skill_activation"]["selected_skill_names"] == []
    assert prep.diagnostics["runtime_capability_summary"]["selected_skill_names"] == []
    assert (
        prep.diagnostics["runtime_capability_summary"]["selection_semantics"]
        == "turn_selected_subset"
    )
    assert prep.diagnostics["runtime_capability_summary"]["selection_live"] is True
    assert prep.diagnostics["runtime_capability_summary"]["live_turn_bound"] is True
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"][
            "selection_semantics"
        ]
        == "turn_selected_subset"
    )
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"]["selection_live"]
        is True
    )
    assert (
        prep.diagnostics["runtime_capability_manifest"]["boundaries"]["live_turn_bound"]
        is True
    )
    assert [
        item["name"]
        for item in prep.diagnostics["runtime_capability_manifest"]["skills"]
        if item["status"] == "available"
    ] == []


@pytest.mark.asyncio
async def test_prepare_execution_page_screenshot_request_uses_no_page_tools() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我给当前数据集截图")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()


@pytest.mark.asyncio
async def test_prepare_execution_editor_write_request_uses_no_page_tools() -> None:
    engine = ConversationEngine(
        db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock()
    )
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        messages=[ChatMessage(role="user", content="帮我替换当前编辑器正文并更新标题")],
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
            skill_result=_build_structured_skill_result(),
        )

    assert [intent.kind for intent in prep.intent_plan] == ["direct_reply"]
    assert prep.tools == []
    assert prep.tool_use_policy == ToolUsePolicy()
