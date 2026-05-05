from __future__ import annotations

from app.ai.context.assembly_initial_support import (
    resolve_knowledge_base_selection,
)
from app.ai.types import ChatMessage


class _PromptBridgeStub:
    @staticmethod
    def _build_system_message(agent, input_variables=None):
        _ = input_variables
        return ChatMessage(role="system", content=f"system:{agent.id}")


def test_resolve_knowledge_base_selection_merges_and_drops() -> None:
    selection = resolve_knowledge_base_selection(
        request_kb_ids=[3, 5, 8],
        agent_kb_ids=[1, 5, 9],
        agent_kb_weights={1: 0.3, 5: 0.7, 9: 1.0},
    )

    assert selection.requested_kb_ids == [3, 5, 8]
    assert selection.merged_kb_ids == [5]
    assert selection.dropped_kb_ids == [3, 8]
    assert selection.agent_kb_weights == {1: 0.3, 5: 0.7, 9: 1.0}


def test_resolve_knowledge_base_selection_falls_back_to_agent_when_no_overlap() -> None:
    selection = resolve_knowledge_base_selection(
        request_kb_ids=[77],
        agent_kb_ids=[10, 11],
        agent_kb_weights={10: 1.0, 11: 0.5},
    )

    assert selection.requested_kb_ids == [77]
    assert selection.merged_kb_ids == [10, 11]
    assert selection.dropped_kb_ids == [77]
