"""Test type: behavioral.

Verifies page-workflow failure diagnostics prefer canonical page_workflow_*
metadata and only use bounded historical fallback for legacy page intent aliases
when canonical metadata is absent.
"""

from __future__ import annotations

from app.services.ai.turn_failure_normalizer import (
    extract_page_workflow_context,
    normalize_failure_termination_reason,
    resolve_failure_projection,
)


def test_extract_page_workflow_context_prefers_canonical_goal_over_legacy_kind() -> (
    None
):
    context = extract_page_workflow_context(
        {
            "tool_planner": {
                "family": "page_ops",
                "kind": "page_search",
                "metadata": {
                    "page_workflow_kind": "page_workflow",
                    "page_workflow_goal": "navigation",
                    "page_workflow_phase": "navigate_or_open",
                },
            }
        }
    )

    assert context["intent_kind"] == "page_workflow"
    assert "intent_kind_alias" not in context
    assert context["goal"] == "navigation"
    assert context["phase"] == "navigate_or_open"
    assert context["has_metadata"] is True


def test_extract_page_workflow_context_omits_alias_for_canonical_kind() -> None:
    context = extract_page_workflow_context(
        {
            "tool_planner": {
                "family": "page_ops",
                "kind": "page_workflow",
                "metadata": {
                    "page_workflow_kind": "page_workflow",
                    "page_workflow_goal": "search",
                },
            }
        }
    )

    assert context["intent_kind"] == "page_workflow"
    assert "intent_kind_alias" not in context
    assert context["goal"] == "search"
    assert context["has_metadata"] is True


def test_extract_page_workflow_context_normalizes_historical_goal_alias_in_metadata() -> (
    None
):
    context = extract_page_workflow_context(
        {
            "tool_planner": {
                "family": "page_ops",
                "metadata": {
                    "page_workflow_kind": "page_workflow",
                    "page_workflow_goal": "page_navigation",
                },
            }
        }
    )

    assert context["intent_kind"] == "page_workflow"
    assert context["goal"] == "navigation"
    assert context["has_metadata"] is True


def test_extract_page_workflow_context_uses_legacy_kind_only_without_metadata() -> (
    None
):
    context = extract_page_workflow_context(
        {
            "tool_planner": {
                "kind": "page_navigation",
            }
        }
    )

    assert context["intent_kind"] == "page_workflow"
    assert context["family"] == "page_ops"
    assert context["goal"] == "navigation"
    assert context["has_metadata"] is False


def test_extract_page_workflow_context_does_not_backfill_goal_from_legacy_kind_when_canonical_metadata_is_partial() -> (
    None
):
    context = extract_page_workflow_context(
        {
            "tool_planner": {
                "kind": "page_navigation",
                "metadata": {
                    "page_workflow_kind": "page_workflow",
                    "page_workflow_phase": "navigate_or_open",
                },
            }
        }
    )

    assert context["intent_kind"] == "page_workflow"
    assert context["goal"] is None
    assert context["phase"] == "navigate_or_open"
    assert context["has_metadata"] is True


def test_normalize_failure_termination_reason_prefers_timeout_over_interrupted_marker() -> (
    None
):
    reason = normalize_failure_termination_reason(
        termination_reason="interrupted",
        failure_kind="provider_timeout",
    )

    assert reason == "provider_timeout"


def test_resolve_failure_projection_preserves_provider_timeout_when_cancelled_after_timeout() -> (
    None
):
    projection = resolve_failure_projection(
        diagnostics={
            "termination_reason": "interrupted",
            "failure_kind": "provider_timeout",
            "turn_outcome": "partial",
        },
        turn_flow={
            "timeline": [
                {
                    "id": "terminal",
                    "type": "failed",
                    "status": "interrupted",
                }
            ]
        },
    )

    assert projection["turn_outcome"] == "partial"
    assert projection["termination_reason"] == "provider_timeout"
    assert projection["failure_kind"] == "provider_timeout"


def test_resolve_failure_projection_keeps_explicit_partial_when_turn_flow_failed_after_partial_progress() -> (
    None
):
    projection = resolve_failure_projection(
        diagnostics={
            "turn_outcome": "partial",
            "conversation_outcome": "failed",
            "termination_reason": "provider_error",
            "failure_kind": "provider_http_5xx",
        },
        turn_flow={
            "timeline": [
                {
                    "id": "failed",
                    "type": "failed",
                    "status": "error",
                }
            ],
            "error_surface": {
                "failure_kind": "provider_http_5xx",
            },
        },
    )

    assert projection["turn_outcome"] == "partial"
    assert projection["termination_reason"] == "provider_error"
    assert projection["failure_kind"] == "provider_http_5xx"


def test_resolve_failure_projection_still_promotes_failed_turn_flow_without_failed_conversation_outcome() -> (
    None
):
    projection = resolve_failure_projection(
        diagnostics={
            "turn_outcome": "partial",
            "termination_reason": "provider_failure_after_partial_progress",
            "failure_kind": "provider_http_5xx",
        },
        turn_flow={
            "timeline": [
                {
                    "id": "failed",
                    "type": "failed",
                    "status": "error",
                }
            ],
            "error_surface": {
                "failure_kind": "provider_http_5xx",
            },
        },
    )

    assert projection["turn_outcome"] == "failed"
    assert (
        projection["termination_reason"]
        == "provider_failure_after_partial_progress"
    )
    assert projection["failure_kind"] == "provider_http_5xx"


def test_resolve_failure_projection_keeps_partial_conversation_outcome_authoritative_over_successful_call_log_hint() -> (
    None
):
    projection = resolve_failure_projection(
        diagnostics={
            "turn_outcome": "success",
            "conversation_outcome": "partial",
            "selected_tool_names": ["web_search"],
            "unfinished_intents": ["web_research"],
        },
        turn_flow=None,
    )

    assert projection["turn_outcome"] == "partial"
    assert projection["has_failure_signal"] is True
