"""
Test type: behavioral
Regression for: BUG-2026-05-04-2282
Original symptom: conversation 2282 successfully ran web_search, then elapsed
budget exit prevented the required fetch_url verification step and the user saw
only a partial "sources need verification" fallback.
Scope: TurnExecutor web_research control flow after successful search evidence.
Mock strategy: provider transport is a controlled recorded-shape replay; the test
does not assert the mocked LLM answer, it asserts the runtime's deterministic
fetch_url synthesis and recovered tool-evidence output.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.turn_executor import ModelRoundResult, ToolBatchResult, TurnExecutor
from app.ai.engine.types import IntentPlan, ToolUsePolicy
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _ReplayIOAdapter:
    def __init__(
        self,
        *,
        model_rounds: list[ModelRoundResult],
        tool_batches: list[ToolBatchResult],
        after_first_model_round: Callable[[], None] | None = None,
    ) -> None:
        self.model_rounds = list(model_rounds)
        self.tool_batches = list(tool_batches)
        self.after_first_model_round = after_first_model_round
        self.call_history: list[dict[str, Any]] = []
        self.tool_call_history: list[dict[str, Any]] = []
        self.finalize_calls: list[dict[str, Any]] = []
        self.finalize_completed_calls: list[dict[str, Any]] = []
        self.retry_logs: list[str] = []

    async def call_llm(self, **kwargs: Any) -> ModelRoundResult:
        self.call_history.append(dict(kwargs))
        if not self.model_rounds:
            raise AssertionError("No model rounds left")
        round_result = self.model_rounds.pop(0)
        if len(self.call_history) == 1 and self.after_first_model_round is not None:
            self.after_first_model_round()
        return round_result

    async def handle_tool_calls(self, **kwargs: Any) -> ToolBatchResult:
        self.tool_call_history.append(dict(kwargs))
        if not self.tool_batches:
            raise AssertionError("No tool batches left")
        response = kwargs["response"]
        messages = kwargs["messages"]
        tool_calls = list(response.tool_calls or response.message.tool_calls or [])
        messages.append(
            ChatMessage(role="assistant", content="", tool_calls=tool_calls)
        )
        batch = self.tool_batches.pop(0)
        for result in batch.tool_results:
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result.output or result.summary or "",
                    name=result.name,
                    tool_call_id=result.tool_call_id,
                )
            )
        return batch

    async def finalize_partial_output(self, **kwargs: Any) -> tuple[str, int, int]:
        self.finalize_calls.append(dict(kwargs))
        return ("这些来源还需要继续核验，我先把目前能确认的内容给你。", 23, 23)

    async def finalize_completed_output(self, **kwargs: Any) -> tuple[str, int, int]:
        self.finalize_completed_calls.append(dict(kwargs))
        state = kwargs["state"]
        tool_results = kwargs["tool_results"]
        reason = str(kwargs.get("reason") or "completed")
        return (
            RecoveryManager.build_completed_output(
                state.intent_plan,
                tool_results=tool_results,
                reason=reason,
            ),
            int(kwargs.get("total_tokens") or 0),
            int(kwargs.get("completion_tokens_used") or 0),
        )

    def should_retry_tool_contract_breach(self, **_kwargs: Any):
        return False, None, ""

    def should_retry_web_research_contract_breach(self, **_kwargs: Any):
        return False, None, ""

    def analyze_post_tool_contract_breach(self, **_kwargs: Any):
        return None, None, {}

    def restrict_tools_to_names(
        self,
        tools: list[ToolDefinition],
        allowed_tool_names: list[str] | None,
    ) -> list[ToolDefinition]:
        if not allowed_tool_names:
            return list(tools)
        allowed = set(allowed_tool_names)
        return [tool for tool in tools if tool.name in allowed]

    def log_tool_contract_diagnostics(self, **kwargs: Any) -> None:
        self.retry_logs.append(str(kwargs.get("retry_result") or ""))

    async def emit_chunk(self, text: str) -> None:
        _ = text


def _assistant_response(
    content: str,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
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


def _web_research_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-1",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="大模型排行榜",
        source_text="查一下大模型排行榜 2026  水平排行！",
        status="pending",
        requires_tools=True,
        allowed_tool_names=["web_search", "fetch_url"],
        preferred_tool_names=["web_search", "fetch_url"],
        completion_signals=["fetch_url"],
        metadata={
            "routing_mode": "structured_semantic",
            "native_search_preferred": True,
            "fallback_tool_names": ["web_search", "fetch_url"],
        },
    )


def _prepared_execution(tools: list[ToolDefinition], intents: list[IntentPlan]):
    return SimpleNamespace(
        messages=[
            ChatMessage(role="user", content="查一下大模型排行榜 2026  水平排行！")
        ],
        tools=list(tools),
        all_tools=list(tools),
        tool_use_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
            retry_on_contract_breach=False,
            reason="native_web_search_first:web_research",
        ),
        execution_budget=BudgetGuard.build_default("normal", intent_count=len(intents)),
        execution_path="normal",
        intent_plan=list(intents),
        diagnostics={},
        provider_events=[],
        recovery_history=[],
        continuation_context=None,
    )


@pytest.mark.asyncio
async def test_bug_2026_05_04_2282_chains_fetch_url_before_budget_partial_exit() -> (
    None
):
    tools = [
        ToolDefinition(name="web_search", description="Search"),
        ToolDefinition(name="fetch_url", description="Fetch"),
    ]
    prep = _prepared_execution(tools, [_web_research_intent()])
    state = ExecutionStateMachine.from_prepared_execution(prep)

    def expire_elapsed_budget_after_initial_model() -> None:
        state.started_at = time.perf_counter() - 76

    search_url = "http://www.baidu.com/link?url=rank-2282"
    io = _ReplayIOAdapter(
        model_rounds=[
            _assistant_response(
                "",
                tool_calls=[
                    {
                        "id": "call-search-2282",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": (
                                '{"query":"2026 大模型 排行榜 LM leaderboard May '
                                'Artificial AnalysisMArena","max_results":5}'
                            ),
                        },
                    }
                ],
            )
        ],
        tool_batches=[
            ToolBatchResult(
                response=None,
                tool_results=[
                    ToolResult(
                        tool_call_id="call-search-2282",
                        name="web_search",
                        success=True,
                        output="Search results for: 2026 大模型 排行榜",
                        summary="baidu_public: 5 result(s)",
                        summary_payload={
                            "status": "success",
                            "result_count": 5,
                            "items": [
                                {
                                    "title": "2026大模型 战力榜:一句话看懂谁称王",
                                    "url": search_url,
                                    "snippet": (
                                        "SWE-bench编码得分80%+，agent能力顶尖；"
                                        "GPT-5.2 推理、数学、速度多项基准靠前。"
                                    ),
                                }
                            ],
                        },
                    )
                ],
                total_tokens=7,
                completion_tokens_used=7,
            ),
            ToolBatchResult(
                response=None,
                tool_results=[
                    ToolResult(
                        tool_call_id="synthetic_intent-1_fetch_url_1",
                        name="fetch_url",
                        success=True,
                        output=(
                            "Content from https://example.com/llm-rank-2026:\n"
                            "Title: 2026大模型 战力榜:一句话看懂谁称王\n\n"
                            "Claude Opus 4.5 在 SWE-bench 编码得分80%+，"
                            "agent能力位居第一梯队。\n"
                            "GPT-5.2 在推理、数学、速度多项基准靠前，"
                            "Artificial Analysis v4.0指数进入第一梯队。\n"
                            "LMArena 仍需结合具体日期和榜单维度核验。"
                        ),
                        summary="Fetched https://example.com/llm-rank-2026",
                        summary_payload={
                            "fetch_url": True,
                            "ok": True,
                            "requested_url": search_url,
                            "final_url": "https://example.com/llm-rank-2026",
                            "summary": "Fetched https://example.com/llm-rank-2026",
                        },
                    )
                ],
                total_tokens=7,
                completion_tokens_used=7,
            ),
        ],
        after_first_model_round=expire_elapsed_budget_after_initial_model,
    )

    result = await TurnExecutor.run(
        state=state,
        io=io,
        prep=prep,
        request=SimpleNamespace(input_variables={}, conversation_id=2282),
        agent=SimpleNamespace(id=59),
    )

    assert len(io.tool_call_history) == 2
    synthetic_call = io.tool_call_history[1]["response"].tool_calls[0]
    assert synthetic_call["function"]["name"] == "fetch_url"
    assert search_url in synthetic_call["function"]["arguments"]
    assert state.intent_plan[0].status == "completed"
    assert state.intent_plan[0].completed_by_tool_names == ["fetch_url"]
    assert result.partial is False
    assert result.completion_reason == "completed"
    assert result.final_output_source == "recovery_evidence"
    assert "SWE-bench 编码得分80%+" in result.output
    assert "Artificial Analysis v4.0指数进入第一梯队" in result.output
    assert "这些来源还需要继续核验" not in result.output
    assert io.finalize_completed_calls
    assert len(io.call_history) == 1
    assert (
        state.preparation_diagnostics["synthetic_required_fetch_url_reason"]
        == "required_fetch_url_after_search_success"
    )
    assert (
        state.preparation_diagnostics[
            "budget_synthesis_skipped_for_synthetic_fetch_url"
        ]
        is True
    )
