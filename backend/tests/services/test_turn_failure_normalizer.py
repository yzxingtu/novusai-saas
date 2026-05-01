"""Test type: behavioral.

Verifies generic turn-failure normalization without invalid runtime workflow
compatibility paths.
"""

from __future__ import annotations

from app.services.ai.turn_failure_normalizer import (
    normalize_failure_termination_reason,
    resolve_failure_projection,
)


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
