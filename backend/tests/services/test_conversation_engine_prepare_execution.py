from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.context import get_context_engine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest, ToolUsePolicy
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
    assert captured["kwargs"] == {"preferred_family": "web_research"}
    assert [tool.name for tool in prep.tools] == ["web_search", "fetch_url"]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="web_research",
        mode="auto",
        allowed_tool_names=["web_search", "fetch_url"],
        retry_on_contract_breach=True,
        reason="soft_hint:web_research",
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
        reason="active_continuation:web_research",
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
        reason="active_continuation:web_research",
    )


@pytest.mark.asyncio
async def test_prepare_execution_requires_page_ops_for_generic_follow_up_after_page_tool() -> None:
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

    assert captured["kwargs"] == {"preferred_family": "page_ops"}
    assert [tool.name for tool in prep.tools] == [
        "invoke_page_operation",
        "get_page_context",
        "pageop_fill_form",
    ]
    assert prep.tool_use_policy == ToolUsePolicy(
        family="page_ops",
        mode="auto",
        allowed_tool_names=[
            "invoke_page_operation",
            "get_page_context",
            "pageop_fill_form",
        ],
        retry_on_contract_breach=True,
        reason="generic_follow_up_after:invoke_page_operation",
    )


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
            "get_page_context",
            "invoke_page_operation",
            "web_search",
            "fetch_url",
        ],
        retry_on_contract_breach=True,
        reason="soft_hint:web_research",
    )
    assert [tool.name for tool in prep.tools] == [
        "get_page_context",
        "invoke_page_operation",
        "web_search",
        "fetch_url",
    ]


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
        reason="soft_hint:time_ops",
    )
    assert [tool.name for tool in prep.tools] == ["get_current_time"]
    assert "[RUNTIME CLOCK]" in prep.messages[0].content


@pytest.mark.asyncio
async def test_prepare_execution_exposes_legacy_context_engine_diagnostics() -> None:
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

    assert prep.context_engine_id == "legacy"
    assert prep.prune_stats is not None
    assert prep.prune_stats["mode"] == "transient_tool_result_pruning"
    assert prep.diagnostics["context_engine_id"] == "legacy"


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
        patch("app.ai.context.engine.LegacyContextEngine.compact", mock_compact),
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
        request=request,
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
