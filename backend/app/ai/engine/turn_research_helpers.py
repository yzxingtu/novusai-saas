"""Turn-level research helpers extracted from BaseEngine."""

from __future__ import annotations

from .turn_research_continuation import (
    build_web_research_continuation_context,
    has_page_context,
    page_operation_names_from_input_variables,
)
from .turn_research_evidence import (
    collect_web_research_evidence,
    extract_recent_successful_tool_names,
    extract_recent_web_queries,
)
from .turn_research_extraction import (
    collect_current_turn_fetch_titles,
    extract_fetch_title_from_output,
    extract_last_user_text,
    extract_latest_turn_runtime_facts,
    extract_recent_research_instruction_texts,
    is_title_only_fetch_response,
    looks_like_explicit_title_request,
    normalize_web_research_contract_text,
)
from .turn_research_gating import (
    apply_fetch_url_only_gate,
    needs_fetch_url_before_summary,
)

__all__ = [
    "apply_fetch_url_only_gate",
    "build_web_research_continuation_context",
    "collect_current_turn_fetch_titles",
    "collect_web_research_evidence",
    "extract_fetch_title_from_output",
    "extract_last_user_text",
    "extract_latest_turn_runtime_facts",
    "extract_recent_research_instruction_texts",
    "extract_recent_successful_tool_names",
    "extract_recent_web_queries",
    "has_page_context",
    "is_title_only_fetch_response",
    "looks_like_explicit_title_request",
    "needs_fetch_url_before_summary",
    "normalize_web_research_contract_text",
    "page_operation_names_from_input_variables",
]
