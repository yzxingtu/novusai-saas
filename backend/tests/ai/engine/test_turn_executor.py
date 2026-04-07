from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.recovery_manager import RecoveryDecision
from app.ai.engine.turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from app.ai.engine.types import IntentPlan, ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _FakeIOAdapter:
    def __init__(
        self,
        *,
        model_rounds: list[ModelRoundResult],
        tool_batch: ToolBatchResult | None = None,
        contract_retry: tuple[bool, ToolUsePolicy | None, str] = (False, None, ""),
        post_tool_contract_breach: tuple[
            str | None,
            ToolUsePolicy | None,
            dict[str, object],
        ] = (None, None, {}),
    ) -> None:
        self.model_rounds = list(model_rounds)
        self.tool_batch = tool_batch or ToolBatchResult(response=None, tool_results=[])
        self.contract_retry = contract_retry
        self.post_tool_contract_breach = post_tool_contract_breach
        self.call_history: list[dict[str, object]] = []
        self.retry_logs: list[str] = []
        self.finalize_calls: list[dict[str, object]] = []

    async def call_llm(self, **kwargs):
        self.call_history.append(dict(kwargs))
        if not self.model_rounds:
            raise AssertionError("No model rounds left")
        return self.model_rounds.pop(0)

    async def handle_tool_calls(self, **kwargs):
        return self.tool_batch

    async def finalize_partial_output(self, **kwargs):
        self.finalize_calls.append(dict(kwargs))
        return ("finalized partial output", 23, 23)

    def should_retry_tool_contract_breach(self, **kwargs):
        return self.contract_retry

    def should_retry_web_research_contract_breach(self, **kwargs):
        return False, None, ""

    def analyze_post_tool_contract_breach(self, **kwargs):
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
async def test_turn_executor_scopes_initial_model_round_to_active_intent_tools() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search"),
        ToolDefinition(name="fetch_url", description="Fetch"),
        ToolDefinition(name="get_page_context", description="Page"),
    ]
    intents = [
        _build_intent(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            allowed_tool_names=["web_search", "fetch_url"],
        ),
        _build_intent(
            intent_id="intent-page",
            kind="page_summary",
            family="page_ops",
            allowed_tool_names=["get_page_context"],
        ),
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=[tool.name for tool in tools],
            retry_on_contract_breach=True,
            reason="mixed_turn",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(model_rounds=[_assistant_response("scoped")])

    with patch("app.ai.engine.turn_executor.RecoveryManager.decide", return_value=None):
        await TurnExecutor.run(
            state=state,
            io=io,
            prep=prep,
            request=SimpleNamespace(
                input_variables={},
                conversation_id=1,
            ),
            agent=SimpleNamespace(id=1),
        )

    first_call_tools = [tool.name for tool in io.call_history[0]["tools"]]
    assert first_call_tools == ["web_search", "fetch_url"]
    first_policy = io.call_history[0]["tool_use_policy"]
    assert first_policy.allowed_tool_names == ["web_search", "fetch_url"]


@pytest.mark.asyncio
async def test_turn_executor_marks_contract_retry_round_and_failed_retry() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search"),
        ToolDefinition(name="fetch_url", description="Fetch"),
    ]
    prep = _build_prep(
        tools=tools,
        intents=[],
        tool_use_policy=ToolUsePolicy(
            family="none",
            mode="auto",
            allowed_tool_names=[tool.name for tool in tools],
            retry_on_contract_breach=True,
            reason="default_auto",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("first round says no tools"),
            _assistant_response("retry still says no tools"),
        ],
        contract_retry=(
            True,
            ToolUsePolicy(
                family="web_research",
                mode="required",
                allowed_tool_names=["web_search", "fetch_url"],
                retry_on_contract_breach=False,
                reason="required_retry:web_research",
            ),
            "",
        ),
    )

    await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(
            input_variables={},
            conversation_id=9,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert len(io.call_history) == 2
    assert io.call_history[1]["breach_retry_result"] == "contract_retry"
    assert io.retry_logs == ["retrying", "failed"]
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "contract_retry"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_retries_structured_intent_when_assistant_claims_fake_tool_call() -> None:
    tools = [ToolDefinition(name="get_page_context", description="Read page")]
    intents = [
        _build_intent(
            intent_id="intent-page",
            kind="page_summary",
            family="page_ops",
            allowed_tool_names=["get_page_context"],
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="page_ops",
            mode="required",
            allowed_tool_names=["get_page_context"],
            retry_on_contract_breach=True,
            reason="intent:page_summary",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("Calling get_page_context to continue reviewing."),
            _assistant_response(
                "",
                tool_calls=[
                    {
                        "id": "call_page_ctx",
                        "type": "function",
                        "function": {
                            "name": "get_page_context",
                            "arguments": "{}",
                        },
                    }
                ],
            ),
        ],
        tool_batch=ToolBatchResult(
            response=ChatResponse(
                message=ChatMessage(role="assistant", content="我继续查看了页面内容。"),
                total_tokens=11,
                output_tokens=11,
            ),
            tool_results=[
                ToolResult(
                    tool_call_id="call_page_ctx",
                    name="get_page_context",
                    success=True,
                    output="page context payload",
                )
            ],
            total_tokens=11,
            completion_tokens_used=11,
        ),
        post_tool_contract_breach=(
            "assistant_claimed_tool_call_without_tool_event",
            ToolUsePolicy(
                family="page_ops",
                mode="required",
                allowed_tool_names=["get_page_context"],
                retry_on_contract_breach=False,
                reason="assistant_claimed_tool_call_without_tool_event",
            ),
            {
                "assistant_claimed_tool_call_without_tool_event": True,
                "unfinished_intents": ["page_summary"],
            },
        ),
    )

    with patch("app.ai.engine.turn_executor.RecoveryManager.decide", return_value=None):
        result = await TurnExecutor.run(
            state=state,
            io=io,
            prep=prep,
            request=SimpleNamespace(
                input_variables={
                    "page_context": {"page_key": "admin.ai.conversations"},
                },
                conversation_id=15,
            ),
            agent=SimpleNamespace(id=1),
        )

    assert result.output == "我继续查看了页面内容。"
    assert len(io.call_history) == 2
    assert io.call_history[1]["breach_retry_result"] == "contract_retry"
    assert [tool.name for tool in io.call_history[1]["tools"]] == ["get_page_context"]
    assert state.preparation_diagnostics["contract_breach_type"] == (
        "assistant_claimed_tool_call_without_tool_event"
    )
    assert state.preparation_diagnostics[
        "assistant_claimed_tool_call_without_tool_event"
    ] is True
    assert state.preparation_diagnostics["unfinished_intents"] == ["page_summary"]
    assert io.retry_logs == ["retrying"]


@pytest.mark.asyncio
async def test_turn_executor_marks_intent_retry_round() -> None:
    tools = [
        ToolDefinition(name="web_search", description="Search"),
        ToolDefinition(name="fetch_url", description="Fetch"),
    ]
    intents = [
        _build_intent(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            allowed_tool_names=["fetch_url"],
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=[tool.name for tool in tools],
            retry_on_contract_breach=True,
            reason="explicit_web_request",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("first round says no tools"),
            _assistant_response("retry uses narrowed tools"),
        ]
    )

    with patch(
        "app.ai.engine.turn_executor.RecoveryManager.decide",
        side_effect=[
            RecoveryDecision(
                action="retry_intent",
                target_intent_id="intent-web",
                retry_family="web_research",
                allowed_tool_names=["fetch_url"],
                reason="unfinished_intent_retry",
            ),
            None,
        ],
    ):
        await TurnExecutor.run(
            state=state,
            io=io,
            prep=prep,
            request=SimpleNamespace(
                input_variables={},
                conversation_id=11,
            ),
            agent=SimpleNamespace(id=1),
        )

    assert len(io.call_history) == 2
    assert io.call_history[1]["breach_retry_result"] == "intent_retry"
    assert [tool.name for tool in io.call_history[1]["tools"]] == ["fetch_url"]
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "intent_retry"
        and event.data.get("intent_id") == "intent-web"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_finalizes_partial_without_budget_finalization_round() -> None:
    tools = [ToolDefinition(name="web_search", description="Search")]
    intents = [
        _build_intent(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            allowed_tool_names=["web_search"],
        )
    ]
    prep = _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search"],
            retry_on_contract_breach=False,
            reason="explicit_web_request",
        ),
    )
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(model_rounds=[_assistant_response("partial reply")])

    with patch(
        "app.ai.engine.turn_executor.RecoveryManager.decide",
        return_value=RecoveryDecision(
            action="return_partial",
            target_intent_id="intent-web",
            reason="elapsed_budget_exceeded",
        ),
    ):
        result = await TurnExecutor.run(
            state=state,
            io=io,
            prep=prep,
            request=SimpleNamespace(
                input_variables={},
                conversation_id=13,
            ),
            agent=SimpleNamespace(id=1),
        )

    assert result.partial is True
    assert io.finalize_calls
    assert not any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "budget_finalization"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_runs_post_tool_follow_up_when_batch_returns_no_final_text() -> None:
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
        model_rounds=[
            _assistant_response(
                "",
                tool_calls=[
                    {
                        "id": "call_time",
                        "type": "function",
                        "function": {"name": "get_current_time", "arguments": "{}"},
                    }
                ],
            ),
            _assistant_response("现在是 09:30。"),
        ],
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
            conversation_id=21,
        ),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "现在是 09:30。"
    assert len(io.call_history) == 2
    assert io.call_history[1]["breach_retry_result"] == "normal_follow_up_round"
    assert io.call_history[1]["tools"] is None
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "normal_follow_up_round"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_requests_weather_city_before_tool_retry_when_city_missing() -> None:
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
