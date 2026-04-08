from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine import tool_processor as tool_processor_mod
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.stream_handler import StreamExecutionHandler
from app.ai.engine.types import (
    ExecutionBudget,
    ExecutionRequest,
    IntentPlan,
    PreparedExecution,
    ToolUsePolicy,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


def _make_agent() -> SimpleNamespace:
    provider = SimpleNamespace(
        code="mock-provider",
        type="mock",
        base_url="",
        config={},
        decrypt_key=lambda: "fake-key",
    )
    model = SimpleNamespace(
        provider=provider,
        code="mock-model",
        supports_vision=False,
        supports_audio=False,
        supports_video=False,
        supports_streaming=False,
        config={},
    )
    return SimpleNamespace(
        id=1,
        name="Weather Agent",
        system_prompt="",
        temperature=0.0,
        max_tokens=256,
        top_p=1.0,
        model=model,
    )


def _weather_tool_call(*, city: str, call_id: str) -> dict[str, object]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "arguments": f'{{"city":"{city}"}}',
        },
    }


def _make_budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_prompt_tokens=4000,
        max_completion_tokens=2000,
        max_tool_rounds=3,
        max_elapsed_ms=40000,
        max_retry_per_intent=1,
        max_candidate_tools=3,
        max_tool_result_bytes=16000,
        finalization_grace_ms=15000,
    )


def _install_fake_weather_processor(
    monkeypatch: pytest.MonkeyPatch,
    *,
    budget: ExecutionBudget,
    exceed_after_success_before_followup: bool = False,
    processed_cities: list[str] | None = None,
) -> None:
    class FakeProcessor:
        def __init__(self, *_args, tools=None, **_kwargs):
            self.tools = list(tools or [])

        @staticmethod
        def approved_pending_consent_tool_names(_updates):
            return []

        def parse_arguments(self, raw: str):
            city = raw.split('"city":"', 1)[1].split('"', 1)[0]
            return {"city": city}, None

        def get_skill_info(self, _func_name: str):
            return None

        def annotate_tool_call(self, *_args, **_kwargs):
            return None

        def check_consent(self, *_args, **_kwargs):
            return None

        def build_pending_consent_payload(self, *_args, **_kwargs):
            return {}

        def build_consent_ask_message(self, *_args, **_kwargs):
            return ChatMessage(role="assistant", content="Need consent")

        async def process_single(self, tc, conversation_id: int):
            _ = conversation_id
            city = tc["function"]["arguments"].split('"city":"', 1)[1].split('"', 1)[0]
            if processed_cities is not None:
                processed_cities.append(city)
            success = city == "凤凰"
            if success and exceed_after_success_before_followup:
                budget.tool_result_bytes_used = budget.max_tool_result_bytes + 1
            tool_result = ToolResult(
                tool_call_id=tc["id"],
                name="get_current_weather",
                success=success,
                output=(
                    "Current weather for 凤凰:\n  Temperature: 7.5°C\n  Condition: Clear sky (晴)"
                    if success
                    else "未找到城市：凤凰县"
                ),
                error=None if success else "未找到城市：凤凰县",
                duration_ms=1,
            )
            return SimpleNamespace(
                tool_result=tool_result,
                tool_message=ChatMessage(
                    role="tool",
                    content=tool_result.output or tool_result.error or "",
                    tool_call_id=tc["id"],
                ),
                follow_up_message=None,
                duration_ms=1,
            )

        def check_confirmation_output(self, _tool_result: ToolResult):
            return None

        def build_pending_confirmation_payload(self, *_args, **_kwargs):
            return {}

        def build_assistant_tool_call_message(
            self,
            *,
            content: str,
            tool_calls: list[dict[str, object]],
            reasoning_content: str | None = None,
        ):
            _ = reasoning_content
            return ChatMessage(role="assistant", content=content, tool_calls=tool_calls)

    monkeypatch.setattr(tool_processor_mod, "ToolCallProcessor", FakeProcessor)


@pytest.mark.asyncio
async def test_budget_exit_with_tool_results_uses_cached_partial_output(
    monkeypatch,
) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="帮我查一下西安现在的天气")],
        tools=[ToolDefinition(name="get_current_weather", description="Current weather")],
        all_tools=[
            ToolDefinition(name="get_current_weather", description="Current weather")
        ],
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="intent:weather_query",
        ),
        intent_plan=[
            IntentPlan(
                intent_id="intent-weather",
                kind="weather_query",
                family="weather",
                order=1,
                user_visible_label="天气",
                source_text="帮我查一下西安现在的天气",
                allowed_tool_names=["get_current_weather"],
                completion_signals=["get_current_weather"],
            )
        ],
        execution_path="fast",
        execution_budget=_make_budget(),
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        side_effect=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="西安", call_id="tc_weather")],
                total_tokens=8,
                output_tokens=8,
            ),
            ChatResponse(
                message=ChatMessage(role="assistant", content="西安现在多云，气温约 18C。"),
                total_tokens=6,
                output_tokens=6,
            ),
        ]
    )

    async def _fake_handle_tool_calls(*, messages, response, **kwargs):
        _ = kwargs
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{**response.tool_calls[0], "success": True}],
            )
        )
        messages.append(
            ChatMessage(
                role="tool",
                content='{"city":"西安","condition":"多云","temperature":"18C"}',
                tool_call_id="tc_weather",
            )
        )
        return (
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=8,
                output_tokens=0,
            ),
            [
                ToolResult(
                    tool_call_id="tc_weather",
                    name="get_current_weather",
                    success=True,
                    output='{"city":"西安","condition":"多云","temperature":"18C"}',
                )
            ],
            8,
            8,
        )

    engine._handle_tool_calls = AsyncMock(side_effect=_fake_handle_tool_calls)

    sync_calls = {"count": 0}

    def _force_budget_exit(self) -> None:
        sync_calls["count"] += 1
        if self.budget is None:
            return
        if sync_calls["count"] >= 2:
            self.budget.elapsed_ms_used = self.budget.max_elapsed_ms + 1
        else:
            self.budget.elapsed_ms_used = 0

    monkeypatch.setattr(ExecutionStateMachine, "sync_elapsed", _force_budget_exit)

    result = await engine.execute(
        _make_agent(),
        ExecutionRequest(
            agent_id=1,
            tenant_id=1,
            user_id=1,
            conversation_id=101,
            messages=[ChatMessage(role="user", content="帮我查一下西安现在的天气")],
        ),
    )

    # Elapsed budget is diagnostic-only and does not trigger partial exit.
    # The follow-up synthesis round runs and produces a completed result.
    assert result.partial is False
    assert result.success is True
    assert result.completion_reason == "completed"
    assert result.output == "西安现在多云，气温约 18C。"
    assert result.execution_budget is not None
    assert result.execution_budget["limits"]["finalization_grace_ms"] == 15000
    assert result.execution_budget["usage"]["finalization_grace_applied"] is False
    # 2 calls: tool selection + follow-up synthesis
    assert len(engine._call_llm.await_args_list) == 2


@pytest.mark.asyncio
async def test_handle_tool_calls_skips_finalization_only_call_after_retry_success_when_budget_is_exceeded(
    monkeypatch,
) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    budget = _make_budget()
    tools = [ToolDefinition(name="get_current_weather", description="Current weather")]
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=848,
        messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="intent:weather_query",
        ),
    )

    _install_fake_weather_processor(
        monkeypatch,
        budget=budget,
        exceed_after_success_before_followup=True,
    )

    async def _fake_call_llm(**kwargs):
        if kwargs["tools"] is not None:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰", call_id="tc_weather_retry")],
                total_tokens=4,
                output_tokens=2,
            )
        return ChatResponse(
            message=ChatMessage(role="assistant", content="凤凰今天晴，气温 7.5°C。"),
            total_tokens=6,
            output_tokens=6,
        )

    engine._call_llm = AsyncMock(side_effect=_fake_call_llm)

    final_response, tool_results, total_tokens, completion_tokens = (
        await engine._handle_tool_calls(
            agent=_make_agent(),
            messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰县", call_id="tc_weather_initial")],
                total_tokens=8,
                output_tokens=4,
            ),
            tools=tools,
            all_tools=tools,
            request=request,
            tool_use_policy=request.tool_use_policy,
            execution_budget=budget,
        )
    )

    assert final_response is not None
    assert (final_response.message.content or "").strip() == ""
    assert budget.finalization_grace_applied is False
    assert not any(
        call.kwargs.get("tools") is None for call in engine._call_llm.await_args_list
    )


@pytest.mark.asyncio
async def test_handle_tool_calls_keeps_completed_final_answer_even_if_budget_is_exceeded_before_next_round(
    monkeypatch,
) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    budget = _make_budget()
    tools = [ToolDefinition(name="get_current_weather", description="Current weather")]
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=849,
        messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="intent:weather_query",
        ),
    )

    _install_fake_weather_processor(
        monkeypatch,
        budget=budget,
        exceed_after_success_before_followup=False,
    )

    call_counter = {"count": 0}

    async def _fake_call_llm(**kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰", call_id="tc_weather_retry")],
                total_tokens=4,
                output_tokens=2,
            )
        budget.elapsed_ms_used = budget.max_elapsed_ms + 1000
        return ChatResponse(
            message=ChatMessage(role="assistant", content="凤凰今天晴，气温 7.5°C。"),
            total_tokens=6,
            output_tokens=6,
        )

    engine._call_llm = AsyncMock(side_effect=_fake_call_llm)

    final_response, tool_results, total_tokens, completion_tokens = (
        await engine._handle_tool_calls(
            agent=_make_agent(),
            messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰县", call_id="tc_weather_initial")],
                total_tokens=8,
                output_tokens=4,
            ),
            tools=tools,
            all_tools=tools,
            request=request,
            tool_use_policy=request.tool_use_policy,
            execution_budget=budget,
        )
    )

    assert final_response is not None
    assert final_response.message.content == "凤凰今天晴，气温 7.5°C。"
    assert [result.success for result in tool_results] == [False, True]
    assert total_tokens == 18
    assert completion_tokens == 12
    assert len(engine._call_llm.await_args_list) == 2


@pytest.mark.asyncio
async def test_handle_tool_calls_does_not_start_finalization_only_response_when_budget_is_exceeded(
    monkeypatch,
) -> None:
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    budget = _make_budget()
    tools = [ToolDefinition(name="get_current_weather", description="Current weather")]
    processed_cities: list[str] = []
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=850,
        messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="intent:weather_query",
        ),
    )

    _install_fake_weather_processor(
        monkeypatch,
        budget=budget,
        exceed_after_success_before_followup=True,
        processed_cities=processed_cities,
    )

    async def _fake_call_llm(**kwargs):
        if kwargs["tools"] is not None:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰", call_id="tc_weather_retry")],
                total_tokens=4,
                output_tokens=2,
            )
        return ChatResponse(
            message=ChatMessage(role="assistant", content="凤凰今天晴，气温 7.5°C。"),
            tool_calls=[_weather_tool_call(city="长沙", call_id="tc_unexpected_finalization")],
            total_tokens=6,
            output_tokens=6,
        )

    engine._call_llm = AsyncMock(side_effect=_fake_call_llm)

    final_response, tool_results, total_tokens, completion_tokens = (
        await engine._handle_tool_calls(
            agent=_make_agent(),
            messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
            response=ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[_weather_tool_call(city="凤凰县", call_id="tc_weather_initial")],
                total_tokens=8,
                output_tokens=4,
            ),
            tools=tools,
            all_tools=tools,
            request=request,
            tool_use_policy=request.tool_use_policy,
            execution_budget=budget,
        )
    )

    assert final_response is not None
    assert (final_response.message.content or "").strip() == ""
    assert processed_cities == ["凤凰县", "凤凰"]
    assert not any(
        call.kwargs.get("tools") is None for call in engine._call_llm.await_args_list
    )


@pytest.mark.asyncio
async def test_stream_handler_uses_partial_summary_without_finalization_round(
    monkeypatch,
) -> None:
    budget = _make_budget()
    tools = [ToolDefinition(name="get_current_weather", description="Current weather")]
    processed_cities: list[str] = []

    class FakeStreamProcessor:
        def __init__(self, *_args, tools=None, **_kwargs):
            self.tools = list(tools or [])

        @staticmethod
        def approved_pending_consent_tool_names(_updates):
            return []

        def is_confirmation_text(self, _text: str) -> bool:
            return False

        def find_pending_confirmation(self, _messages):
            return None

        def parse_arguments(self, raw: str):
            city = raw.split('"city":"', 1)[1].split('"', 1)[0]
            return {"city": city}, None

        def get_skill_info(self, _func_name: str):
            return None

        def annotate_tool_call(self, *_args, **_kwargs):
            return None

        def check_consent(self, *_args, **_kwargs):
            return None

        def build_pending_consent_payload(self, *_args, **_kwargs):
            return {}

        def build_consent_ask_message(self, *_args, **_kwargs):
            return ChatMessage(role="assistant", content="Need consent")

        def build_consent_ask_event(self, *_args, **_kwargs):
            return {"event": "consent_ask"}

        def build_consent_reject_message(self, tc_id: str):
            return ChatMessage(role="tool", content="Rejected", tool_call_id=tc_id)

        def build_consent_reject_event(self, *_args, **_kwargs):
            return {"event": "consent_reject"}

        def build_tool_start_event(
            self,
            func_name: str,
            arguments: dict[str, object],
            _skill_info,
            *,
            tool_call_id: str | None = None,
        ):
            return {
                "event": "tool_start",
                "tool_name": func_name,
                "tool_call_id": tool_call_id,
                "arguments": arguments,
            }

        async def execute_tool(
            self,
            tc_id: str,
            func_name: str,
            arguments: dict[str, object],
            *,
            conversation_id: int,
        ):
            _ = (tc_id, func_name, conversation_id)
            city = str(arguments["city"])
            processed_cities.append(city)
            success = city == "凤凰"
            if success:
                budget.elapsed_ms_used = budget.max_elapsed_ms + 1000
            result = ToolResult(
                tool_call_id=tc_id,
                name="get_current_weather",
                success=success,
                output=(
                    "Current weather for 凤凰:\n  Temperature: 7.5°C\n  Condition: Clear sky (晴)"
                    if success
                    else "未找到城市：凤凰县"
                ),
                error=None if success else "未找到城市：凤凰县",
                duration_ms=1,
            )
            return result, 1

        def build_tool_call_event(
            self,
            result: ToolResult,
            duration_ms: int,
            _skill_info,
            *,
            name_override: str | None = None,
        ):
            return {
                "event": "tool_call",
                "tool_name": name_override or result.name,
                "success": result.success,
                "duration_ms": duration_ms,
            }

        def build_tool_message(self, result: ToolResult, tc_id: str):
            return ChatMessage(
                role="tool",
                content=result.output or result.error or "",
                tool_call_id=tc_id,
            )

        def build_attachment_relay_message(self, _result: ToolResult):
            return None

        def check_confirmation_output(self, _tool_result: ToolResult):
            return None

        def build_pending_confirmation_payload(self, *_args, **_kwargs):
            return {}

        def build_confirmation_event(self, _payload):
            return {"event": "confirmation"}

        def build_assistant_tool_call_message(
            self,
            *,
            content: str,
            tool_calls: list[dict[str, object]],
            reasoning_content: str | None = None,
        ):
            _ = reasoning_content
            return ChatMessage(role="assistant", content=content, tool_calls=tool_calls)

    monkeypatch.setattr(tool_processor_mod, "ToolCallProcessor", FakeStreamProcessor)

    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    prep = PreparedExecution(
        messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
        tools=tools,
        all_tools=tools,
        tool_use_policy=ToolUsePolicy(
            family="weather",
            mode="required",
            allowed_tool_names=["get_current_weather"],
            retry_on_contract_breach=False,
            reason="intent:weather_query",
        ),
        intent_plan=[
            IntentPlan(
                intent_id="intent-weather",
                kind="weather_query",
                family="weather",
                order=1,
                user_visible_label="天气",
                source_text="今天凤凰县天气咋样",
                allowed_tool_names=["get_current_weather"],
                completion_signals=["get_current_weather"],
            )
        ],
        execution_path="fast",
        execution_budget=budget,
    )
    prep.rag_sources = []
    prep.rag_source_kinds = []

    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=1,
        conversation_id=851,
        stream=True,
        messages=[ChatMessage(role="user", content="今天凤凰县天气咋样")],
        interaction_updates=[],
        tool_use_policy=prep.tool_use_policy,
    )

    call_counter = {"count": 0}

    def _force_budget_exit(self) -> None:
        if self.budget is None:
            return
        if len(processed_cities) >= 2:
            self.budget.tool_result_bytes_used = (
                self.budget.max_tool_result_bytes + 1
            )
        else:
            self.budget.tool_result_bytes_used = 0

    monkeypatch.setattr(ExecutionStateMachine, "sync_elapsed", _force_budget_exit)

    async def _fake_stream_llm_chunks(**kwargs):
        call_counter["count"] += 1
        metadata = {"runtime_model_info": {}, "runtime_turn_record": {}}
        if call_counter["count"] == 1:
            yield ChatChunk(
                delta="",
                tool_calls=[_weather_tool_call(city="凤凰县", call_id="tc_weather_initial")],
                total_tokens=8,
                output_tokens=4,
                metadata=metadata,
            )
            return
        if call_counter["count"] == 2:
            yield ChatChunk(
                delta="",
                tool_calls=[_weather_tool_call(city="凤凰", call_id="tc_weather_retry")],
                total_tokens=4,
                output_tokens=2,
                metadata=metadata,
            )
            return
        assert kwargs["tools"] == []
        yield ChatChunk(
            delta="凤凰今天晴，气温 7.5°C。",
            tool_calls=[_weather_tool_call(city="长沙", call_id="tc_unexpected_finalization")],
            total_tokens=6,
            output_tokens=6,
            metadata=metadata,
        )

    monkeypatch.setattr(engine, "_stream_llm_chunks", _fake_stream_llm_chunks)

    handler = StreamExecutionHandler(
        engine=engine,
        agent=_make_agent(),
        request=request,
        prep=prep,
        start_time=0,
        on_complete=None,
    )

    captured: dict[str, object] = {}
    handler._schedule_on_complete = lambda result: captured.setdefault("result", result)

    async for _ in handler.generate():
        pass

    result = captured["result"]

    assert "凤凰" in result.output
    assert "7.5" in result.output
    assert processed_cities == ["凤凰县", "凤凰"]
    assert call_counter["count"] == 2


def test_partial_output_prefers_cached_completed_result_and_distinguishes_tool_timeout() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-time",
            kind="time_query",
            family="time",
            order=1,
            user_visible_label="时间",
            source_text="现在几点",
            status="completed",
        ),
        IntentPlan(
            intent_id="intent-weather",
            kind="weather_query",
            family="weather",
            order=2,
            user_visible_label="天气",
            source_text="今天什么天气",
            status="pending",
        ),
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="retry_budget_exhausted",
        provider_failure_kind="tool_timeout",
        intent_results={"intent-time": "现在是 14:30。"},
    )

    assert "现在是 14:30" in output
    assert "天气" in output
    assert "超时" in output


def test_recovery_manager_caches_completed_intent_result_from_tool_output() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-weather",
            kind="weather_query",
            family="weather",
            order=1,
            user_visible_label="天气",
            source_text="今天西安天气",
            status="pending",
            allowed_tool_names=["get_current_weather"],
            completion_signals=["get_current_weather"],
        )
    ]
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "tc-weather",
                    "type": "function",
                    "success": True,
                    "function": {
                        "name": "get_current_weather",
                        "arguments": '{"city":"西安"}',
                    },
                }
            ],
        )
    ]
    tool_results = [
        ToolResult(
            tool_call_id="tc-weather",
            name="get_current_weather",
            success=True,
            output='{"city":"西安","condition":"多云","temperature":"18C"}',
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=messages,
        tool_results=tool_results,
    )

    assert updated[0].status == "completed"
    assert updated[0].cached_result == "西安现在多云，气温约 18C。"
    assert updated[0].metadata["cached_result"] == "西安现在多云，气温约 18C。"


def test_recovery_manager_prefers_current_completed_tool_result_over_stale_cache() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="AI 新闻",
            source_text="联网查一下今日 AI 最新要闻",
            status="pending",
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
            cached_result="旧的搜索命中缓存",
            metadata={"cached_result": "旧的搜索命中缓存"},
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                summary=(
                    "TodayAiNews.com ~ The latest Artificial Intelligence (AI) news - "
                    "The latest Artificial Intelligence (AI) news, articles, photos, slideshows and videos."
                ),
            )
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].cached_result.startswith("TodayAiNews.com")
    assert updated[0].cached_result != "旧的搜索命中缓存"


def test_recovery_manager_treats_terminal_failure_as_partial_exit_not_retry() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-weather",
            kind="weather_query",
            family="weather",
            order=1,
            user_visible_label="天气",
            source_text="今天西安天气",
            status="pending",
            allowed_tool_names=["get_current_weather"],
            completion_signals=["get_current_weather"],
        )
    ]

    decision = RecoveryManager.decide(
        intents,
        budget=_make_budget(),
        provider_failure_kind="provider_unavailable",
    )

    assert decision is not None
    assert decision.action == "return_partial"
    assert decision.reason == "terminal_failure"
    assert decision.provider_failure_kind == "provider_unavailable"
