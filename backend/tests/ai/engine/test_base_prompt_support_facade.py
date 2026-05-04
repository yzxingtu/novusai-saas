"""
Test type: structural
Scope: base prompt support facade exports and mixin composition.
"""

from __future__ import annotations

import app.ai.engine.base_helpers as base_helpers
from app.ai.engine.base_prompt_contract_support import BasePromptContractSupportMixin
from app.ai.engine.base_prompt_llm_support import BasePromptLLMSupportMixin
from app.ai.engine.base_prompt_research_support import BasePromptResearchSupportMixin
from app.ai.engine.base_prompt_support import BaseEnginePromptSupport
from app.ai.engine.base_prompt_system_support import BasePromptSystemSupportMixin
from app.ai.engine.base_prompt_tool_policy_support import (
    BasePromptToolPolicySupportMixin,
)


def test_base_prompt_support_facade_composes_split_mixins() -> None:
    assert issubclass(BaseEnginePromptSupport, BasePromptSystemSupportMixin)
    assert issubclass(BaseEnginePromptSupport, BasePromptToolPolicySupportMixin)
    assert issubclass(BaseEnginePromptSupport, BasePromptResearchSupportMixin)
    assert issubclass(BaseEnginePromptSupport, BasePromptContractSupportMixin)
    assert issubclass(BaseEnginePromptSupport, BasePromptLLMSupportMixin)


def test_base_prompt_support_facade_keeps_stable_helper_surface() -> None:
    required_names = [
        "_build_system_message",
        "_inject_runtime_summary",
        "_prepare_llm_gateway_call",
        "_apply_llm_response_metadata",
        "_build_contract_recovery_system_message",
        "_merge_contract_diagnostics_into_turn_record",
        "_allowed_tool_names_for_family",
        "_build_web_research_continuation_context",
        "_apply_fetch_url_only_gate",
        "_messages_to_dicts",
    ]

    for attr_name in required_names:
        assert callable(getattr(BaseEnginePromptSupport, attr_name))


def test_base_prompt_support_facade_bindings_match_helpers() -> None:
    assert BaseEnginePromptSupport._user_message is base_helpers.build_user_message
    assert (
        BaseEnginePromptSupport._parse_tool_arguments
        is base_helpers.parse_tool_arguments
    )
    assert BaseEnginePromptSupport._tool_call_name is base_helpers.tool_call_name
    assert (
        BaseEnginePromptSupport._tool_call_operation_name
        is base_helpers.tool_call_operation_name
    )
    assert (
        BaseEnginePromptSupport._keep_tool_calls_for_round
        is base_helpers.keep_tool_calls_for_round
    )
    assert BaseEnginePromptSupport._truncate_preview is base_helpers.truncate_preview
    assert (
        BaseEnginePromptSupport._stable_unique_text_list
        is base_helpers.stable_unique_text_list
    )
    assert BaseEnginePromptSupport._messages_to_dicts is base_helpers.messages_to_dicts
