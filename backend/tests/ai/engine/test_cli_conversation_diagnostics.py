from __future__ import annotations

from app.ai.engine.execution_state_machine import ExecutionStateMachine
from app.ai.engine.types import (
    ExecutionBudget,
    IntentPlan,
    PreparedExecution,
    RecoveryDecision,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.cli import (
    _build_ai_conversation_compact_diagnostics,
    _extract_turn_diagnostics_from_call_log_metadata,
    _render_ai_conversation_diagnostics_text,
)


def test_extract_turn_diagnostics_from_call_log_metadata_reads_extended_fields() -> None:
    top_level_diagnostics = {
        "execution_path": "deep",
        "intent_plan": [
            {
                "intent_id": "intent-1",
                "kind": "weather_query",
                "family": "weather",
                "order": 1,
                "user_visible_label": "weather",
                "status": "completed",
                "allowed_tool_names": ["get_current_weather"],
            },
            {
                "intent_id": "intent-3",
                "kind": "page_read",
                "family": "page_ops",
                "order": 3,
                "user_visible_label": "page_read",
                "status": "pending",
                "allowed_tool_names": ["get_page_context"],
            },
        ],
        "budget": {
            "status": "exited",
            "exit_reason": "tool_round_budget_exceeded",
            "limits": {"max_tool_rounds": 3},
            "usage": {"tool_rounds_used": 4},
        },
        "routing": {
            "candidate_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
                "get_page_context",
            ]
        },
        "recovery": {
            "retry_events": [
                {
                    "action": "retry_intent",
                    "target_intent_id": "intent-3",
                    "retry_family": "page_ops",
                    "allowed_tool_names": ["get_page_context"],
                    "completed_intent_ids": ["intent-1", "intent-2"],
                    "unfinished_intent_ids": ["intent-3"],
                    "reason": "unfinished_intent_retry",
                }
            ],
            "partial_exit_reason": "retry_budget_exhausted",
        },
        "failures": {
            "failure_kind": "provider_http_5xx",
            "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
        },
        "contract_breach_type": "unfinished_multi_intent_reply",
        "tool_leak_detected": True,
        "unfinished_intents": ["intent-3"],
        "recovered_via_retry": False,
    }
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                **top_level_diagnostics,
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "elapsed_budget_exceeded",
                    "protocol_path": "responses",
                    "selected_tool_names": ["get_current_weather", "web_search"],
                    "selected_skill_names": ["runtime.page_context"],
                    "context_sources": [
                        {"kind": "page_context", "name": "admin.ai.dashboard"}
                    ],
                    "last_tool_name": "get_page_context",
                    "last_page_key": "admin.ai.dashboard",
                    "last_page_op": "read",
                    "interrupted_stage": "tool_loop",
                    "tool_loop_progress": {"current_round": 2, "total_rounds": 3},
                    "metadata": {
                        "contract_breach_type": "unfinished_multi_intent_reply",
                        "tool_leak_detected": True,
                        "unfinished_intents": ["intent-3"],
                        "leaked_tool_names": ["web_search"],
                        "recovered_via_retry": False,
                        "turn_diagnostics": top_level_diagnostics,
                    },
                },
            }
        }
    )

    assert diagnostics["execution_path"] == "deep"
    assert diagnostics["intent_plan"][1]["intent_id"] == "intent-3"
    assert diagnostics["budget_status"] == "exited"
    assert diagnostics["budget_exit_reason"] == "tool_round_budget_exceeded"
    assert diagnostics["candidate_tool_names"] == [
        "get_current_weather",
        "web_search",
        "fetch_url",
        "get_page_context",
    ]
    assert diagnostics["retry_events"][0]["retry_family"] == "page_ops"
    assert diagnostics["partial_exit_reason"] == "retry_budget_exhausted"
    assert diagnostics["failure_kind"] == "provider_http_5xx"
    assert diagnostics["provider_events"] == [
        {"kind": "provider_http_5xx", "status_code": 503}
    ]
    assert diagnostics["contract_breach_type"] == "unfinished_multi_intent_reply"
    assert diagnostics["tool_leak_detected"] is True
    assert diagnostics["unfinished_intents"] == ["intent-3"]
    assert diagnostics["recovered_via_retry"] is False
    assert diagnostics["last_tool_name"] == "get_page_context"
    assert diagnostics["tool_loop_progress"] == {"current_round": 2, "total_rounds": 3}


def test_cli_compact_diagnostics_builder_and_text_renderer_surface_key_orchestration_state() -> None:
    snapshot = {
        "conversation": {
            "id": 666,
            "tenant_id": 1,
            "agent_id": 99,
            "user_id": 7,
            "status": "active",
            "message_count": 12,
        },
        "diagnostics": {
            "source": "assistant_message",
            "turn_outcome": "partial",
            "termination_reason": "elapsed_budget_exceeded",
            "protocol_path": "responses",
            "execution_path": "deep",
            "selected_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
            ],
            "selected_skill_names": ["runtime.page_context"],
            "candidate_tool_names": [
                "get_current_weather",
                "web_search",
                "fetch_url",
                "get_page_context",
            ],
            "intent_plan": [
                {
                    "intent_id": "intent-1",
                    "kind": "weather_query",
                    "family": "weather",
                    "order": 1,
                    "user_visible_label": "weather",
                    "status": "completed",
                    "allowed_tool_names": ["get_current_weather"],
                },
                {
                    "intent_id": "intent-2",
                    "kind": "web_research",
                    "family": "web_research",
                    "order": 2,
                    "user_visible_label": "rail_search",
                    "status": "completed",
                    "allowed_tool_names": ["web_search", "fetch_url"],
                },
                {
                    "intent_id": "intent-3",
                    "kind": "page_read",
                    "family": "page_ops",
                    "order": 3,
                    "user_visible_label": "page_read",
                    "status": "pending",
                    "allowed_tool_names": ["get_page_context"],
                },
            ],
            "unfinished_intents": ["intent-3"],
            "retry_events": [
                {
                    "action": "retry_intent",
                    "target_intent_id": "intent-3",
                    "retry_family": "page_ops",
                    "allowed_tool_names": ["get_page_context"],
                    "completed_intent_ids": ["intent-1", "intent-2"],
                    "unfinished_intent_ids": ["intent-3"],
                    "reason": "unfinished_intent_retry",
                }
            ],
            "partial_exit_reason": "retry_budget_exhausted",
            "failure_kind": "provider_http_5xx",
            "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
            "budget": {
                "status": "exited",
                "exit_reason": "elapsed_budget_exceeded",
                "limits": {"max_elapsed_ms": 45000},
                "usage": {"elapsed_ms_used": 47000},
            },
            "budget_status": "exited",
            "budget_exit_reason": "elapsed_budget_exceeded",
            "contract_breach_type": "unfinished_multi_intent_reply",
            "tool_leak_detected": True,
            "recovered_via_retry": False,
            "last_tool_name": "get_page_context",
            "last_page_key": "admin.ai.dashboard",
            "last_page_op": "read",
            "interrupted_stage": "tool_loop",
        },
    }

    compact = _build_ai_conversation_compact_diagnostics(snapshot)
    text = _render_ai_conversation_diagnostics_text(snapshot)

    assert compact["conversation_id"] == 666
    assert compact["execution_path"] == "deep"
    assert compact["failure_kind"] == "provider_http_5xx"
    assert compact["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert compact["intent_plan"][2]["status"] == "pending"
    assert compact["retry_events"][0]["target_intent_id"] == "intent-3"
    assert compact["provider_events"] == [
        {"kind": "provider_http_5xx", "status_code": 503}
    ]
    assert "Conversation #666 diagnostics" in text
    assert "execution_path=deep" in text
    assert "unfinished_intents=intent-3" in text
    assert "provider_events=" in text
    assert "budget=" in text


def test_extract_turn_diagnostics_preserves_provider_failure_after_partial_progress() -> None:
    diagnostics = _extract_turn_diagnostics_from_call_log_metadata(
        {
            "turn_diagnostics": {
                "execution_path": "normal",
                "failures": {
                    "failure_kind": "provider_http_5xx",
                    "provider_events": [{"kind": "provider_http_5xx", "status_code": 503}],
                },
                "turn_record": {
                    "turn_outcome": "partial",
                    "termination_reason": "provider_failure_after_partial_progress",
                    "protocol_path": "responses",
                    "metadata": {},
                },
            }
        }
    )

    assert diagnostics["turn_outcome"] == "partial"
    assert (
        diagnostics["termination_reason"] == "provider_failure_after_partial_progress"
    )
    assert diagnostics["failure_kind"] == "provider_http_5xx"


def test_execution_state_machine_emits_canonical_turn_event_schema() -> None:
    budget = ExecutionBudget(
        max_prompt_tokens=4096,
        max_completion_tokens=1024,
        max_tool_rounds=4,
        max_elapsed_ms=120000,
        max_retry_per_intent=2,
        max_candidate_tools=4,
        max_tool_result_bytes=16384,
    )
    intent = IntentPlan(
        intent_id="intent-1",
        kind="time_query",
        family="time",
        order=1,
        user_visible_label="time",
        source_text="现在几点",
        shortcircuit=True,
        allowed_tool_names=["get_current_time"],
        completion_signals=["get_current_time"],
    )
    prep = PreparedExecution(
        intent_plan=[intent],
        execution_path="fast",
        execution_budget=budget,
        tools=[ToolDefinition(name="get_current_time")],
        all_tools=[
            ToolDefinition(name="get_current_time"),
            ToolDefinition(name="get_current_weather"),
            ToolDefinition(name="web_search"),
        ],
        diagnostics={
            "capability_injection_decision": {
                "skills_injected": False,
                "kb_injected": False,
                "memory_injected": False,
                "page_injected": False,
                "bypass_reason": "all_shortcircuit",
            }
        },
    )

    machine = ExecutionStateMachine.from_prepared_execution(prep)
    machine.register_completion_tokens(32)
    machine.register_tool_round()
    machine.register_tool_results(
        messages=[
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "success": True,
                        "function": {"name": "get_current_time"},
                    }
                ],
            )
        ],
        tool_results=[
            ToolResult(
                tool_call_id="call-1",
                name="get_current_time",
                success=True,
                output="现在是 14:30",
            )
        ],
    )
    machine.register_retry(
        RecoveryDecision(
            action="retry_intent",
            target_intent_id="intent-1",
            retry_family="time",
            allowed_tool_names=["get_current_time"],
            completed_intent_ids=["intent-1"],
            unfinished_intent_ids=[],
            reason="retry_for_validation",
        )
    )

    payload = machine.build_diagnostics_payload()

    assert payload["path_decision"] == {
        "path": "fast",
        "reason": "all_shortcircuit",
        "all_shortcircuit": True,
        "intent_count": 1,
    }
    assert payload["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "page_injected": False,
        "bypass_reason": "all_shortcircuit",
    }
    assert payload["tool_filtering"] == {
        "all_tools_count": 3,
        "candidate_tools_count": 1,
        "filtering_reason": "intent_scoped_shortcircuit",
    }
    assert payload["recovery_chain"][-1]["action"] == "retry_intent"
    assert payload["recovery_chain"][-1]["target_intent"] == "intent-1"
    event_kinds = {event["kind"] for event in payload["turn_events"]}
    assert {
        "turn.started",
        "turn.intent_planned",
        "turn.path_selected",
        "turn.capability_gated",
        "turn.tools_filtered",
        "turn.model_called",
        "turn.tool_round",
        "turn.tool_completed",
        "turn.recovery_decided",
        "turn.budget_checked",
    }.issubset(event_kinds)
    assert payload["candidate_tool_names"] == ["get_current_time"]
    for event in payload["turn_events"]:
        assert isinstance(event["timestamp_ms"], int)
        assert event["timestamp_ms"] >= 0
        assert isinstance(event["data"], dict)


def test_recoverable_failure_does_not_emit_terminal_failed_event_before_recovery() -> None:
    budget = ExecutionBudget(
        max_prompt_tokens=2048,
        max_completion_tokens=512,
        max_tool_rounds=3,
        max_elapsed_ms=60000,
        max_retry_per_intent=2,
        max_candidate_tools=3,
        max_tool_result_bytes=8192,
    )
    intent = IntentPlan(
        intent_id="intent-1",
        kind="weather_query",
        family="weather",
        order=1,
        user_visible_label="weather",
        source_text="今天天气",
        allowed_tool_names=["get_current_weather"],
    )
    machine = ExecutionStateMachine.from_prepared_execution(
        PreparedExecution(
            intent_plan=[intent],
            execution_path="normal",
            execution_budget=budget,
            tools=[ToolDefinition(name="get_current_weather")],
            all_tools=[
                ToolDefinition(name="get_current_weather"),
                ToolDefinition(name="web_search"),
            ],
        )
    )

    machine.register_provider_failure(
        kind="tool_timeout",
        event={"kind": "tool_timeout", "status_code": 504},
    )
    machine.register_retry(
        RecoveryDecision(
            action="retry_intent",
            target_intent_id="intent-1",
            retry_family="weather",
            allowed_tool_names=["get_current_weather"],
            completed_intent_ids=[],
            unfinished_intent_ids=["intent-1"],
            reason="unfinished_intent_retry",
            provider_failure_kind="tool_timeout",
        )
    )
    machine.transition("completed")

    payload = machine.build_diagnostics_payload()
    event_kinds = [event["kind"] for event in payload["turn_events"]]

    assert "turn.tool_failed" in event_kinds
    assert "turn.recovery_decided" in event_kinds
    assert "turn.completed" in event_kinds
    assert "turn.failed" not in event_kinds
    assert "turn.partial_exit" not in event_kinds
