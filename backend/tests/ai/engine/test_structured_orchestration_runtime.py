from __future__ import annotations

import asyncio

from app.ai.engine.budget_guard import BudgetGuard
from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.failure_classifier import FailureClassifier
from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.path_selector import PathSelector
from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.tool_router import ToolRouter
from app.ai.engine.types import (
    ExecutionBudget,
    IntentPlan,
    PreparedExecution,
    RecoveryDecision,
)
from app.ai.exceptions import (
    AIGatewayError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage


def _tool(name: str, description: str = "") -> ToolDefinition:
    return ToolDefinition(name=name, description=description or name)


def _mixed_tools() -> list[ToolDefinition]:
    return [
        _tool("get_current_weather", "Current weather"),
        _tool("get_weather_forecast", "Forecast"),
        _tool("web_search", "Search the web"),
        _tool("fetch_url", "Fetch url"),
        _tool("get_page_context", "Read page"),
        _tool("invoke_page_operation", "Operate page"),
        _tool("pageop_navigate_menu", "Navigate menu"),
    ]


def _page_context() -> dict:
    return {
        "page_context": {
            "page_key": "admin.ai.dashboard",
            "page_data": {
                "available_operations": [{"name": "navigate_menu"}],
                "available_menus": [
                    {
                        "title": "智能体管理",
                        "page_key": "admin.ai.agents",
                        "path": "/admin/ai/agents",
                        "description": "创建、编辑和管理 AI 智能体",
                        "keywords": ["智能体", "agent", "AI助手"],
                        "capabilities": ["create_agent"],
                        "category": "ai",
                    }
                ],
            },
        }
    }


def _intent(
    intent_id: str,
    *,
    kind: str,
    family: str,
    order: int,
    label: str | None = None,
    status: str = "pending",
    allowed_tool_names: list[str] | None = None,
) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind=kind,
        family=family,
        order=order,
        user_visible_label=label or kind,
        source_text="user turn",
        status=status,
        allowed_tool_names=list(allowed_tool_names or []),
        completion_signals=list(allowed_tool_names or []),
    )


def test_intent_planner_splits_666_style_turn_into_stable_ordered_intents() -> None:
    intents = IntentPlanner.plan_turn(
        messages=[
            ChatMessage(
                role="user",
                content="请帮我查一下今天北京的天气，然后联网查一下长沙去北京的高铁票，再帮我阅读一下本页面都有什么内容",
            )
        ],
        tools=_mixed_tools(),
        input_variables=_page_context(),
        continuation_context=None,
    )

    assert [intent.family for intent in intents] == [
        "weather",
        "web_research",
        "page_ops",
    ]
    assert [intent.kind for intent in intents] == [
        "weather_query",
        "web_research",
        "page_read",
    ]
    assert [intent.user_visible_label for intent in intents] == [
        "weather",
        "rail_search",
        "page_read",
    ]


def test_intent_planner_keeps_page_follow_up_in_page_family() -> None:
    intents = IntentPlanner.plan_turn(
        messages=[
            ChatMessage(role="user", content="看看本页面"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "get_page_context"},
                    }
                ],
            ),
            ChatMessage(role="user", content="你再分析一下新的页面"),
        ],
        tools=_mixed_tools(),
        input_variables=_page_context(),
        continuation_context=None,
    )

    assert len(intents) == 1
    assert intents[0].family == "page_ops"
    assert intents[0].requires_tools is True


def test_path_selector_routes_fast_normal_and_deep_by_intent_shape() -> None:
    fast = PathSelector.select(
        [_intent("intent-1", kind="page_read", family="page_ops", order=1)]
    )
    normal = PathSelector.select(
        [
            _intent("intent-1", kind="weather_query", family="weather", order=1),
            _intent("intent-2", kind="web_research", family="web_research", order=2),
        ]
    )
    deep = PathSelector.select(
        [
            _intent("intent-1", kind="weather_query", family="weather", order=1),
            _intent("intent-2", kind="web_research", family="web_research", order=2),
            _intent("intent-3", kind="page_read", family="page_ops", order=3),
        ]
    )

    assert fast == "fast"
    assert normal == "normal"
    assert deep == "deep"


def test_tool_router_omits_forecast_for_current_weather_only() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)
    intent = _intent("intent-1", kind="weather_query", family="weather", order=1)

    decision = ToolRouter.route(
        intents=[intent],
        tools=_mixed_tools(),
        budget=budget,
        input_variables={},
        user_text="帮我查一下北京现在的天气",
    )

    assert decision.intent_allowed_tools["intent-1"] == ["get_current_weather"]
    assert decision.intent_preferred_tools["intent-1"] == ["get_current_weather"]
    assert "get_weather_forecast" not in decision.candidate_tool_names()


def test_tool_router_caps_mixed_candidates_and_preserves_page_read_focus() -> None:
    budget = BudgetGuard.build_default("deep", intent_count=3)
    intents = [
        _intent("intent-1", kind="weather_query", family="weather", order=1),
        _intent("intent-2", kind="web_research", family="web_research", order=2),
        _intent("intent-3", kind="page_read", family="page_ops", order=3),
    ]

    decision = ToolRouter.route(
        intents=intents,
        tools=_mixed_tools(),
        budget=budget,
        input_variables=_page_context(),
        user_text="查天气、搜高铁票、阅读本页面",
    )

    assert len(decision.candidate_tool_names()) <= budget.max_candidate_tools
    assert decision.intent_allowed_tools["intent-3"] == ["get_page_context"]
    assert set(decision.candidate_tool_names()) == {
        "get_current_weather",
        "web_search",
        "fetch_url",
        "get_page_context",
    }


def test_budget_guard_registers_preparation_and_detects_candidate_budget_exit() -> None:
    budget = ExecutionBudget(
        max_prompt_tokens=5000,
        max_completion_tokens=1000,
        max_tool_rounds=2,
        max_elapsed_ms=10000,
        max_retry_per_intent=1,
        max_candidate_tools=2,
        max_tool_result_bytes=4096,
    )

    BudgetGuard.register_preparation(
        budget,
        prompt_tokens=1200,
        candidate_tools_count=3,
    )

    assert budget.prompt_tokens_used == 1200
    assert budget.candidate_tools_count == 3
    assert budget.first_exceeded_reason() == "candidate_tool_budget_exceeded"


def test_budget_guard_completion_budget_uses_output_tokens_not_total_tokens() -> None:
    budget = BudgetGuard.build_default("fast", intent_count=1)

    assert (
        BudgetGuard.completion_reason(
            budget,
            completion_tokens=48,
            total_tokens=1359,
        )
        is None
    )
    assert (
        BudgetGuard.completion_reason(
            budget,
            completion_tokens=budget.max_completion_tokens + 1,
            total_tokens=budget.max_completion_tokens + 200,
        )
        == "completion_budget_exceeded"
    )


def test_recovery_manager_retries_only_unfinished_page_intent() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="weather_query",
            family="weather",
            order=1,
            status="completed",
            allowed_tool_names=["get_current_weather"],
        ),
        _intent(
            "intent-2",
            kind="web_research",
            family="web_research",
            order=2,
            status="completed",
            allowed_tool_names=["web_search", "fetch_url"],
        ),
        _intent(
            "intent-3",
            kind="page_read",
            family="page_ops",
            order=3,
            status="pending",
            allowed_tool_names=["get_page_context"],
        ),
    ]
    budget = BudgetGuard.build_default("deep", intent_count=3)

    decision = RecoveryManager.decide(intents, budget=budget)
    assert decision is not None
    assert decision.action == "retry_intent"
    assert decision.target_intent_id == "intent-3"
    assert decision.retry_family == "page_ops"
    assert decision.allowed_tool_names == ["get_page_context"]
    assert decision.completed_intent_ids == ["intent-1", "intent-2"]
    assert decision.unfinished_intent_ids == ["intent-3"]

    message = RecoveryManager.build_recovery_message(decision=decision, intents=intents)
    assert message.role == "system"
    assert "Allowed tools for this recovery: get_page_context." in message.content
    assert "Unfinished requested intents: page_read." in message.content


def test_recovery_manager_returns_partial_when_retry_budget_is_exhausted() -> None:
    intents = [
        _intent(
            "intent-3",
            kind="page_read",
            family="page_ops",
            order=3,
            status="pending",
            allowed_tool_names=["get_page_context"],
        )
    ]
    budget = BudgetGuard.build_default("normal", intent_count=1)
    budget.retries_by_intent["intent-3"] = 1

    decision = RecoveryManager.decide(
        intents,
        budget=budget,
        provider_failure_kind="tool_timeout",
    )

    assert decision is not None
    assert decision.action == "return_partial"
    assert decision.reason == "retry_budget_exhausted"
    assert decision.provider_failure_kind == "tool_timeout"
    assert decision.unfinished_intent_ids == ["intent-3"]


def test_failure_classifier_distinguishes_provider_and_tool_failures() -> None:
    timeout_kind, timeout_event = FailureClassifier.classify_exception(
        ProviderTimeoutError("provider timed out")
    )
    rate_limit_kind, rate_limit_event = FailureClassifier.classify_exception(
        ProviderRateLimitError("too many requests")
    )
    http_5xx_exc = AIGatewayError("upstream 503")
    http_5xx_exc.status_code = 503
    http_5xx_kind, http_5xx_event = FailureClassifier.classify_exception(http_5xx_exc)
    interrupt_kind, interrupt_event = FailureClassifier.classify_exception(
        asyncio.CancelledError()
    )
    tool_kind, tool_events = FailureClassifier.classify_tool_results(
        [
            ToolResult(
                tool_call_id="call-1",
                name="get_page_context",
                success=False,
                error="timeout",
                error_type="timeout",
            )
        ]
    )

    assert timeout_kind == "provider_timeout"
    assert timeout_event["kind"] == "provider_timeout"
    assert rate_limit_kind == "provider_rate_limit"
    assert rate_limit_event["kind"] == "provider_rate_limit"
    assert http_5xx_kind == "provider_http_5xx"
    assert http_5xx_event["status_code"] == 503
    assert interrupt_kind == "server_interrupt"
    assert interrupt_event["kind"] == "server_interrupt"
    assert tool_kind == "tool_timeout"
    assert tool_events == [
        {
            "tool_name": "get_page_context",
            "error_type": "timeout",
            "error": "timeout",
        }
    ]


def test_execution_state_machine_accumulates_usage_and_emits_turn_diagnostics() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="weather_query",
            family="weather",
            order=1,
            allowed_tool_names=["get_current_weather"],
        ),
        _intent(
            "intent-2",
            kind="page_read",
            family="page_ops",
            order=2,
            allowed_tool_names=["get_page_context"],
        ),
    ]
    budget = BudgetGuard.build_default("normal", intent_count=2)
    prep = PreparedExecution(
        intent_plan=intents,
        execution_path="normal",
        execution_budget=budget,
        tools=[
            _tool("get_current_weather"),
            _tool("get_page_context"),
        ],
        provider_events=[{"kind": "provider_timeout", "trace_id": "t-1"}],
        recovery_history=[
            RecoveryDecision(
                action="retry_intent",
                target_intent_id="intent-2",
                retry_family="page_ops",
                allowed_tool_names=["get_page_context"],
                completed_intent_ids=["intent-1"],
                unfinished_intent_ids=["intent-2"],
                reason="unfinished_intent_retry",
            )
        ],
    )

    machine = ExecutionStateMachine.from_prepared_execution(prep)
    machine.register_completion_tokens(321)
    machine.register_tool_round()
    machine.register_tool_results(
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "get_current_weather"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-1",
                name="get_current_weather",
                success=True,
                output='{"temperature": 8.4}',
            )
        ],
    )
    machine.register_provider_failure(
        kind="provider_timeout",
        event={"kind": "provider_timeout", "status_code": 504},
    )
    machine.register_retry(
        RecoveryDecision(
            action="retry_intent",
            target_intent_id="intent-2",
            retry_family="page_ops",
            allowed_tool_names=["get_page_context"],
            completed_intent_ids=["intent-1"],
            unfinished_intent_ids=["intent-2"],
            reason="unfinished_intent_retry",
        )
    )

    payload = machine.build_diagnostics_payload()

    assert payload["execution_path"] == "normal"
    assert payload["routing"]["candidate_tool_names"] == [
        "get_current_weather",
        "get_page_context",
    ]
    assert payload["failures"]["failure_kind"] == "provider_timeout"
    assert payload["failures"]["provider_events"][-1]["status_code"] == 504
    assert payload["budget"]["usage"]["tool_rounds_used"] == 1
    assert payload["budget"]["usage"]["completion_tokens_used"] == 321
    assert payload["budget"]["usage"]["tool_result_bytes_used"] > 0
    assert payload["budget"]["usage"]["retries_by_intent"]["intent-2"] == 1
    assert payload["recovery"]["retry_events"][-1]["target_intent_id"] == "intent-2"
    assert payload["recovery"]["unfinished_intents"] == ["intent-2"]
    assert payload["intent_plan"][0]["status"] == "completed"
    assert payload["intent_plan"][0]["completed_by_tool_names"] == ["get_current_weather"]
