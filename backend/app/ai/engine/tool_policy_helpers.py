"""Tool policy and semantic helpers extracted from BaseEngine."""

from __future__ import annotations

from .tool_policy_intent_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
)
from .tool_policy_message_helpers import (
    log_tool_selection_status,
    looks_like_generic_follow_up,
    messages_have_blocking_pending_interaction,
    response_has_native_web_search_evidence,
)
from .tool_policy_selection_helpers import (
    allowed_tool_names_for_families,
    allowed_tool_names_for_family,
    build_required_policy_for_family,
    ensure_explicit_family_coverage,
    ensure_web_research_tool_pair,
    filter_tools_for_policy,
    first_incomplete_requested_family,
    mark_multi_family_progress,
    ordered_requested_families_from_intents,
    restore_explicit_family_tools,
    restrict_tools_to_names,
)
from .tool_policy_semantics import (
    extract_textual_tool_call_names,
    family_capability_terms,
    looks_like_explicit_time_request,
    looks_like_explicit_web_research_request,
    looks_like_tool_planning_leak,
    response_denies_family_capability,
    tool_family_for_name,
    tool_semantic_family,
    tool_semantic_tags,
)
from .tool_policy_trust_helpers import apply_execution_trust_policy


def first_page_intent_kind(*args, **kwargs) -> None:
    del args, kwargs
    return None


def looks_like_generic_page_summary_request(*args, **kwargs) -> bool:
    del args, kwargs
    return False


def restrict_page_tools_for_generic_summary(
    *,
    selected_tools,
    all_tools,
    user_text,
    input_variables=None,
):
    del all_tools, user_text, input_variables
    return selected_tools, False

__all__ = [
    "allowed_tool_names_for_families",
    "allowed_tool_names_for_family",
    "apply_execution_trust_policy",
    "build_required_policy_for_family",
    "collect_completed_turn_intents",
    "detect_requested_turn_intents",
    "ensure_explicit_family_coverage",
    "ensure_web_research_tool_pair",
    "extract_textual_tool_call_names",
    "family_capability_terms",
    "filter_tools_for_policy",
    "first_incomplete_requested_family",
    "first_page_intent_kind",
    "log_tool_selection_status",
    "looks_like_explicit_time_request",
    "looks_like_explicit_web_research_request",
    "looks_like_generic_follow_up",
    "looks_like_generic_page_summary_request",
    "looks_like_tool_planning_leak",
    "mark_multi_family_progress",
    "messages_have_blocking_pending_interaction",
    "ordered_requested_families_from_intents",
    "response_denies_family_capability",
    "response_has_native_web_search_evidence",
    "restore_explicit_family_tools",
    "restrict_page_tools_for_generic_summary",
    "restrict_tools_to_names",
    "tool_family_for_name",
    "tool_semantic_family",
    "tool_semantic_tags",
]
