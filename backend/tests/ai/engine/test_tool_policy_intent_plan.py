"""
Test type: behavioral
Scope: tool-policy intent projection and canonical page_workflow runtime facts
Mock strategy: intent planner may be blocked in focused fallback tests, but page
intent canonicalization and completion tracking run through the real helpers.
"""

from __future__ import annotations

import pytest

from app.ai.engine.intent_planner import IntentPlanner
from app.ai.engine.tool_policy_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
    first_page_intent_kind,
)
from app.ai.engine.tool_policy_page_helpers import first_page_workflow_goal
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
        ]
    }

    assert (
        first_page_intent_kind(
            user_text="Summarize the current page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        == "page_workflow"
    )


def test_detect_requested_turn_intents_uses_runtime_intent_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "page_workflow"],
            "page_workflow_goal": "page_summary",
        }
    }

    intents = detect_requested_turn_intents(
        "Check the weather and summarize the page",
        tools=[ToolDefinition(name="ui_get_snapshot")],
        input_variables=input_variables,
    )
    assert intents == ["weather", "page_workflow"]


def test_detect_requested_turn_intents_prefers_active_page_intent_over_stale_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "page_workflow"],
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "navigation",
        }
    }

    intents = detect_requested_turn_intents(
        "先查天气，再去供应商页面",
        tools=[ToolDefinition(name="ui_open_surface")],
        input_variables=input_variables,
    )

    assert intents == ["weather", "page_workflow"]


def test_detect_requested_turn_intents_uses_canonical_page_workflow_runtime_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "requested_intents": ["weather", "page_summary"],
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "navigation",
        }
    }

    intents = detect_requested_turn_intents(
        "先查天气，再去供应商页面",
        tools=[ToolDefinition(name="ui_open_surface")],
        input_variables=input_variables,
    )

    assert intents == ["weather", "page_workflow"]


def test_first_page_intent_kind_uses_runtime_intent_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "row_detail",
        }
    }

    assert (
        first_page_intent_kind(
            user_text="Summarize the current page",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables=input_variables,
        )
        == "page_workflow"
    )


def test_first_page_intent_kind_uses_canonical_page_workflow_runtime_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "row_detail",
        }
    }

    assert (
        first_page_intent_kind(
            user_text="点开这条记录看看",
            tools=[ToolDefinition(name="ui_read_region")],
            input_variables=input_variables,
        )
        == "page_workflow"
    )


def test_first_page_workflow_goal_preserves_canonical_page_summary_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_plan_turn(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("IntentPlanner.plan_turn should not be called")

    monkeypatch.setattr(IntentPlanner, "plan_turn", _fail_plan_turn)

    input_variables = {
        "_runtime_intent_facts": {
            "active_intent_kind": "page_workflow",
            "page_workflow_goal": "page_summary",
        }
    }

    assert (
        first_page_workflow_goal(
            user_text="列出这个表格前5条标题和时间",
            tools=[ToolDefinition(name="ui_read_table")],
            input_variables=input_variables,
        )
        == "page_summary"
    )


def test_first_page_intent_kind_does_not_infer_from_colloquial_page_question() -> (
    None
):
    assert (
        first_page_intent_kind(
            user_text="这里都有啥？",
            tools=[ToolDefinition(name="ui_get_snapshot")],
            input_variables={"page_context": {"page_key": "admin.ai.logs", "ui_epoch": 1}},
        )
        is None
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


def test_collect_completed_turn_intents_uses_active_page_intent_over_stale_summary() -> (
    None
):
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "ui_get_snapshot",
                        "arguments": {},
                    },
                    "success": True,
                }
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables={
            "_runtime_intent_facts": {
                "requested_intents": ["page_workflow"],
                "active_intent_kind": "page_workflow",
                "page_workflow_goal": "navigation",
            }
        },
    )

    assert "page_workflow" not in completed


def test_collect_completed_turn_intents_keeps_navigation_pending_until_action_and_verify() -> (
    None
):
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "ui_get_snapshot",
                        "arguments": {},
                    },
                    "success": True,
                }
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables={
            "_runtime_intent_plan": [
                {
                    **_intent_payload(
                        intent_id="intent-1",
                        kind="page_workflow",
                        family="page_ops",
                        order=1,
                        label="page_workflow",
                        source_text="添加供应商",
                    ),
                    "metadata": {
                        "page_workflow_kind": "page_workflow",
                        "page_workflow_goal": "navigation",
                        "page_workflow_stage": "discover_navigation_target",
                    },
                }
            ]
        },
    )

    assert "page_workflow" not in completed


def test_collect_completed_turn_intents_marks_navigation_complete_after_click_and_verify() -> (
    None
):
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "ui_click",
                        "arguments": {"target_locator": "添加供应商"},
                    },
                    "success": True,
                },
                {
                    "function": {
                        "name": "ui_get_snapshot",
                        "arguments": {},
                    },
                    "success": True,
                },
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables={
            "_runtime_intent_plan": [
                {
                    **_intent_payload(
                        intent_id="intent-1",
                        kind="page_workflow",
                        family="page_ops",
                        order=1,
                        label="page_workflow",
                        source_text="添加供应商",
                    ),
                    "metadata": {
                        "page_workflow_kind": "page_workflow",
                        "page_workflow_goal": "navigation",
                        "page_workflow_stage": "discover_navigation_target",
                    },
                }
            ]
        },
    )

    assert "page_workflow" in completed


def test_collect_completed_turn_intents_prefers_explicit_page_progress_over_snapshot_match() -> (
    None
):
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "function": {
                        "name": "ui_get_snapshot",
                        "arguments": {},
                    },
                    "success": True,
                }
            ],
        )
    ]

    completed = collect_completed_turn_intents(
        messages,
        tools=[],
        input_variables={
            "_runtime_intent_plan": [
                {
                    **_intent_payload(
                        intent_id="intent-1",
                        kind="page_workflow",
                        family="page_ops",
                        order=1,
                        label="page_workflow",
                        source_text="打开供应商页面",
                    ),
                    "metadata": {
                        "page_workflow_stage": "verify_navigation_result",
                        "page_workflow_phase": "verify",
                        "page_workflow_goal": "navigation",
                        "page_workflow_progress": {
                            "status": "verify_pending",
                            "continuation_required": True,
                        },
                    },
                }
            ]
        },
    )

    assert "page_workflow" not in completed


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
