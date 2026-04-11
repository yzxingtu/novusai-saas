from __future__ import annotations

from app.ai.engine.tool_execution_helpers import (
    normalize_tool_call_outcome,
    register_tool_failures,
    synthesize_tool_results_from_calls,
)
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse


class _StateRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def register_provider_failure(self, *, kind: str, event: dict) -> None:
        self.events.append((kind, event))


def test_normalize_tool_call_outcome_supports_three_item_shape() -> None:
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="hello"),
        total_tokens=7,
        output_tokens=5,
    )
    normalized = normalize_tool_call_outcome((response, [], 7))
    assert normalized[0] is response
    assert normalized[2] == 7
    assert normalized[3] == 5


def test_synthesize_tool_results_skips_unresolved_interactions_when_configured() -> None:
    tool_calls = [
        {
            "id": "call-1",
            "function": {"name": "fetch_url", "arguments": "{}"},
            "pending_consent": {"resolved": False},
        },
        {
            "id": "call-2",
            "function": {"name": "web_search", "arguments": "{}"},
            "pending_consent": {"resolved": True},
        },
    ]
    synthesized = synthesize_tool_results_from_calls(
        tool_calls,
        skip_unresolved_interactions=True,
    )
    assert [item.name for item in synthesized] == ["web_search"]


def test_register_tool_failures_records_timeout_failure_event() -> None:
    state = _StateRecorder()
    register_tool_failures(
        state,
        [
            ToolResult(
                tool_call_id="tool-1",
                name="fetch_url",
                success=False,
                error="timeout",
                error_type="timeout",
            )
        ],
    )
    assert state.events
    assert state.events[0][0] == "tool_timeout"
