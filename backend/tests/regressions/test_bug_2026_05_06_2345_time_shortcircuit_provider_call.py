"""
Test type: behavioral
Regression for: BUG-2026-05-06-2345-time-shortcircuit-provider-call
中文: 对话 2345 中“现在是几点钟？”已经命中 get_current_time，却仍然请求上游模型。
EN: Conversation 2345 hit get_current_time but still requested the upstream model.
Scope: TurnExecutor deterministic time-tool short-circuit.
Real dependencies: TurnExecutor, ExecutionStateMachine, RecoveryManager, and
tool-result finalization logic run real code.
Mocked dependencies: Only the transport adapter is faked; the test asserts no
LLM response body is consumed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from app.ai.engine.types import IntentPlan, ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


class _NoProviderTimeIO:
    def __init__(self, *, time_output: str) -> None:
        self.time_output = time_output
        self.call_history: list[dict[str, Any]] = []
        self.tool_call_history: list[dict[str, Any]] = []

    async def call_llm(self, **kwargs: Any) -> ModelRoundResult:
        self.call_history.append(dict(kwargs))
        raise AssertionError("conversation 2345 time short-circuit called provider")

    async def handle_tool_calls(self, **kwargs: Any) -> ToolBatchResult:
        self.tool_call_history.append(dict(kwargs))
        return ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="call_time",
                    name="get_current_time",
                    success=True,
                    output=self.time_output,
                )
            ],
            total_tokens=0,
            completion_tokens_used=0,
        )

    async def finalize_partial_output(self, **_kwargs: Any) -> tuple[str, int, int]:
        raise AssertionError("time short-circuit should not finalize partial output")

    async def finalize_completed_output(
        self,
        **kwargs: Any,
    ) -> tuple[str, int, int]:
        response = kwargs["response"]
        if response is not None and str(response.message.content or "").strip():
            return (
                str(response.message.content).strip(),
                int(kwargs.get("total_tokens") or 0),
                int(kwargs.get("completion_tokens_used") or 0),
            )
        state = kwargs["state"]
        tool_results = kwargs["tool_results"]
        return (
            RecoveryManager.build_completed_output(
                state.intent_plan,
                tool_results=tool_results,
                reason=str(kwargs.get("reason") or "completed"),
            ),
            int(kwargs.get("total_tokens") or 0),
            int(kwargs.get("completion_tokens_used") or 0),
        )

    def should_retry_tool_contract_breach(self, **_kwargs: Any):
        return False, None, ""

    def analyze_post_tool_contract_breach(self, **_kwargs: Any):
        return None, None, {}

    @staticmethod
    def restrict_tools_to_names(
        tools: list[ToolDefinition],
        allowed_tool_names: list[str] | None,
    ) -> list[ToolDefinition]:
        if not allowed_tool_names:
            return list(tools)
        allowed = set(allowed_tool_names)
        return [tool for tool in tools if tool.name in allowed]

    def log_tool_contract_diagnostics(self, **_kwargs: Any) -> None:
        return None

    async def emit_chunk(self, text: str) -> None:
        _ = text


def _prepared_time_turn() -> SimpleNamespace:
    tools = [ToolDefinition(name="get_current_time", description="Current time")]
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="time_query",
            family="time_ops",
            order=1,
            user_visible_label="time",
            source_text="现在是几点钟 ？",
            shortcircuit=True,
            allowed_tool_names=["get_current_time"],
            preferred_tool_names=["get_current_time"],
        )
    ]
    return SimpleNamespace(
        messages=[ChatMessage(role="user", content="现在是几点钟 ？")],
        tools=tools,
        all_tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="time_ops",
            mode="required",
            allowed_tool_names=["get_current_time"],
            retry_on_contract_breach=False,
            reason="time_query",
        ),
        execution_budget=BudgetGuard.build_default("fast", intent_count=1),
        execution_path="fast",
        intent_plan=intents,
        diagnostics={},
        provider_events=[],
        recovery_history=[],
        continuation_context=None,
    )


@pytest.mark.asyncio
async def test_conversation_2345_time_tool_short_circuits_without_provider_call() -> (
    None
):
    prep = _prepared_time_turn()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _NoProviderTimeIO(time_output="2026-05-05 21:53:44")

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=2345),
        agent=SimpleNamespace(id=59),
    )

    assert result.output == "现在是 2026-05-05 21:53:44。"
    assert result.total_tokens == 0
    assert result.completion_tokens_used == 0
    assert result.final_output_source == "recovery_evidence"
    assert io.call_history == []
    assert len(io.tool_call_history) == 1
    assert state.intent_plan[0].status == "completed"
    assert state.intent_plan[0].completed_by_tool_names == ["get_current_time"]
    assert (
        state.preparation_diagnostics["deterministic_shortcircuit_intent_kind"]
        == "time_query"
    )
    assert all(
        event.data.get("round_kind") != "normal_follow_up_round"
        for event in state.turn_events
        if event.kind == "turn.round_started"
    )
