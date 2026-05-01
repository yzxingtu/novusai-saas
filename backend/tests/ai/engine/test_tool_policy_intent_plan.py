"""
Test type: behavioral
Scope: tool-policy intent projection with invalid runtime hints absent.
Mock strategy: focused monkeypatch only blocks planner recomputation; assertions
cover real helper behavior for ordinary intents and invalid runtime hints.
"""

from __future__ import annotations

import pytest

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.tool_policy_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def _intent_payload(
    *,
    intent_id: str,
    kind: str,
    family: str,
    order: int,
    label: str,
    source_text: str,
    requires_tools: bool = True,
    metadata: dict | None = None,
) -> dict:
    return {
        "intent_id": intent_id,
        "kind": kind,
        "family": family,
        "order": order,
        "user_visible_label": label,
        "source_text": source_text,
        "requires_tools": requires_tools,
        "metadata": dict(metadata or {}),
    }


def test_detect_requested_turn_intents_prefers_precomputed_ordinary_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_plan": [
            _intent_payload(
                intent_id="intent-1",
                kind="weather_query",
                family="weather",
                order=1,
                label="weather",
                source_text="weather",
            ),
            _intent_payload(
                intent_id="intent-2",
                kind="web_research",
                family="web_research",
                order=2,
                label="rail_search",
                source_text="rail",
            ),
        ]
    }

    intents = detect_requested_turn_intents(
        "Check the weather and rail tickets",
        tools=[ToolDefinition(name="web_search")],
        input_variables=input_variables,
    )
    assert intents == ["weather", "rail_ticket_research"]


def test_invalid_runtime_intent_plan_does_not_reactivate_current_page_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_plan": [
            _intent_payload(
                intent_id="intent-1",
                kind="data_workflow",
                family="data_ops",
                order=1,
                label="data_workflow",
                source_text="page",
                metadata={
                    "data_workflow_kind": "data_workflow",
                    "data_workflow_goal": "record_summary",
                },
            )
        ],
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "data_workflow"],
            "active_intent_kind": "data_workflow",
            "data_workflow_goal": "navigation",
        },
    }

    assert (
        detect_requested_turn_intents(
            "Check the weather and summarize the page",
            tools=[ToolDefinition(name="crm_lookup")],
            input_variables=input_variables,
        )
        == []
    )


def test_collect_completed_turn_intents_ignores_invalid_runtime_tool_results() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "crm_lookup", "arguments": "{}"},
                }
            ],
        ),
        ChatMessage(
            role="tool",
            content='{"title":"invalid runtime"}',
            name="crm_lookup",
            tool_call_id="call-1",
            metadata={"success": True},
        ),
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[ToolDefinition(name="crm_lookup")],
        input_variables={
            "_runtime_intent_facts": {
                "requested_intents": ["data_workflow"],
                "data_workflow_goal": "record_summary",
            }
        },
    )

    assert "data_workflow" not in completed
