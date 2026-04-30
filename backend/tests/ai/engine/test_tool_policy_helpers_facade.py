from __future__ import annotations

from app.ai.engine import (
    tool_policy_helpers as facade,
)
from app.ai.engine import (
    tool_policy_semantics,
    tool_policy_trust_helpers,
)
from app.ai.engine.tool_policy_helpers import (
    apply_execution_trust_policy,
    messages_have_blocking_pending_interaction,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


def test_tool_policy_helpers_facade_exports() -> None:
    assert facade.tool_semantic_family is tool_policy_semantics.tool_semantic_family
    assert facade.first_page_intent_kind() is None
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


def test_apply_execution_trust_policy_trusted_auto_allows_readonly() -> None:
    tools = [ToolDefinition(name="web_search")]

    updated = apply_execution_trust_policy(
        tools=tools,
        input_variables=None,
        tool_consent_modes={"web_search": "ask"},
        trust_policy_ref=None,
        interaction_mode="trusted_auto",
    )

    assert updated["web_search"] == "auto"


def test_apply_execution_trust_policy_defaults_to_trusted_auto() -> None:
    tools = [ToolDefinition(name="web_search")]

    updated = apply_execution_trust_policy(
        tools=tools,
        input_variables=None,
        tool_consent_modes={"web_search": "ask"},
        trust_policy_ref=None,
    )

    assert updated["web_search"] == "auto"
