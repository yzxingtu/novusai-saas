"""
Test type: behavioral
Scope: tool-call loop runtime control flow, budget, and tool execution states.
Mocked dependencies: local tool/model seams only; policy/runtime logic runs real.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine import base_tool_loop_support as tool_loop_support_mod
from app.ai.engine import tool_call_loop_runtime as runtime_mod
from app.ai.engine.base import BaseEngine
from app.ai.engine.tool_policy_selection_helpers import allowed_tool_names_for_family
from app.ai.engine.types import (
    ExecutionBudget,
    ExecutionRequest,
    ExecutionResult,
    ToolUsePolicy,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse


class _DummyEngine(BaseEngine):
    async def execute(self, _agent, _request) -> ExecutionResult:  # noqa: ANN001
        return ExecutionResult(success=True)


def _make_request() -> ExecutionRequest:
    return ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=7,
        conversation_id=42,
        messages=[ChatMessage(role="user", content="check runtime")],
    )


def _make_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=10,
        max_completion_tokens=20,
        max_tool_rounds=2,
        max_elapsed_ms=30000,
        max_retry_per_intent=1,
        max_candidate_tools=3,
        max_tool_result_bytes=4096,
    )


def _make_response(tool_calls: list[dict[str, object]] | None = None) -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(role="assistant", content="thinking"),
        tool_calls=tool_calls or [],
        total_tokens=3,
        output_tokens=1,
    )


def _make_callbacks(
    *,
    call_followup_llm=None,
    keep_tool_calls_for_round=None,
) -> runtime_mod.ToolCallLoopCallbacks:
    async def _default_followup_llm(_tools, _policy):
        return _make_response()

    return runtime_mod.ToolCallLoopCallbacks(
        ordered_requested_families_from_intents=lambda **_kwargs: [],
        keep_tool_calls_for_round=(
            keep_tool_calls_for_round or (lambda tool_calls: (tool_calls, False))
        ),
        mark_multi_family_progress=lambda **_kwargs: None,
        budget_exit_response=lambda total_tokens: ChatResponse(
            message=ChatMessage(role="assistant", content=f"budget:{total_tokens}"),
            total_tokens=total_tokens,
        ),
        messages_have_blocking_pending_interaction=lambda _messages: False,
        first_incomplete_requested_family=lambda _ordered, _completed: None,
        allowed_tool_names_for_family=lambda _family, _tools, _input: [],
        build_ordered_capability_hint=lambda _families, _tools, _input: None,
        restrict_tools_to_names=lambda _tools, _allowed: [],
        call_followup_llm=call_followup_llm or _default_followup_llm,
    )


@pytest.mark.asyncio
async def test_handle_tool_calls_delegates_to_runtime_helper(monkeypatch) -> None:
    engine = _DummyEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    engine._call_llm = AsyncMock(return_value=_make_response())  # type: ignore[method-assign]

    tools = [ToolDefinition(name="get_current_time", description="time")]
    request = _make_request()
    response = _make_response(
        [
            {
                "id": "tc-time",
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "arguments": "{}",
                },
            }
        ]
    )
    selected_skill_names = ["clock-skill"]
    context_sources = [SimpleNamespace(kind="time")]
    captured: dict[str, object] = {}
    sentinel = (
        ChatResponse(message=ChatMessage(role="assistant", content="done")),
        [],
        11,
        5,
    )

    async def _fake_run_tool_call_loop(*, runtime, callbacks):
        captured["runtime"] = runtime
        captured["followup"] = await callbacks.call_followup_llm([], ToolUsePolicy())
        return sentinel

    monkeypatch.setattr(
        tool_loop_support_mod,
        "run_tool_call_loop",
        _fake_run_tool_call_loop,
    )

    result = await engine._handle_tool_calls(
        agent=SimpleNamespace(id=99),
        messages=[ChatMessage(role="user", content="what time is it?")],
        response=response,
        tools=tools,
        all_tools=tools,
        request=request,
        route_result={"chosen": "mock"},
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        tool_use_policy=ToolUsePolicy(
            family="time",
            mode="required",
            allowed_tool_names=["get_current_time"],
        ),
    )

    assert result == sentinel
    runtime = captured["runtime"]
    assert runtime.agent.id == 99
    assert runtime.response is response
    assert runtime.tools == tools
    assert runtime.all_tools == tools
    assert runtime.request is request

    engine._call_llm.assert_awaited_once()
    kwargs = engine._call_llm.await_args.kwargs
    assert kwargs["agent"].id == 99
    assert kwargs["messages"][0].content == "what time is it?"
    assert kwargs["tools"] == []
    assert kwargs["all_tool_names"] == ["get_current_time"]
    assert kwargs["tool_use_policy"].family == "none"
    assert kwargs["selected_skill_names"] == selected_skill_names
    assert kwargs["context_sources"] == context_sources
    assert kwargs["route_result"] == {"chosen": "mock"}
    assert kwargs["log_user_type"] == request.user_role


def test_allowed_tool_names_for_family_unknown_family_stays_empty() -> None:
    """Test type: structural; missing family must not reopen all tool names."""
    tools = [ToolDefinition(name="clock_now", description="time")]

    assert (
        allowed_tool_names_for_family(
            "missing_family",
            tools,
            None,
        )
        == []
    )
