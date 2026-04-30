"""
Test type: behavioral
Scope: tool-policy intent projection after page-awareness retirement.
Mock strategy: focused monkeypatch only blocks planner recomputation; assertions
cover real helper behavior for non-page intents and retired page hints.
"""

from __future__ import annotations

import pytest

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.tool_policy_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
    first_page_intent_kind,
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


def test_detect_requested_turn_intents_prefers_precomputed_non_page_plan(
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


def test_page_intent_helpers_do_not_reactivate_retired_page_awareness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_plan": [
            _intent_payload(
                intent_id="intent-1",
                kind="page_workflow",
                family="page_ops",
                order=1,
                label="page_workflow",
                source_text="page",
                metadata={
                    "page_workflow_kind": "page_workflow",
                    "page_workflow_goal": "page_summary",
                },
            )
        ],
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "page_workflow"],
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "navigation",
        },
    }

    assert (
        first_page_intent_kind(
            user_text="Summarize the current page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        is None
    )
    assert (
        detect_requested_turn_intents(
            "Check the weather and summarize the page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        == []
    )


def test_collect_completed_turn_intents_ignores_retired_page_tool_results() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "ui_get_snapshot", "arguments": "{}"},
                }
            ],
        ),
        ChatMessage(
            role="tool",
            content='{"title":"legacy page"}',
            name="ui_get_snapshot",
            tool_call_id="call-1",
            metadata={"success": True},
        ),
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[ToolDefinition(name="ui_get_snapshot")],
        input_variables={
            "_runtime_intent_facts": {
                "requested_intents": ["page_workflow"],
                "page_workflow_goal": "page_summary",
            }
        },
    )

    assert "page_workflow" not in completed
