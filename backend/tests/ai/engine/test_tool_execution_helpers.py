from __future__ import annotations

from app.ai.engine.tool_execution_helpers import (
    normalize_tool_call_outcome,
)
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
