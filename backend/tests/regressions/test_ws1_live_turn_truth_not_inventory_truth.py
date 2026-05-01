"""
Test type: behavioral
Regression for: BUG-2026-04-27-WS1-PKG-03
Original symptom: when live `selected_tool_names` / `selected_skill_names` were
explicitly empty, retained projection fallback still widened the turn back to
broader inventory names from `turn_record.metadata.turn_diagnostics`.
Scope: WS1-PKG-03 live-turn truth must beat retained inventory fallback in the
real runtime projection path.
Real dependencies: a fresh Python interpreter imports the real projector and
turn-projection modules from the backend root and executes the retained
projection path end to end.
Mocked dependencies: none.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _run_projection_probe() -> dict[str, object]:
    script = textwrap.dedent(
        """
        import json
        from app.ai.engine.types import ExecutionResult
        from app.services.ai.agent_chat_turn_projection import (
            build_context_diagnostics,
            build_last_run_summary,
        )
        from app.services.ai.conversation_diagnostics_projector import (
            ConversationDiagnosticsProjector,
        )
        from app.services.ai.monitoring_read_model_projector import (
            MonitoringReadModelProjector,
        )

        metadata = {
            "turn_record": {
                "selected_tool_names": [],
                "selected_skill_names": [],
                "turn_outcome": "failed",
                "termination_reason": "tool_round_failed",
                "metadata": {
                    "turn_diagnostics": {
                        "turn_outcome": "failed",
                        "selected_tool_names": ["ui_get_snapshot", "web_search"],
                        "selected_skill_names": ["page_awareness", "Research Skill"],
                        "turn_skill_activation": {
                            "applied": True,
                            "reason": "runtime_policy",
                            "selected_tool_names": [],
                            "selected_skill_names": [],
                            "inventory_selected_tool_names": [
                                "ui_get_snapshot",
                                "web_search",
                            ],
                            "inventory_selected_skill_names": [
                                "page_awareness",
                                "Research Skill",
                            ],
                        },
                    }
                },
            },
            "context_diagnostics": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["page_awareness", "Research Skill"],
            },
            "last_run_summary": {
                "selected_tool_names": ["ui_get_snapshot", "web_search"],
                "selected_skill_names": ["page_awareness", "Research Skill"],
            },
        }
        request_metadata = {
            "turn_diagnostics": metadata,
            "request": {"turn_record": metadata["turn_record"]},
        }

        result = ExecutionResult(
            success=False,
            output="upstream failure",
            messages=[],
            tool_results=[],
            total_tokens=17,
            duration_ms=31,
            error="tool_round_failed",
            completion_reason="tool_round_failed",
            turn_record=metadata["turn_record"],
        )

        payload = {
            "turn_meta": (
                ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                    metadata
                )
            ),
            "context_payload": build_context_diagnostics(
                result,
                interaction_mode_effective="trusted_auto",
            ),
            "summary_payload": build_last_run_summary(
                result,
                interaction_mode_effective="trusted_auto",
                downgrade_reason=None,
            ),
            "monitoring_payload": (
                MonitoringReadModelProjector.extract_call_trace_diagnostics(
                    request_metadata
                )
            ),
        }
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_retained_projection_does_not_leak_inventory_when_live_selection_is_empty() -> (
    None
):
    payload = _run_projection_probe()

    assert payload["turn_meta"]["selected_tool_names"] == []
    assert payload["turn_meta"]["selected_skill_names"] == []
    assert payload["turn_meta"]["turn_skill_activation"] == {
        "applied": True,
        "reason": "runtime_policy",
        "tool_count": 0,
        "selected_tool_names": [],
        "skill_count": 0,
        "selected_skill_names": [],
        "inventory_tool_count": 1,
        "inventory_selected_tool_names": ["web_search"],
        "inventory_skill_count": 1,
        "inventory_selected_skill_names": ["Research Skill"],
    }
    assert "selected_tool_names" not in payload["context_payload"]
    assert "selected_skill_names" not in payload["context_payload"]
    assert payload["context_payload"]["turn_skill_activation"] == {
        "applied": True,
        "reason": "runtime_policy",
        "tool_count": 0,
        "selected_tool_names": [],
        "skill_count": 0,
        "selected_skill_names": [],
        "inventory_tool_count": 1,
        "inventory_selected_tool_names": ["web_search"],
        "inventory_skill_count": 1,
        "inventory_selected_skill_names": ["Research Skill"],
    }
    assert "selected_tool_names" not in payload["summary_payload"]
    assert "selected_skill_names" not in payload["summary_payload"]
    assert payload["summary_payload"]["turn_skill_activation"] == {
        "applied": True,
        "reason": "runtime_policy",
        "tool_count": 0,
        "selected_tool_names": [],
        "skill_count": 0,
        "selected_skill_names": [],
        "inventory_tool_count": 1,
        "inventory_selected_tool_names": ["web_search"],
        "inventory_skill_count": 1,
        "inventory_selected_skill_names": ["Research Skill"],
    }
    assert payload["monitoring_payload"]["selected_tool_names"] == []
    assert payload["monitoring_payload"]["selected_skill_names"] == []
    assert payload["monitoring_payload"]["turn_record"]["metadata"][
        "turn_diagnostics"
    ]["selected_tool_names"] == ["web_search"]
    assert payload["monitoring_payload"]["turn_record"]["metadata"][
        "turn_diagnostics"
    ]["selected_skill_names"] == ["Research Skill"]
