from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine import base_tool_loop_support as tool_loop_support_mod
from app.ai.engine import tool_call_loop_runtime as runtime_mod
from app.ai.engine import tool_processor as tool_processor_mod
from app.ai.engine.base import BaseEngine
from app.ai.engine.tool_loop_session import ToolLoopSession
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
    truncate_tool_calls_after_navigation=None,
) -> runtime_mod.ToolCallLoopCallbacks:
    async def _default_followup_llm(_tools, _policy):
        return _make_response()

    return runtime_mod.ToolCallLoopCallbacks(
        ordered_requested_families_from_intents=lambda **_kwargs: [],
        truncate_tool_calls_after_navigation=(
            truncate_tool_calls_after_navigation
            or (lambda tool_calls: (tool_calls, False))
        ),
        mark_multi_family_progress=lambda **_kwargs: None,
        budget_exit_response=lambda total_tokens: ChatResponse(
            message=ChatMessage(role="assistant", content=f"budget:{total_tokens}"),
            total_tokens=total_tokens,
        ),
        build_page_no_progress_recovery=lambda **_kwargs: ([], {}),
        messages_have_blocking_pending_interaction=lambda _messages: False,
        first_incomplete_requested_family=lambda _ordered, _completed: None,
        allowed_tool_names_for_family=lambda _family, _tools, _input: [],
        build_ordered_capability_hint=lambda _families, _tools, _input: None,
        needs_fetch_url_before_summary=lambda _messages: False,
        apply_fetch_url_only_gate=lambda _messages, tools, _all_tools: tools,
        restrict_tools_to_names=lambda tools, _allowed: tools,
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


@pytest.mark.asyncio
async def test_run_tool_call_loop_returns_budget_exit_before_round_execution(
    monkeypatch,
) -> None:
    response = _make_response(
        [
            {
                "id": "tc-time",
                "type": "function",
                "function": {"name": "get_current_time", "arguments": "{}"},
            }
        ]
    )
    tools = [ToolDefinition(name="get_current_time", description="time")]
    budget = _make_budget()
    budget.prompt_tokens_used = budget.max_prompt_tokens + 1

    class _FakeProcessor:
        def __init__(self, *_args, **_kwargs):
            pass

        @staticmethod
        def approved_pending_consent_tool_names(_updates):
            return []

    monkeypatch.setattr(tool_processor_mod, "ToolCallProcessor", _FakeProcessor)
    monkeypatch.setattr(
        runtime_mod,
        "build_tool_loop_session",
        lambda **_kwargs: ToolLoopSession(
            current_response=response,
            tools_full=tools,
            all_tools_full=tools,
            effective_policy=ToolUsePolicy(),
            ordered_requested_families=[],
            has_fetch_url_in_toolset=False,
            total_tokens=13,
            completion_tokens_used=5,
            tracked_tool_rounds=0,
            tracked_tool_result_bytes=0,
        ),
    )
    monkeypatch.setattr(
        runtime_mod,
        "sync_sandbox_runtime_model_info",
        lambda **_kwargs: None,
    )

    async def _unexpected_execute_tool_round(**_kwargs):
        raise AssertionError(
            "execute_tool_round should not run when budget already exited"
        )

    monkeypatch.setattr(
        runtime_mod, "execute_tool_round", _unexpected_execute_tool_round
    )

    result = await runtime_mod.run_tool_call_loop(
        runtime=runtime_mod.ToolCallLoopRuntime(
            sandbox=MagicMock(),
            agent=SimpleNamespace(id=1),
            messages=[ChatMessage(role="user", content="what time is it?")],
            response=response,
            tools=tools,
            all_tools=tools,
            request=_make_request(),
            skip_final_call=False,
            tool_consent_modes={},
            continuation_context=None,
            tool_use_policy=ToolUsePolicy(),
            execution_budget=budget,
            starting_total_tokens=None,
            starting_completion_tokens=None,
        ),
        callbacks=_make_callbacks(),
    )

    final_response, tool_results, total_tokens, completion_tokens = result
    assert final_response is not None
    assert final_response.message.content == "budget:13"
    assert tool_results == []
    assert total_tokens == 13
    assert completion_tokens == 5
