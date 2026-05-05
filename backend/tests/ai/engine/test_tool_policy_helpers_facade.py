"""
Test type: structural
Scope: tool policy helper facade exports after split-module refactors.
"""

from __future__ import annotations

from app.ai.engine import (
    tool_policy_helpers as facade,
)
from app.ai.engine import (
    tool_policy_semantics,
    tool_policy_trust_helpers,
)
from app.ai.engine.tool_policy_helpers import (
    messages_have_blocking_pending_interaction,
)
from app.ai.types import ChatMessage


def test_tool_policy_helpers_facade_exports() -> None:
    assert facade.tool_semantic_family is tool_policy_semantics.tool_semantic_family
    assert (
        facade.apply_execution_trust_policy
        is tool_policy_trust_helpers.apply_execution_trust_policy
    )


def test_messages_have_blocking_pending_interaction_detects_pending_consent() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{"pending_consent": {"resolved": False}}],
        )
    ]

    assert messages_have_blocking_pending_interaction(messages) is True
