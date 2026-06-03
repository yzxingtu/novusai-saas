"""Test type: behavioral
Scope: extracted diagnostics support seam and invalid runtime metadata scrubbing.
Real dependencies: diagnostics extraction helpers.
Mocked dependencies: none.
"""

from __future__ import annotations

from app.services.ai.conversation_diagnostics_projector_support import (
    extract_turn_diagnostics_from_metadata,
)


def test_extract_turn_diagnostics_projects_compact_runtime_decision_fields() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "metadata": {
                    "turn_diagnostics": {
                        "path_decision": {
                            "path": "normal",
                            "reason": "bounded_multi_intent",
                            "all_shortcircuit": False,
                            "intent_count": 1,
                        },
                        "capability_injection_decision": {
                            "skills_injected": False,
                            "kb_injected": False,
                            "memory_injected": False,
                            "bypass_reason": None,
                        },
                        "routing": {
                            "tool_filtering": {
                                "all_tools_count": 15,
                                "candidate_tools_count": 3,
                                "filtering_reason": "intent_scoped",
                            }
                        },
                        "recovery_chain": [],
                    }
                }
            }
        }
    )

    assert payload["path_decision"] == {
        "path": "normal",
        "reason": "bounded_multi_intent",
        "all_shortcircuit": False,
        "intent_count": 1,
    }
    assert payload["capability_injection"] == {
        "skills_injected": False,
        "kb_injected": False,
        "memory_injected": False,
        "bypass_reason": None,
    }
    assert payload["tool_filtering"] == {
        "all_tools_count": 15,
        "candidate_tools_count": 3,
        "filtering_reason": "intent_scoped",
    }
    assert payload["recovery_chain"] == []


def test_extract_turn_diagnostics_derives_elapsed_budget_exit_from_usage() -> None:
    payload = extract_turn_diagnostics_from_metadata(
        {
            "turn_record": {
                "turn_outcome": "success",
                "termination_reason": "completed",
                "budget": {
                    "status": "ok",
                    "limits": {"max_elapsed_ms": 60000},
                    "usage": {"elapsed_ms_used": 135500},
                },
            }
        }
    )

    assert payload["budget_status"] == "exited"
    assert payload["budget_exit_reason"] == "elapsed_budget_exceeded"
    assert payload["budget"]["usage"]["elapsed_over_limit"] is True
    assert payload["budget"]["usage"]["elapsed_over_limit_ms"] == 75500


def test_extract_turn_diagnostics_does_not_backfill_turn_flow_from_legacy_metadata() -> (
    None
):
    metadata = {
        "thinking_content": "raw reasoning must not create a public stage",
        "rag_sources": [
            {
                "source": "KB",
                "chunk_id": "legacy-kb",
                "title": "Legacy KB",
            }
        ],
    }

    payload = extract_turn_diagnostics_from_metadata(metadata)

    assert "turn_flow" not in metadata
    assert "turn_flow" not in payload
