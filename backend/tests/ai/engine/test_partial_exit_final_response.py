from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.types import (
    ExecutionBudget,
    ExecutionRequest,
    IntentPlan,
    PreparedExecution,
    ToolUsePolicy,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


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


@pytest.mark.asyncio
async def test_budget_exit_with_tool_results_still_generates_final_response(monkeypatch) -> None:
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
        execution_budget=ExecutionBudget(
            max_prompt_tokens=4000,
            max_completion_tokens=2000,
            max_tool_rounds=2,
            max_elapsed_ms=40000,
            max_retry_per_intent=1,
            max_candidate_tools=3,
            max_tool_result_bytes=16000,
        ),
    )
    engine._prepare_execution = AsyncMock(return_value=prep)
    engine._call_llm = AsyncMock(
        side_effect=[
            ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                tool_calls=[
                    {
                        "id": "tc_weather",
                        "type": "function",
                        "function": {
                            "name": "get_current_weather",
                            "arguments": '{"city":"西安"}',
                        },
                    }
                ],
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

    assert result.partial is True
    assert result.success is False
    assert result.completion_reason == "elapsed_budget_exceeded"
    assert result.output == "西安现在多云，气温约 18C。"
    assert len(engine._call_llm.await_args_list) == 2
    assert engine._call_llm.await_args_list[1].kwargs["tools"] is None
    assert (
        engine._call_llm.await_args_list[1].kwargs["tool_use_policy"].reason
        == "partial_exit_final_response"
    )
