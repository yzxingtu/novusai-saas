"""Continuation context helpers for turn-level research."""

from __future__ import annotations

from typing import Any

from app.ai.tools.semantic_defaults import (
    _has_page_context as _has_page_context_unified,
)
from app.ai.tools.semantic_defaults import (
    page_context_available_ui_tools,
    page_context_payload,
)
from app.ai.tools.semantic_defaults import (
    tool_family_from_name as _tool_family_from_name_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_family as _tool_semantic_family_unified,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import stable_unique_text_list
from .intent_page_rules import looks_like_page_follow_up
from .turn_research_evidence import (
    collect_web_research_evidence,
    extract_recent_successful_tool_names,
    extract_recent_web_queries,
)
from .turn_research_extraction import (
    extract_last_user_text,
    extract_latest_turn_runtime_facts,
    extract_recent_research_instruction_texts,
)
from .types import ResearchContinuationContext


def has_page_context(input_variables: dict[str, Any] | None) -> bool:
    return _has_page_context_unified(input_variables)


def page_operation_names_from_input_variables(
    input_variables: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(input_variables, dict):
        return []
    page_context = page_context_payload(input_variables)
    if not isinstance(page_context, dict):
        return []
    return page_context_available_ui_tools(page_context)


def build_web_research_continuation_context(
    messages: list[ChatMessage],
    all_tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> ResearchContinuationContext:
    tool_names = {tool.name for tool in all_tools}
    tool_families = [
        family
        for family in stable_unique_text_list(
            [_tool_semantic_family_unified(tool, input_variables) for tool in all_tools]
        )
        if family != "none"
    ]
    page_operation_names = page_operation_names_from_input_variables(input_variables)
    page_context_attached = has_page_context(input_variables)
    web_research_pair_complete = {"web_search", "fetch_url"} <= tool_names
    continuation_capable_families: list[str] = []
    if page_context_attached and "page_ops" in tool_families:
        continuation_capable_families.append("page_ops")
    if web_research_pair_complete and "web_research" in tool_families:
        continuation_capable_families.append("web_research")

    current_user_text = ""
    prior_messages: list[ChatMessage] = []
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if msg.role == "user":
            current_user_text = (msg.content or "").strip()
            prior_messages = messages[:idx]
            break

    if not current_user_text:
        return ResearchContinuationContext(
            tool_families=tool_families,
            page_operation_names=page_operation_names,
            page_context_attached=page_context_attached,
            web_research_pair_complete=web_research_pair_complete,
            continuation_capable_families=continuation_capable_families,
        )

    recent_successful_tool_names = extract_recent_successful_tool_names(prior_messages)
    recent_web_queries = extract_recent_web_queries(prior_messages)
    search_queries, fetched_urls = collect_web_research_evidence(prior_messages)
    research_instruction_texts = extract_recent_research_instruction_texts(
        prior_messages,
        current_user_text,
    )
    last_turn_facts = extract_latest_turn_runtime_facts(prior_messages)
    latest_successful_tool = (
        recent_successful_tool_names[0] if recent_successful_tool_names else ""
    )
    last_tool_name = str(last_turn_facts.get("last_tool_name") or "").strip()
    last_page_key = str(last_turn_facts.get("last_page_key") or "").strip()
    last_page_op = str(last_turn_facts.get("last_page_op") or "").strip()
    active_intent_kind = (
        str(last_turn_facts.get("active_intent_kind") or "").strip() or None
    )
    last_tool_family = _tool_family_from_name_unified(last_tool_name, input_variables)
    page_follow_up_requested = looks_like_page_follow_up(current_user_text)
    # A bare historical ui_* tool name is not a safe continuation anchor: the
    # current page may be unrelated. Canonical page continuation requires a
    # page key from turn diagnostics/tool evidence.
    prior_page_progress = bool(last_page_key)

    active = False
    family: str | None = None
    if (
        "page_ops" in continuation_capable_families
        and page_follow_up_requested
        and prior_page_progress
    ):
        active = True
        family = "page_ops"
    elif latest_successful_tool in {"web_search", "fetch_url"} and "web_search" in tool_names:
        active = True
        family = "web_research"

    origin = "continuation" if active else "none"

    research_target_text = (
        recent_web_queries[0]
        if recent_web_queries
        else (
            last_page_key
            if family == "page_ops" and last_page_key
            else extract_last_user_text(prior_messages) or current_user_text
        )
    )

    return ResearchContinuationContext(
        active=active,
        family=family,
        origin=origin,
        current_user_text=current_user_text,
        research_target_text=research_target_text,
        recent_successful_tool_names=recent_successful_tool_names,
        recent_web_queries=recent_web_queries,
        search_query_count=len(search_queries),
        fetched_url_count=len(fetched_urls),
        research_instruction_texts=research_instruction_texts,
        tool_families=tool_families,
        page_operation_names=page_operation_names,
        page_context_attached=page_context_attached,
        web_research_pair_complete=web_research_pair_complete,
        continuation_capable_families=continuation_capable_families,
        last_tool_name=last_tool_name,
        last_page_key=last_page_key,
        last_page_op=last_page_op,
        active_intent_kind=active_intent_kind,
    )
