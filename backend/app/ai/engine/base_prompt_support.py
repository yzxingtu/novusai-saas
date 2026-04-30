"""
Prompt/runtime helper facade bindings for BaseEngine.
"""

from __future__ import annotations

from .base_helpers import (
    build_user_message,
    messages_to_dicts,
    parse_tool_arguments,
    stable_unique_text_list,
    tool_call_name,
    tool_call_operation_name,
    truncate_preview,
    keep_tool_calls_for_round,
)
from .base_prompt_contract_support import BasePromptContractSupportMixin
from .base_prompt_llm_support import BasePromptLLMSupportMixin
from .base_prompt_research_support import BasePromptResearchSupportMixin
from .base_prompt_system_support import BasePromptSystemSupportMixin
from .base_prompt_tool_policy_support import BasePromptToolPolicySupportMixin


class BaseEnginePromptSupport(
    BasePromptSystemSupportMixin,
    BasePromptToolPolicySupportMixin,
    BasePromptResearchSupportMixin,
    BasePromptContractSupportMixin,
    BasePromptLLMSupportMixin,
):
    """Facade that preserves the historic BaseEngine prompt helper surface."""

    _user_message = staticmethod(build_user_message)
    _parse_tool_arguments = staticmethod(parse_tool_arguments)
    _tool_call_operation_name = staticmethod(tool_call_operation_name)
    _tool_call_name = staticmethod(tool_call_name)
    _keep_tool_calls_for_round = staticmethod(keep_tool_calls_for_round)
    _truncate_preview = staticmethod(truncate_preview)
    _stable_unique_text_list = staticmethod(stable_unique_text_list)
    _messages_to_dicts = staticmethod(messages_to_dicts)


__all__ = ["BaseEnginePromptSupport"]
