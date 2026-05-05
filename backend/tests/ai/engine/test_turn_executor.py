"""
Test type: structural / behavioral
Scope: TurnExecutor orchestration contract with fake transport adapters and
deterministic tool-result replay.
Real dependencies: ExecutionStateMachine and RecoveryManager run real control-flow logic.
Mocked dependencies: LLM/tool transport via _FakeIOAdapter; no provider text is
hand-authored as the asserted outcome.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.turn_executor import (
    ModelRoundResult,
    ToolBatchResult,
    TurnExecutor,
)
from app.ai.engine.types import IntentPlan, ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _FakeIOAdapter:
    def __init__(
        self,
        *,
        model_rounds: list[ModelRoundResult],
        tool_batch: ToolBatchResult | None = None,
        tool_batches: list[ToolBatchResult] | None = None,
        contract_retry: tuple[bool, ToolUsePolicy | None, str] = (False, None, ""),
        post_tool_contract_breach: tuple[
            str | None,
            ToolUsePolicy | None,
            dict[str, object],
        ] = (None, None, {}),
    ) -> None:
        self.model_rounds = list(model_rounds)
        self.tool_batch = tool_batch or ToolBatchResult(response=None, tool_results=[])
        self.tool_batches = list(tool_batches or [])
        self.contract_retry = contract_retry
        self.post_tool_contract_breach = post_tool_contract_breach
        self.call_history: list[dict[str, object]] = []
        self.retry_logs: list[str] = []
        self.finalize_calls: list[dict[str, object]] = []
        self.finalize_completed_calls: list[dict[str, object]] = []
        self.tool_call_history: list[dict[str, object]] = []

    async def call_llm(self, **kwargs):
        self.call_history.append(dict(kwargs))
        if not self.model_rounds:
            raise AssertionError("No model rounds left")
        return self.model_rounds.pop(0)

    async def handle_tool_calls(self, **kwargs):
        self.tool_call_history.append(dict(kwargs))
        if self.tool_batches:
            return self.tool_batches.pop(0)
        return self.tool_batch

    async def finalize_partial_output(self, **kwargs):
        self.finalize_calls.append(dict(kwargs))
        return ("finalized partial output", 23, 23)

    async def finalize_completed_output(self, **kwargs):
        self.finalize_completed_calls.append(dict(kwargs))
        response = kwargs["response"]
        visible_output = (
            str(response.message.content or "").strip() if response is not None else ""
        )
        if visible_output:
            return (
                visible_output,
                int(kwargs.get("total_tokens") or 0),
                int(kwargs.get("completion_tokens_used") or 0),
            )
        state = kwargs["state"]
        tool_results = kwargs["tool_results"]
        reason = str(kwargs.get("reason") or "completed")
        return (
            RecoveryManager.build_completed_output(
                state.intent_plan,
                tool_results=tool_results,
                reason=reason,
                contract_breach_type=(
                    str(
                        state.preparation_diagnostics.get("contract_breach_type") or ""
                    ).strip()
                    or None
                ),
            ),
            int(kwargs.get("total_tokens") or 0),
            int(kwargs.get("completion_tokens_used") or 0),
        )

    def should_retry_tool_contract_breach(self, **_kwargs):
        return self.contract_retry

    def analyze_post_tool_contract_breach(self, **_kwargs):
        return self.post_tool_contract_breach

    def restrict_tools_to_names(self, tools, allowed_tool_names):
        if not allowed_tool_names:
            return list(tools)
        allowed = set(allowed_tool_names)
        return [tool for tool in tools if tool.name in allowed]

    def log_tool_contract_diagnostics(self, **kwargs):
        self.retry_logs.append(str(kwargs.get("retry_result") or ""))

    async def emit_chunk(self, text: str) -> None:
        _ = text


def _build_prep(
    *,
    tools: list[ToolDefinition],
    intents: list[IntentPlan],
    tool_use_policy: ToolUsePolicy,
):
    return SimpleNamespace(
        messages=[ChatMessage(role="user", content="test")],
        tools=list(tools),
        all_tools=list(tools),
        tool_use_policy=tool_use_policy,
        execution_budget=BudgetGuard.build_default(
            "normal",
            intent_count=len(intents),
        ),
        execution_path="normal",
        intent_plan=list(intents),
        diagnostics={},
        provider_events=[],
        recovery_history=[],
        continuation_context=None,
    )


def _build_intent(
    *,
    intent_id: str,
    kind: str,
    family: str,
    allowed_tool_names: list[str],
) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind=kind,
        family=family,
        order=1,
        user_visible_label=kind,
        source_text=kind,
        allowed_tool_names=list(allowed_tool_names),
        preferred_tool_names=list(allowed_tool_names),
    )


def _assistant_response(
    content: str,
    *,
    tool_calls: list[dict[str, object]] | None = None,
    total_tokens: int = 7,
) -> ModelRoundResult:
    response = ChatResponse(
        message=ChatMessage(role="assistant", content=content, tool_calls=tool_calls),
        tool_calls=tool_calls,
        total_tokens=total_tokens,
        output_tokens=total_tokens,
    )
    return ModelRoundResult(
        response=response,
        total_tokens=total_tokens,
        completion_tokens_used=total_tokens,
    )


@pytest.mark.asyncio
async def test_turn_executor_returns_cached_shortcircuit_without_provider_call() -> (
    None
):
    intent = IntentPlan(
        intent_id="intent-1",
        kind="unsupported_image_generation",
        family="none",
        order=1,
        user_visible_label="image_generation",
        source_text="帮我画一张猫咪的图片",
        requires_tools=False,
        shortcircuit=True,
        cached_result="当前对话暂不支持直接生成图片。",
    )
    prep = _build_prep(
        tools=[],
        intents=[intent],
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="cached_shortcircuit",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(model_rounds=[])

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=1,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "当前对话暂不支持直接生成图片。"
    assert result.partial is False
    assert result.final_output_source == "assistant"
    assert io.call_history == []
    assert state.intent_plan[0].status == "completed"
    assert state.intent_plan[0].metadata["cached_shortcircuit_completed"] is True
    assert (
        state.preparation_diagnostics["cached_shortcircuit_intent_kind"]
        == "unsupported_image_generation"
    )


@pytest.mark.asyncio
async def test_turn_executor_returns_precompleted_cached_shortcircuit_without_provider_call() -> (
    None
):
    intent = IntentPlan(
        intent_id="intent-1",
        kind="unsupported_image_generation",
        family="none",
        order=1,
        user_visible_label="image_generation",
        source_text="帮我画一张猫咪的图片",
        requires_tools=False,
        shortcircuit=True,
        cached_result="当前对话暂不支持直接生成图片。",
        status="completed",
    )
    prep = _build_prep(
        tools=[],
        intents=[intent],
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="cached_shortcircuit",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(model_rounds=[])

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=1,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "当前对话暂不支持直接生成图片。"
    assert result.partial is False
    assert result.final_output_source == "assistant"
    assert io.call_history == []
    assert state.intent_plan[0].metadata["cached_shortcircuit_completed"] is True


@pytest.mark.asyncio
async def test_turn_executor_runs_time_shortcircuit_without_provider_call_for_conversation_2345() -> (
    None
):
    tools = [ToolDefinition(name="get_current_time", description="Time")]
    intents = [
        IntentPlan(
            intent_id="intent-time",
            kind="time_query",
            family="time_ops",
            order=1,
            user_visible_label="time",
            source_text="现在几点",
            shortcircuit=True,
            allowed_tool_names=["get_current_time"],
            preferred_tool_names=["get_current_time"],
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="time_ops",
            mode="required",
            allowed_tool_names=["get_current_time"],
            retry_on_contract_breach=False,
            reason="time_query",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[],
        tool_batch=ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="call_time",
                    name="get_current_time",
                    success=True,
                    output="2026-04-07 09:30:00 Tuesday",
                )
            ],
            total_tokens=0,
            completion_tokens_used=0,
        ),
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=21,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "现在是 2026-04-07 09:30:00 Tuesday。"
    assert result.total_tokens == 0
    assert result.completion_tokens_used == 0
    assert result.final_output_source == "recovery_evidence"
    assert io.call_history == []
    assert len(io.tool_call_history) == 1
    assert (
        io.tool_call_history[0]["response"].metadata[
            "deterministic_shortcircuit_tool_call"
        ]
        is True
    )
    assert (
        state.preparation_diagnostics["deterministic_shortcircuit_intent_kind"]
        == "time_query"
    )
    assert all(
        event.data.get("round_kind") != "normal_follow_up_round"
        for event in state.turn_events
        if event.kind == "turn.round_started"
    )


@pytest.mark.asyncio
async def test_turn_executor_keeps_post_tool_follow_up_for_non_deterministic_tools() -> (
    None
):
    tools = [ToolDefinition(name="crm_lookup", description="Lookup CRM record")]
    intents = [
        IntentPlan(
            intent_id="intent-crm",
            kind="crm_lookup",
            family="crm",
            order=1,
            user_visible_label="CRM lookup",
            source_text="查一下客户状态",
            allowed_tool_names=["crm_lookup"],
            preferred_tool_names=["crm_lookup"],
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="crm",
            mode="required",
            allowed_tool_names=["crm_lookup"],
            retry_on_contract_breach=False,
            reason="crm_lookup",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response(
                "",
                tool_calls=[
                    {
                        "id": "call_crm",
                        "type": "function",
                        "function": {"name": "crm_lookup", "arguments": "{}"},
                    }
                ],
            ),
            _assistant_response("客户状态是 active。"),
        ],
        tool_batch=ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="call_crm",
                    name="crm_lookup",
                    success=True,
                    output="active",
                )
            ],
            total_tokens=7,
            completion_tokens_used=7,
        ),
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=22,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "客户状态是 active。"
    assert len(io.call_history) == 2
    assert io.call_history[1]["breach_retry_result"] == "normal_follow_up_round"
    assert io.call_history[1]["tools"] is None
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "normal_follow_up_round"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_requests_weather_city_before_tool_retry_when_city_missing() -> (
    None
):
    tools = [ToolDefinition(name="get_current_weather", description="Weather")]
    intents = [
        IntentPlan(
            intent_id="intent-weather",
            kind="weather_query",
            family="weather",
            order=1,
            user_visible_label="weather",
            source_text="今天天气怎么样",
            allow_text_response=True,
            shortcircuit=True,
            allowed_tool_names=["get_current_weather"],
            preferred_tool_names=["get_current_weather"],
            metadata={"missing_args": ["city"]},
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="weather_query",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[_assistant_response("你想查询哪个城市的天气？")],
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=22,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "你想查询哪个城市的天气？"
    assert len(io.call_history) == 1
    assert io.call_history[0]["tools"] is None
    assert io.call_history[0]["breach_retry_result"] == "intent_retry"
    assert state.intent_plan[0].status == "completed"
