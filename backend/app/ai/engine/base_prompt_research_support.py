"""
Research bindings for BaseEngine prompt/runtime support.
"""

from __future__ import annotations

from .turn_research_helpers import (
    apply_fetch_url_only_gate as _apply_fetch_url_only_gate_impl,
)
from .turn_research_helpers import (
    build_web_research_continuation_context as _build_web_research_continuation_context_impl,
)
from .turn_research_helpers import (
    collect_current_turn_fetch_titles as _collect_current_turn_fetch_titles_impl,
)
from .turn_research_helpers import (
    collect_web_research_evidence as _collect_web_research_evidence_impl,
)
from .turn_research_helpers import (
    extract_fetch_title_from_output as _extract_fetch_title_from_output_impl,
)
from .turn_research_helpers import (
    extract_last_user_text as _extract_last_user_text_impl,
)
from .turn_research_helpers import (
    extract_latest_turn_runtime_facts as _extract_latest_turn_runtime_facts_impl,
)
from .turn_research_helpers import (
    extract_recent_research_instruction_texts as _extract_recent_research_instruction_texts_impl,
)
from .turn_research_helpers import (
    extract_recent_successful_tool_names as _extract_recent_successful_tool_names_impl,
)
from .turn_research_helpers import (
    extract_recent_web_queries as _extract_recent_web_queries_impl,
)
from .turn_research_helpers import (
    is_title_only_fetch_response as _is_title_only_fetch_response_impl,
)
from .turn_research_helpers import (
    looks_like_explicit_title_request as _looks_like_explicit_title_request_impl,
)
from .turn_research_helpers import (
    needs_fetch_url_before_summary as _needs_fetch_url_before_summary_impl,
)
from .turn_research_helpers import (
    normalize_web_research_contract_text as _normalize_web_research_contract_text_impl,
)


class BasePromptResearchSupportMixin:
    """Binds research gating helpers onto BaseEngine."""

    _extract_recent_successful_tool_names = staticmethod(
        _extract_recent_successful_tool_names_impl
    )
    _extract_recent_web_queries = staticmethod(_extract_recent_web_queries_impl)
    _collect_web_research_evidence = staticmethod(_collect_web_research_evidence_impl)
    _collect_current_turn_fetch_titles = staticmethod(
        _collect_current_turn_fetch_titles_impl
    )
    _extract_fetch_title_from_output = staticmethod(_extract_fetch_title_from_output_impl)
    _normalize_web_research_contract_text = staticmethod(
        _normalize_web_research_contract_text_impl
    )
    _looks_like_explicit_title_request = staticmethod(
        _looks_like_explicit_title_request_impl
    )
    _is_title_only_fetch_response = staticmethod(_is_title_only_fetch_response_impl)
    _needs_fetch_url_before_summary = staticmethod(_needs_fetch_url_before_summary_impl)
    _apply_fetch_url_only_gate = staticmethod(_apply_fetch_url_only_gate_impl)
    _extract_last_user_text = staticmethod(_extract_last_user_text_impl)
    _extract_recent_research_instruction_texts = staticmethod(
        _extract_recent_research_instruction_texts_impl
    )
    _extract_latest_turn_runtime_facts = staticmethod(
        _extract_latest_turn_runtime_facts_impl
    )
    _build_web_research_continuation_context = staticmethod(
        _build_web_research_continuation_context_impl
    )


__all__ = ["BasePromptResearchSupportMixin"]
