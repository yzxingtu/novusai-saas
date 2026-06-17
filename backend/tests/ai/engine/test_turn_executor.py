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
        consent_payloads: list[dict[str, object] | None] | None = None,
    ) -> None:
        self.model_rounds = list(model_rounds)
        self.tool_batch = tool_batch or ToolBatchResult(response=None, tool_results=[])
        self.tool_batches = list(tool_batches or [])
        self.contract_retry = contract_retry
        self.post_tool_contract_breach = post_tool_contract_breach
        self.consent_payloads = list(consent_payloads or [])
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
        call_index = len(self.tool_call_history)
        self.tool_call_history.append(dict(kwargs))
        # Mirror production: handle_tool_calls appends one assistant tool_call
        # message per round so delta-based tool-round counting works correctly.
        # 贴合真实运行：每轮 append 一条 assistant tool_call 消息，使基于 delta
        # 的工具轮次计数生效（否则测试无法发现轮次双计/漏计问题）。
        messages = kwargs.get("messages")
        response = kwargs.get("response")
        tool_calls = (
            getattr(response, "tool_calls", None) if response is not None else None
        )
        if isinstance(messages, list) and tool_calls:
            messages.append(
                ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=list(tool_calls),
                )
            )
        # Simulate a consent gate for this batch by appending a pending_consent
        # message, mirroring the real tool processor's consent_ask behavior.
        # 模拟该批次命中 consent 门控：append 一条带 pending_consent 的消息，
        # 贴合真实工具处理器的 consent_ask 行为，用于验证 ReAct 暂停/恢复。
        consent_payload = (
            self.consent_payloads[call_index]
            if call_index < len(self.consent_payloads)
            else None
        )
        if isinstance(messages, list) and consent_payload:
            messages.append(
                ChatMessage(
                    role="tool",
                    content="",
                    tool_call_id="consent_tc",
                    metadata={"pending_consent": dict(consent_payload)},
                )
            )
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
            return []
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


def test_scope_tools_to_active_intent_fails_closed_when_allowlist_misses() -> None:
    """Test type: behavioral; stale allowlists must not reopen the full tool set."""
    tools = [
        ToolDefinition(name="clock_now", description="Current time"),
        ToolDefinition(name="weather_lookup", description="Plugin weather"),
    ]
    intent = _build_intent(
        intent_id="intent-1",
        kind="weather_query",
        family="weather",
        allowed_tool_names=["removed_weather_tool"],
    )
    state = ExecutionStateMachine(
        intent_plan=[intent],
        budget=BudgetGuard.build_default("normal", intent_count=1),
        execution_path="normal",
    )
    policy = ToolUsePolicy(
        family="weather",
        mode="required",
        allowed_tool_names=["removed_weather_tool"],
    )
    io = _FakeIOAdapter(model_rounds=[])

    scoped_tools, scoped_policy, active = TurnExecutor._scope_tools_to_active_intent(
        state=state,
        tools=tools,
        policy=policy,
        io=io,
    )

    assert active is intent
    assert scoped_tools == []
    assert scoped_policy is policy


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
    """验证 ReAct 循环在工具执行后继续调用 LLM 生成最终回复。"""
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

    # ReAct 循环：第 1 次 LLM 调用返回 tool_calls，第 2 次返回纯文本
    assert result.output == "客户状态是 active。"
    assert len(io.call_history) == 2
    # ReAct 循环中第 2 次调用是普通轮次，不需要 normal_follow_up_round 标记
    assert any(
        event.kind == "turn.round_started"
        and event.data.get("round_kind") == "react_round"
        for event in state.turn_events
    )


@pytest.mark.asyncio
async def test_turn_executor_requests_weather_city_before_tool_retry_when_city_missing() -> (
    None
):
    """验证 ReAct 循环中缺失参数澄清仍然工作。"""
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

    # ReAct 循环中缺失参数澄清仍然工作
    assert result.output == "你想查询哪个城市的天气？"
    assert len(io.call_history) == 1
    assert io.call_history[0]["tools"] is None
    # ReAct 循环中不再使用 intent_retry 标记，而是通过短路处理
    assert state.intent_plan[0].status == "completed"


def _tool_call(name: str, *, call_id: str, arguments: str = "{}") -> dict[str, object]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _crm_prep():
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
    return _build_prep(
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


@pytest.mark.asyncio
async def test_react_round_counts_single_tool_round_no_double_count() -> None:
    """P0-1: 每个 ReAct 工具轮次只计 1 次，不再双计预算。"""
    prep = _crm_prep()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("", tool_calls=[_tool_call("crm_lookup", call_id="c1")]),
            _assistant_response("客户状态是 active。"),
        ],
        tool_batch=ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="c1",
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
        request=SimpleNamespace(input_variables={}, conversation_id=30),
        agent=SimpleNamespace(id=1),
    )

    assert result.output == "客户状态是 active。"
    # 一轮工具调用 + 一轮纯文本，工具轮次恰好计 1 次（双计时会是 2）。
    assert state.budget is not None
    assert state.budget.tool_rounds_used == 1


@pytest.mark.asyncio
async def test_react_no_progress_break_on_repeated_tool_call() -> None:
    """P1-3: 连续两轮完全相同的工具调用应中断循环并走 partial。"""
    prep = _crm_prep()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("", tool_calls=[_tool_call("crm_lookup", call_id="a")]),
            _assistant_response("", tool_calls=[_tool_call("crm_lookup", call_id="b")]),
        ],
        tool_batch=ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="a",
                    name="crm_lookup",
                    success=True,
                    output="active",
                )
            ],
            total_tokens=4,
            completion_tokens_used=4,
        ),
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=31),
        agent=SimpleNamespace(id=1),
    )

    assert result.partial is True
    assert state.preparation_diagnostics.get("react_no_progress_break") is True
    # 第 2 轮检测到重复签名后在执行前中断：恰好 2 次 LLM 调用、1 次工具执行。
    assert len(io.call_history) == 2
    assert len(io.tool_call_history) == 1


@pytest.mark.asyncio
async def test_react_empty_action_nudge_retries_once() -> None:
    """P0-2: required 策略下模型口头完成（无工具调用）应被纠偏并重试一次。"""
    prep = _crm_prep()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response("好的，我已经帮你查好了。"),
            _assistant_response("", tool_calls=[_tool_call("crm_lookup", call_id="x")]),
            _assistant_response("客户状态是 active。"),
        ],
        tool_batch=ToolBatchResult(
            response=None,
            tool_results=[
                ToolResult(
                    tool_call_id="x",
                    name="crm_lookup",
                    success=True,
                    output="active",
                )
            ],
            total_tokens=5,
            completion_tokens_used=5,
        ),
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=32),
        agent=SimpleNamespace(id=1),
    )

    assert state.preparation_diagnostics.get("react_empty_action_nudged") is True
    assert result.output == "客户状态是 active。"
    # 空动作纠偏触发一次重试：text → (nudge) → tool → text，共 3 次 LLM 调用。
    assert len(io.call_history) == 3


def _confirmation_replay_prep():
    tools = [
        ToolDefinition(name="create_announcement", description="Create announcement"),
        ToolDefinition(name="publish_announcement", description="Publish announcement"),
    ]
    intents = [
        IntentPlan(
            intent_id="intent-replay",
            kind="confirmation_replay",
            family="internal_ops",
            order=1,
            user_visible_label="确认重放",
            source_text="创建公告后直接发布",
            shortcircuit=True,
            allowed_tool_names=["create_announcement"],
            preferred_tool_names=["create_announcement"],
            metadata={
                "confirmation_replay": {
                    "name": "create_announcement",
                    "tool_call_id": "tc_create",
                    "arguments": "{}",
                }
            },
        )
    ]
    return _build_prep(
        tools=tools,
        intents=intents,
        tool_use_policy=ToolUsePolicy(
            family="internal_ops",
            mode="required",
            allowed_tool_names=["create_announcement"],
            retry_on_contract_breach=False,
            reason="confirmation_replay",
        ),
    )


@pytest.mark.asyncio
async def test_confirmation_replay_injects_continuation_guidance_and_continues() -> None:
    """P0-2: confirmation_replay 续跑前注入引导，并由 ReAct 循环继续后续步骤。"""
    prep = _confirmation_replay_prep()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            # 续跑：模型继续发起 publish，再以纯文本总结
            _assistant_response(
                "", tool_calls=[_tool_call("publish_announcement", call_id="tc_pub")]
            ),
            _assistant_response("公告已创建并发布。"),
        ],
        tool_batches=[
            # call 0: confirmation_replay 执行 create
            ToolBatchResult(
                response=None,
                tool_results=[
                    ToolResult(
                        tool_call_id="tc_create",
                        name="create_announcement",
                        success=True,
                        output='{"id": 11, "status": "draft"}',
                    )
                ],
                total_tokens=3,
                completion_tokens_used=3,
            ),
            # call 1: 续跑执行 publish
            ToolBatchResult(
                response=None,
                tool_results=[
                    ToolResult(
                        tool_call_id="tc_pub",
                        name="publish_announcement",
                        success=True,
                        output='{"id": 11, "status": "published"}',
                    )
                ],
                total_tokens=3,
                completion_tokens_used=3,
            ),
        ],
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=33),
        agent=SimpleNamespace(id=1),
    )

    assert (
        state.preparation_diagnostics.get("react_replay_continuation_guidance") is True
    )
    # 续跑引导消息已注入到对话中
    assert any(
        message.role == "system"
        and (message.metadata or {}).get("react_replay_continuation_guidance")
        for message in prep.messages
    )
    # create（短路）+ publish（续跑）两次工具批次都被执行
    assert len(io.tool_call_history) == 2
    assert result.output == "公告已创建并发布。"


@pytest.mark.asyncio
async def test_confirmation_replay_continuation_pauses_for_second_consent() -> None:
    """链式敏感操作：replay 写入后续跑命中第二次 consent，应再次暂停。"""
    prep = _confirmation_replay_prep()
    state = ExecutionStateMachine.from_prepared_execution(prep)
    io = _FakeIOAdapter(
        model_rounds=[
            _assistant_response(
                "", tool_calls=[_tool_call("publish_announcement", call_id="tc_pub")]
            ),
        ],
        tool_batches=[
            ToolBatchResult(
                response=None,
                tool_results=[
                    ToolResult(
                        tool_call_id="tc_create",
                        name="create_announcement",
                        success=True,
                        output='{"id": 12, "status": "draft"}',
                    )
                ],
                total_tokens=3,
                completion_tokens_used=3,
            ),
            ToolBatchResult(
                response=None,
                tool_results=[],
                total_tokens=2,
                completion_tokens_used=2,
            ),
        ],
        # call 0 (create replay) 无 consent；call 1 (publish) 命中 consent
        consent_payloads=[
            None,
            {
                "tool_name": "publish_announcement",
                "action": "tool_consent",
                "resolved": False,
            },
        ],
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=34),
        agent=SimpleNamespace(id=1),
    )

    assert result.paused_for_consent is True
    assert result.partial is False
