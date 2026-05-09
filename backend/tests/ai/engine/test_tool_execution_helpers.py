"""Test type: behavioral.

中文: 覆盖工具执行缺失结果时的 fail-close 行为。
EN: Covers fail-closed behavior when tool execution returns no result.
"""

from __future__ import annotations

from app.ai.engine.tool_execution_helpers import (
    normalize_tool_call_outcome,
    synthesize_tool_results_from_calls,
)
from app.ai.types import ChatMessage, ChatResponse


def test_synthesized_missing_tool_result_is_failed_not_successful() -> None:
    results = synthesize_tool_results_from_calls(
        [
            {
                "id": "call_1",
                "function": {"name": "crm_lookup"},
            }
        ],
    )

    assert len(results) == 1
    assert results[0].tool_call_id == "call_1"
    assert results[0].name == "crm_lookup"
    assert results[0].success is False
    assert results[0].error_type == "missing_tool_result"
    assert results[0].error == "Tool execution did not return a result."


def test_three_item_tool_call_outcome_uses_response_output_tokens() -> None:
    response = ChatResponse(
        message=ChatMessage(role="assistant", content="done"),
        output_tokens=7,
    )

    normalized_response, tool_results, total_tokens, completion_tokens_used = (
        normalize_tool_call_outcome((response, [], 13))
    )

    assert normalized_response is response
    assert tool_results == []
    assert total_tokens == 13
    assert completion_tokens_used == 7
