from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.engine.base import BaseEngine
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
    ToolUsePolicy,
)
from app.ai.exceptions import (
    AIGatewayError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


def _tool(name: str, description: str = "") -> ToolDefinition:
    return ToolDefinition(name=name, description=description or name)


def _mixed_tools() -> list[ToolDefinition]:
    return [
        _tool("get_current_weather", "Current weather"),
        _tool("get_weather_forecast", "Forecast"),
        _tool("web_search", "Search the web"),
        _tool("fetch_url", "Fetch url"),
        _tool("ui_get_snapshot", "Read page"),
        _tool("ui_read_region", "Read region"),
        _tool("ui_click", "Click ui"),
    ]


def _page_context() -> dict:
    return {
        "page_context": {
            "page_key": "admin.ai.dashboard",
            "page_title": "AI 仪表盘",
            "page_session_id": "session-dashboard",
            "ui_epoch": 1,
            "suggested_tools": {
                "primary": ["ui_get_snapshot", "ui_click"],
                "secondary": ["ui_read_region"],
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
    metadata: dict | None = None,
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
        metadata=dict(metadata or {}),
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
        "page_summary",
    ]
    assert [intent.user_visible_label for intent in intents] == [
        "weather",
        "rail_search",
        "page_summary",
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
                        "function": {"name": "ui_get_snapshot"},
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


def test_detect_requested_turn_intents_aligns_with_planner_for_page_row_detail() -> None:
    user_text = "现在几点了？帮我查北京天气，再搜索今天 AI 新闻，然后看看当前页面第一条记录或关键内容"
    intent_plan = IntentPlanner.plan_turn(
        messages=[ChatMessage(role="user", content=user_text)],
        tools=_mixed_tools(),
        input_variables=_page_context(),
        continuation_context=None,
    )
    input_variables = {
        **_page_context(),
        "_runtime_intent_plan": [intent.to_dict() for intent in intent_plan],
    }
    intents = BaseEngine._detect_requested_turn_intents(
        user_text,
        tools=_mixed_tools(),
        input_variables=input_variables,
    )

    assert intents == ["weather", "page_summary"]


def test_post_tool_contract_breach_keeps_page_intent_when_page_not_executed() -> None:
    user_text = "现在几点了？帮我查北京天气，再搜索今天 AI 新闻，然后看看当前页面第一条记录或关键内容"
    messages = [
        ChatMessage(
            role="user",
            content=user_text,
        ),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {"success": True, "function": {"name": "get_current_weather"}},
                {"success": True, "function": {"name": "web_search"}},
                {"success": True, "function": {"name": "fetch_url"}},
            ],
        ),
    ]
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="现在是北京时间，今天北京天气我也查到了，并给你整理了今天的 AI 新闻。",
        ),
        tool_calls=None,
    )
    intent_plan = IntentPlanner.plan_turn(
        messages=[ChatMessage(role="user", content=user_text)],
        tools=_mixed_tools(),
        input_variables=_page_context(),
        continuation_context=None,
    )
    input_variables = {
        **_page_context(),
        "_runtime_intent_plan": [intent.to_dict() for intent in intent_plan],
    }

    breach_type, retry_policy, diagnostics = BaseEngine._analyze_post_tool_contract_breach(
        messages=messages,
        response=response,
        current_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
        ),
        tools=_mixed_tools(),
        input_variables=input_variables,
    )

    assert breach_type == "unfinished_multi_intent_reply"
    assert retry_policy is not None
    assert diagnostics["requested_intents"] == ["weather", "page_summary"]
    assert diagnostics["unfinished_intents"] == ["page_summary"]
    assert "ui_get_snapshot" in retry_policy.allowed_tool_names


def test_post_tool_contract_breach_native_web_evidence_keeps_page_intent_pending() -> (
    None
):
    response = ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="我已经根据抓取到的网页内容整理了天气信息。",
        ),
        tool_calls=None,
        raw_response={
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "我已经根据抓取到的网页内容整理了天气信息。",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://weather.example.com/beijing",
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )

    breach_type, retry_policy, diagnostics = BaseEngine._analyze_post_tool_contract_breach(
        messages=[ChatMessage(role="user", content="查一下北京天气，再看看当前页面")],
        response=response,
        current_policy=ToolUsePolicy(
            family="web_research",
            mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
        ),
        tools=_mixed_tools(),
        input_variables={
            **_page_context(),
            "_runtime_intent_facts": {
                "requested_intents": ["weather", "page_summary"],
            },
        },
    )

    assert breach_type == "unfinished_multi_intent_reply"
    assert retry_policy is not None
    assert diagnostics["completed_intents"] == ["weather"]
    assert diagnostics["unfinished_intents"] == ["page_summary"]
    assert diagnostics["native_web_search_evidence"] is True


def test_post_tool_contract_breach_retries_cross_page_navigation_after_snapshot_only() -> (
    None
):
    tools = [
        _tool("ui_get_snapshot", "Read page"),
        _tool("ui_list_interactables", "List interactables"),
        _tool("ui_click", "Click ui"),
        _tool("ui_open_surface", "Open surface"),
    ]
    user_text = "添加供应商"
    input_variables = {
        "page_context": {
            "page_key": "admin.ai.conversations",
            "page_title": "对话管理",
            "page_session_id": "session-conversations",
            "ui_epoch": 3,
            "page_data": {
                "navigation_catalog": [
                    {
                        "title": "供应商管理",
                        "path": "/admin/suppliers",
                        "page_key": "admin.suppliers",
                        "keywords": ["供应商", "添加供应商"],
                    }
                ]
            },
            "suggested_tools": {
                "primary": [
                    "ui_get_snapshot",
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                ]
            },
        }
    }
    intent_plan = IntentPlanner.plan_turn(
        messages=[ChatMessage(role="user", content=user_text)],
        tools=tools,
        input_variables=input_variables,
        continuation_context=None,
    )
    input_variables = {
        **input_variables,
        "_runtime_intent_plan": [intent.to_dict() for intent in intent_plan],
    }
    messages = [
        ChatMessage(role="user", content=user_text),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "success": True,
                    "function": {"name": "ui_get_snapshot"},
                }
            ],
        ),
    ]
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="我先帮你看一下当前页面。"),
        tool_calls=None,
    )

    breach_type, retry_policy, diagnostics = BaseEngine._analyze_post_tool_contract_breach(
        messages=messages,
        response=response,
        current_policy=ToolUsePolicy(
            family="page_ops",
            mode="required",
            allowed_tool_names=[
                "ui_get_snapshot",
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
            ],
        ),
        tools=tools,
        input_variables=input_variables,
    )

    assert breach_type == "unfinished_multi_intent_reply"
    assert retry_policy is not None
    assert retry_policy.family == "page_ops"
    assert diagnostics["requested_intents"] == ["page_navigation"]
    assert diagnostics["unfinished_intents"] == ["page_navigation"]
    assert "ui_list_interactables" in retry_policy.allowed_tool_names
    assert "ui_open_surface" in retry_policy.allowed_tool_names


def test_recovery_manager_keeps_page_navigation_pending_after_snapshot_only() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="page_navigation",
            family="page_ops",
            order=1,
            allowed_tool_names=[
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "ui_get_snapshot"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-page",
                name="ui_get_snapshot",
                success=True,
                output='{"ui_epoch": 5}',
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []

    decision = RecoveryManager.decide(
        updated,
        budget=BudgetGuard.build_default("deep", intent_count=1),
    )

    assert decision is not None
    assert decision.action == "retry_intent"

    message = RecoveryManager.build_recovery_message(
        decision=decision,
        intents=updated,
    )

    assert "do NOT call ui_get_snapshot again" in message.content
    assert "ui_list_interactables" in message.content


def test_recovery_manager_completes_page_navigation_after_action_then_snapshot() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="page_navigation",
            family="page_ops",
            order=1,
            allowed_tool_names=[
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
            metadata={"page_workflow_stage": "discover_navigation_target"},
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "ui_click"},
                    },
                    {
                        "success": True,
                        "function": {"name": "ui_get_snapshot"},
                    },
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-nav-1",
                name="ui_click",
                success=True,
                summary_payload={"diff": {"surface_changed": True}},
            ),
            ToolResult(
                tool_call_id="call-nav-2",
                name="ui_get_snapshot",
                success=True,
                output='{"ui_epoch": 6}',
            ),
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["ui_click", "ui_get_snapshot"]


def test_recovery_manager_keeps_submit_stage_form_write_pending_after_fill_only() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="page_form_write",
            family="page_ops",
            order=1,
            allowed_tool_names=[
                "ui_get_form_state",
                "ui_fill_form",
                "ui_set_field",
                "ui_submit_form",
                "ui_open_surface",
            ],
            metadata={"page_workflow_stage": "submit_active_form"},
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "ui_fill_form"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-form-1",
                name="ui_fill_form",
                success=True,
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []


def test_recovery_manager_keeps_row_detail_pending_after_open_without_read() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="page_row_detail",
            family="page_ops",
            order=1,
            allowed_tool_names=[
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ],
            metadata={"page_workflow_stage": "open_detail_surface"},
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "success": True,
                        "function": {"name": "ui_open_surface"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-detail-1",
                name="ui_open_surface",
                success=True,
                summary_payload={"diff": {"surface_changed": True}},
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []


def test_path_selector_routes_fast_normal_and_deep_by_intent_shape() -> None:
    fast = PathSelector.select(
        [_intent("intent-1", kind="page_summary", family="page_ops", order=1)]
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
            _intent("intent-3", kind="page_summary", family="page_ops", order=3),
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


def test_tool_router_caps_mixed_candidates_and_preserves_page_summary_focus() -> None:
    budget = BudgetGuard.build_default("deep", intent_count=3)
    intents = [
        _intent("intent-1", kind="weather_query", family="weather", order=1),
        _intent("intent-2", kind="web_research", family="web_research", order=2),
        _intent("intent-3", kind="page_summary", family="page_ops", order=3),
    ]

    decision = ToolRouter.route(
        intents=intents,
        tools=_mixed_tools(),
        budget=budget,
        input_variables=_page_context(),
        user_text="查天气、搜高铁票、阅读本页面",
    )

    assert len(decision.candidate_tool_names()) <= budget.max_candidate_tools
    assert decision.intent_allowed_tools["intent-3"] == ["ui_get_snapshot"]
    assert set(decision.candidate_tool_names()) == {
        "get_current_weather",
        "web_search",
        "fetch_url",
        "ui_get_snapshot",
    }


def test_tool_router_allows_open_and_read_tools_for_page_form_read_without_active_form() -> (
    None
):
    budget = ExecutionBudget(
        max_prompt_tokens=4000,
        max_completion_tokens=1000,
        max_tool_rounds=2,
        max_elapsed_ms=10000,
        max_retry_per_intent=1,
        max_candidate_tools=8,
        max_tool_result_bytes=4096,
    )
    intents = [
        _intent("intent-1", kind="page_form_read", family="page_ops", order=1)
    ]
    tools = [
        _tool("ui_list_interactables", "List interactables"),
        _tool("ui_click", "Click ui"),
        _tool("ui_open_surface", "Open surface"),
        _tool("ui_get_form_state", "Get form state"),
        _tool("ui_read_region", "Read region"),
        _tool("ui_get_snapshot", "Read page"),
    ]

    decision = ToolRouter.route(
        intents=intents,
        tools=tools,
        budget=budget,
        input_variables={
            "page_context": {
                "page_key": "admin.ai.skills",
                "ui_epoch": 2,
            }
        },
        user_text="点击添加技能，看看表单里有哪些必填项，但不要提交",
    )

    assert decision.intent_allowed_tools["intent-1"] == [
        "ui_list_interactables",
        "ui_click",
        "ui_open_surface",
        "ui_get_form_state",
        "ui_read_region",
        "ui_get_snapshot",
    ]


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
            kind="page_summary",
            family="page_ops",
            order=3,
            status="pending",
            allowed_tool_names=["ui_get_snapshot"],
        ),
    ]
    budget = BudgetGuard.build_default("deep", intent_count=3)

    decision = RecoveryManager.decide(intents, budget=budget)
    assert decision is not None
    assert decision.action == "retry_intent"
    assert decision.target_intent_id == "intent-3"
    assert decision.retry_family == "page_ops"
    assert decision.allowed_tool_names == ["ui_get_snapshot"]
    assert decision.completed_intent_ids == ["intent-1", "intent-2"]
    assert decision.unfinished_intent_ids == ["intent-3"]

    message = RecoveryManager.build_recovery_message(decision=decision, intents=intents)
    assert message.role == "system"
    assert "Allowed tools for this recovery: ui_get_snapshot." in message.content
    assert "Unfinished requested intents: page_summary." in message.content


def test_recovery_manager_unions_allowed_tools_for_multiple_unfinished_intents() -> None:
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
            kind="page_summary",
            family="page_ops",
            order=2,
            status="pending",
            allowed_tool_names=["ui_get_snapshot"],
        ),
        _intent(
            "intent-3",
            kind="page_row_detail",
            family="page_ops",
            order=3,
            status="pending",
            allowed_tool_names=["ui_read_region"],
        ),
    ]
    budget = BudgetGuard.build_default("deep", intent_count=3)

    decision = RecoveryManager.decide(intents, budget=budget)

    assert decision is not None
    assert decision.action == "retry_intent"
    assert decision.target_intent_id == "intent-2"
    assert decision.allowed_tool_names == ["ui_get_snapshot", "ui_read_region"]
    assert decision.unfinished_intent_ids == ["intent-2", "intent-3"]


def test_recovery_manager_retry_tools_do_not_mix_cross_family_unfinished_intents() -> None:
    intents = [
        _intent(
            "intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            status="pending",
            allowed_tool_names=["web_search", "fetch_url"],
        ),
        _intent(
            "intent-2",
            kind="page_summary",
            family="page_ops",
            order=2,
            status="pending",
            allowed_tool_names=["ui_get_snapshot"],
        ),
    ]
    budget = BudgetGuard.build_default("normal", intent_count=2)

    decision = RecoveryManager.decide(intents, budget=budget)

    assert decision is not None
    assert decision.action == "retry_intent"
    assert decision.target_intent_id == "intent-1"
    assert decision.retry_family == "web_research"
    assert decision.allowed_tool_names == ["web_search", "fetch_url"]
    assert decision.unfinished_intent_ids == ["intent-1", "intent-2"]
    assert "ui_get_snapshot" not in decision.allowed_tool_names


def test_recovery_manager_returns_partial_when_retry_budget_is_exhausted() -> None:
    intents = [
        _intent(
            "intent-3",
            kind="page_summary",
            family="page_ops",
            order=3,
            status="pending",
            allowed_tool_names=["ui_get_snapshot"],
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
                name="ui_get_snapshot",
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
            "tool_name": "ui_get_snapshot",
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
            kind="page_summary",
            family="page_ops",
            order=2,
            allowed_tool_names=["ui_get_snapshot"],
        ),
    ]
    budget = BudgetGuard.build_default("normal", intent_count=2)
    prep = PreparedExecution(
        intent_plan=intents,
        execution_path="normal",
        execution_budget=budget,
        tools=[
            _tool("get_current_weather"),
            _tool("ui_get_snapshot"),
        ],
        provider_events=[{"kind": "provider_timeout", "trace_id": "t-1"}],
        recovery_history=[
            RecoveryDecision(
                action="retry_intent",
                target_intent_id="intent-2",
                retry_family="page_ops",
                allowed_tool_names=["ui_get_snapshot"],
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
            allowed_tool_names=["ui_get_snapshot"],
            completed_intent_ids=["intent-1"],
            unfinished_intent_ids=["intent-2"],
            reason="unfinished_intent_retry",
        )
    )

    payload = machine.build_diagnostics_payload()

    assert payload["execution_path"] == "normal"
    assert payload["routing"]["candidate_tool_names"] == [
        "get_current_weather",
        "ui_get_snapshot",
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


@pytest.mark.asyncio
async def test_call_runtime_query_turn_forwards_skip_metering_preflight(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result
        captured["skip_metering_preflight"] = skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            runtime_info={"model_id": 1},
        )

    async def fake_build_runtime_query_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        skip_metering_preflight=True,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=skip_metering_preflight,
        )

        class _Accounting:
            async def finalize_success(
                self,
                *,
                runtime_context,
                request_context,
                audit_context,
                output_text,
                input_tokens,
                output_tokens,
                total_tokens,
                start_time,
                turn_record,
                success_log_message,
            ):
                _ = (
                    runtime_context,
                    request_context,
                    audit_context,
                    output_text,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    start_time,
                    turn_record,
                    success_log_message,
                )
                return SimpleNamespace(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    usage_mode="test",
                )

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_run_runtime_query_entrypoint(*, plan, agent, selected_skill_names):
        _ = plan, agent, selected_skill_names
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_query_entrypoint_plan",
        fake_build_runtime_query_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "run_runtime_query_entrypoint",
        fake_run_runtime_query_entrypoint,
    )

    engine = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        gateway=SimpleNamespace(),
    )
    response, _query_engine = await bridge.call_runtime_query_turn(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=1,
        conversation_id=2,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        selected_skill_names=None,
        context_sources=None,
        execution_path="normal",
        extra_kwargs=None,
        skip_metering_preflight=False,
    )

    assert captured["skip_metering_preflight"] is False
    assert response.metadata["runtime_model_info"]["model_id"] == 1


@pytest.mark.asyncio
async def test_call_runtime_query_turn_passes_model_request_override_builder(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result, skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            runtime_info={"model_id": 1},
        )

    def fake_model_request_override_builder(*, execution_path, tools):
        captured["execution_path"] = execution_path
        captured["tools"] = tools
        return {"_runtime_reasoning_effort_override": "low"}

    async def fake_build_runtime_query_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        model_request_override_builder,
        **kwargs,
    ):
        _ = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )
        captured["builder_result"] = model_request_override_builder(
            execution_path=kwargs["execution_path"],
            tools=kwargs["tools"],
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return SimpleNamespace(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    usage_mode="test",
                )

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=SimpleNamespace(
                provider=SimpleNamespace(code="mock-provider"),
                model_code="mock-model",
                runtime_info={"model_id": 1},
            ),
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_run_runtime_query_entrypoint(*, plan, agent, selected_skill_names):
        _ = plan, agent, selected_skill_names
        return ChatResponse(
            message=ChatMessage(role="assistant", content="ok"),
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
        )

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_query_entrypoint_plan",
        fake_build_runtime_query_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "run_runtime_query_entrypoint",
        fake_run_runtime_query_entrypoint,
    )

    engine = SimpleNamespace(
        db=SimpleNamespace(commit=AsyncMock()),
        gateway=SimpleNamespace(),
    )
    response, _query_engine = await bridge.call_runtime_query_turn(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tools=None,
        all_tool_names=None,
        tool_use_policy=None,
        breach_retry_result=None,
        tenant_id=1,
        user_id=1,
        conversation_id=2,
        billing_context=None,
        route_result=None,
        log_user_type=None,
        selected_skill_names=None,
        context_sources=None,
        execution_path="fast",
        extra_kwargs=None,
        skip_metering_preflight=False,
        model_request_override_builder=fake_model_request_override_builder,
    )

    assert captured["execution_path"] == "fast"
    assert captured["tools"] is None
    assert captured["builder_result"] == {"_runtime_reasoning_effort_override": "low"}
    assert response.metadata["runtime_model_info"]["model_id"] == 1


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_skip_metering_preflight(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result
        captured["skip_metering_preflight"] = skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            ai_model=SimpleNamespace(supports_streaming=True),
            runtime_info={"model_id": 2},
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        skip_metering_preflight=False,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=skip_metering_preflight,
        )

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = plan, agent, selected_skill_names
        yield ChatChunk(delta="ok", finish_reason="stop", total_tokens=1)

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=2,
        tools=None,
        skip_metering_preflight=True,
    ):
        chunks.append(chunk)

    assert captured["skip_metering_preflight"] is True
    assert len(chunks) == 1
    assert chunks[0].delta == "ok"


@pytest.mark.asyncio
async def test_stream_llm_chunks_forwards_extra_kwargs(
    monkeypatch,
) -> None:
    from app.ai.engine import conversation_runtime_bridge as bridge

    captured: dict[str, object] = {}

    async def fake_prepare_stream_runtime(
        engine,
        *,
        agent,
        messages,
        tenant_id,
        route_result=None,
        skip_metering_preflight=False,
    ):
        _ = engine, agent, messages, tenant_id, route_result, skip_metering_preflight
        provider = SimpleNamespace(code="mock-provider", type="mock")
        return SimpleNamespace(
            provider=provider,
            model_code="mock-model",
            ai_model=SimpleNamespace(supports_streaming=True),
            runtime_info={"model_id": 3},
        )

    async def fake_build_runtime_stream_entrypoint_plan(
        engine,
        *,
        runtime_preparer,
        extra_kwargs=None,
        **kwargs,
    ):
        runtime_context = await runtime_preparer(
            engine,
            agent=kwargs["agent"],
            messages=kwargs["messages"],
            tenant_id=kwargs["tenant_id"],
            route_result=kwargs["route_result"],
            skip_metering_preflight=kwargs["skip_metering_preflight"],
        )
        captured["extra_kwargs"] = extra_kwargs

        class _Accounting:
            async def finalize_success(self, **kwargs):
                _ = kwargs
                return None

            async def log_failure(self, **kwargs):
                _ = kwargs
                return None

        return SimpleNamespace(
            runtime_context=runtime_context,
            query_engine=SimpleNamespace(turn_record={}),
            accounting=_Accounting(),
            request_context=SimpleNamespace(),
            audit_context=SimpleNamespace(),
            request_extra_kwargs=extra_kwargs or {},
        )

    async def fake_iterate_runtime_stream_entrypoint(
        *,
        plan,
        agent,
        selected_skill_names,
    ):
        _ = plan, agent, selected_skill_names
        captured["plan_extra_kwargs"] = plan.request_extra_kwargs
        yield ChatChunk(delta="ok", finish_reason="stop", total_tokens=1)

    monkeypatch.setattr(bridge, "prepare_stream_runtime", fake_prepare_stream_runtime)
    monkeypatch.setattr(
        bridge,
        "build_runtime_stream_entrypoint_plan",
        fake_build_runtime_stream_entrypoint_plan,
    )
    monkeypatch.setattr(
        bridge,
        "iterate_runtime_stream_entrypoint",
        fake_iterate_runtime_stream_entrypoint,
    )

    engine = SimpleNamespace(
        logger=None,
        gateway=SimpleNamespace(),
        db=SimpleNamespace(),
    )
    extra_kwargs = {
        "_runtime_reasoning_effort_override": "low",
        "trace_id": "trace-1",
    }
    chunks = []
    async for chunk in bridge.stream_llm_chunks(
        engine,
        agent=SimpleNamespace(id=1),
        messages=[ChatMessage(role="user", content="hi")],
        tenant_id=1,
        conversation_id=2,
        tools=None,
        extra_kwargs=extra_kwargs,
    ):
        chunks.append(chunk)

    assert captured["extra_kwargs"] == extra_kwargs
    assert captured["plan_extra_kwargs"] == extra_kwargs
    assert len(chunks) == 1
    assert chunks[0].delta == "ok"
