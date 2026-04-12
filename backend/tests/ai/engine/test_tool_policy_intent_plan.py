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
) -> dict:
    return {
        "intent_id": intent_id,
        "kind": kind,
        "family": family,
        "order": order,
        "user_visible_label": label,
        "source_text": source_text,
        "requires_tools": requires_tools,
    }


def test_detect_requested_turn_intents_prefers_precomputed_plan(
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


def test_first_page_intent_kind_uses_precomputed_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_plan": [
            _intent_payload(
                intent_id="intent-1",
                kind="page_summary",
                family="page_ops",
                order=1,
                label="page_summary",
                source_text="page",
            )
        ]
    }

    assert (
        first_page_intent_kind(
            user_text="Summarize the current page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        == "page_summary"
    )


def test_detect_requested_turn_intents_uses_runtime_intent_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "page_summary"],
        }
    }

    intents = detect_requested_turn_intents(
        "Check the weather and summarize the page",
        tools=[ToolDefinition(name="ui_get_snapshot")],
        input_variables=input_variables,
    )
    assert intents == ["weather", "page_summary"]


def test_first_page_intent_kind_uses_runtime_intent_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {"active_intent_kind": "page_row_detail"}
    }

    assert (
        first_page_intent_kind(
            user_text="Summarize the current page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        == "page_row_detail"
    )


def test_collect_completed_turn_intents_tracks_rail_search_evidence() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "12306 高铁票 北京 上海"},
                    },
                    "success": True,
                }
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables=None,
    )

    assert "rail_ticket_research" in completed


def test_collect_completed_turn_intents_tracks_rail_fetch_evidence() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "fetch_url",
                        "arguments": {"url": "https://www.12306.cn/index/"},
                    },
                    "success": True,
                }
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables=None,
    )

    assert "rail_ticket_research" in completed


def test_collect_completed_turn_intents_tracks_search_and_fetch_evidence() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "高铁票 票价查询"},
                    },
                    "success": True,
                }
            ],
        ),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "fetch_url",
                        "arguments": {"url": "https://trains.example.com/search"},
                    },
                    "success": True,
                }
            ],
        ),
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables=None,
    )

    assert "rail_ticket_research" in completed
