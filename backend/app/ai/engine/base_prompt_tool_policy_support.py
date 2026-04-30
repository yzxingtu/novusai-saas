"""
Tool policy bindings for BaseEngine prompt/runtime support.
"""

from __future__ import annotations

from .tool_policy_helpers import (
    allowed_tool_names_for_families as _allowed_tool_names_for_families_impl,
)
from .tool_policy_helpers import (
    allowed_tool_names_for_family as _allowed_tool_names_for_family_impl,
)
from .tool_policy_helpers import (
    apply_execution_trust_policy as _apply_execution_trust_policy_impl,
)
from .tool_policy_helpers import (
    build_required_policy_for_family as _build_required_policy_for_family_impl,
)
from .tool_policy_helpers import (
    collect_completed_turn_intents as _collect_completed_turn_intents_impl,
)
from .tool_policy_helpers import (
    detect_requested_turn_intents as _detect_requested_turn_intents_impl,
)
from .tool_policy_helpers import (
    ensure_explicit_family_coverage as _ensure_explicit_family_coverage_impl,
)
from .tool_policy_helpers import (
    ensure_web_research_tool_pair as _ensure_web_research_tool_pair_impl,
)
from .tool_policy_helpers import (
    extract_textual_tool_call_names as _extract_textual_tool_call_names_impl,
)
from .tool_policy_helpers import (
    family_capability_terms as _family_capability_terms_impl,
)
from .tool_policy_helpers import (
    filter_tools_for_policy as _filter_tools_for_policy_impl,
)
from .tool_policy_helpers import (
    first_incomplete_requested_family as _first_incomplete_requested_family_impl,
)
from .tool_policy_helpers import (
    first_page_intent_kind as _first_page_intent_kind_impl,
)
from .tool_policy_helpers import (
    looks_like_explicit_time_request as _looks_like_explicit_time_request_impl,
)
from .tool_policy_helpers import (
    looks_like_explicit_web_research_request as _looks_like_explicit_web_research_request_impl,
)
from .tool_policy_helpers import (
    looks_like_generic_follow_up as _looks_like_generic_follow_up_impl,
)
from .tool_policy_helpers import (
    looks_like_generic_page_summary_request as _looks_like_generic_page_summary_request_impl,
)
from .tool_policy_helpers import (
    looks_like_tool_planning_leak as _looks_like_tool_planning_leak_impl,
)
from .tool_policy_helpers import (
    mark_multi_family_progress as _mark_multi_family_progress_impl,
)
from .tool_policy_helpers import (
    messages_have_blocking_pending_interaction as _messages_have_blocking_pending_interaction_impl,
)
from .tool_policy_helpers import (
    ordered_requested_families_from_intents as _ordered_requested_families_from_intents_impl,
)
from .tool_policy_helpers import (
    response_denies_family_capability as _response_denies_family_capability_impl,
)
from .tool_policy_helpers import (
    response_has_native_web_search_evidence as _response_has_native_web_search_evidence_impl,
)
from .tool_policy_helpers import (
    restore_explicit_family_tools as _restore_explicit_family_tools_impl,
)
from .tool_policy_helpers import (
    restrict_page_tools_for_generic_summary as _restrict_page_tools_for_generic_summary_impl,
)
from .tool_policy_helpers import (
    restrict_tools_to_names as _restrict_tools_to_names_impl,
)
from .tool_policy_helpers import (
    tool_family_for_name as _tool_family_for_name_impl,
)
from .tool_policy_helpers import (
    tool_semantic_family as _tool_semantic_family_impl,
)
from .tool_policy_helpers import (
    tool_semantic_tags as _tool_semantic_tags_impl,
)


class BasePromptToolPolicySupportMixin:
    """Binds tool policy and selection helpers onto BaseEngine."""

    _restrict_tools_to_names = staticmethod(_restrict_tools_to_names_impl)
    _tool_family_for_name = staticmethod(_tool_family_for_name_impl)
    _messages_have_blocking_pending_interaction = staticmethod(
        _messages_have_blocking_pending_interaction_impl
    )
    _first_incomplete_requested_family = staticmethod(
        _first_incomplete_requested_family_impl
    )
    _mark_multi_family_progress = staticmethod(_mark_multi_family_progress_impl)
    _tool_semantic_family = staticmethod(_tool_semantic_family_impl)
    _tool_semantic_tags = staticmethod(_tool_semantic_tags_impl)
    _family_capability_terms = staticmethod(_family_capability_terms_impl)
    _response_denies_family_capability = staticmethod(
        _response_denies_family_capability_impl
    )
    _extract_textual_tool_call_names = staticmethod(
        _extract_textual_tool_call_names_impl
    )
    _looks_like_tool_planning_leak = staticmethod(_looks_like_tool_planning_leak_impl)
    _detect_requested_turn_intents = staticmethod(_detect_requested_turn_intents_impl)
    _collect_completed_turn_intents = staticmethod(_collect_completed_turn_intents_impl)
    _response_has_native_web_search_evidence = staticmethod(
        _response_has_native_web_search_evidence_impl
    )
    _looks_like_generic_follow_up = staticmethod(_looks_like_generic_follow_up_impl)
    _allowed_tool_names_for_family = staticmethod(_allowed_tool_names_for_family_impl)
    _allowed_tool_names_for_families = staticmethod(
        _allowed_tool_names_for_families_impl
    )
    _filter_tools_for_policy = staticmethod(_filter_tools_for_policy_impl)
    _restore_explicit_family_tools = staticmethod(_restore_explicit_family_tools_impl)
    _ensure_explicit_family_coverage = staticmethod(
        _ensure_explicit_family_coverage_impl
    )
    _ensure_web_research_tool_pair = staticmethod(_ensure_web_research_tool_pair_impl)
    _looks_like_explicit_web_research_request = staticmethod(
        _looks_like_explicit_web_research_request_impl
    )
    _first_page_intent_kind = staticmethod(_first_page_intent_kind_impl)
    _looks_like_generic_page_summary_request = staticmethod(
        _looks_like_generic_page_summary_request_impl
    )
    _restrict_page_tools_for_generic_summary = staticmethod(
        _restrict_page_tools_for_generic_summary_impl
    )
    _looks_like_explicit_time_request = staticmethod(
        _looks_like_explicit_time_request_impl
    )
    _ordered_requested_families_from_intents = staticmethod(
        _ordered_requested_families_from_intents_impl
    )
    _build_required_policy_for_family = staticmethod(
        _build_required_policy_for_family_impl
    )
    _apply_execution_trust_policy = staticmethod(_apply_execution_trust_policy_impl)


__all__ = ["BasePromptToolPolicySupportMixin"]
