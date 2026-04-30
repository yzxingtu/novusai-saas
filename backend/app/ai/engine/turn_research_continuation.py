"""Continuation context helpers for turn-level research."""

from __future__ import annotations

from typing import Any

from app.ai.tools.semantic_defaults import (
    tool_semantic_family as _tool_semantic_family_unified,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .base_helpers import stable_unique_text_list
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
    web_research_pair_complete = {"web_search", "fetch_url"} <= tool_names
    continuation_capable_families: list[str] = []
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
    active_intent_kind = (
        str(last_turn_facts.get("active_intent_kind") or "").strip() or None
    )

    active = False
    family: str | None = None
    if latest_successful_tool in {"web_search", "fetch_url"} and "web_search" in tool_names:
        active = True
        family = "web_research"

    origin = "continuation" if active else "none"

    research_target_text = (
        recent_web_queries[0]
        if recent_web_queries
        else extract_last_user_text(prior_messages) or current_user_text
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
        web_research_pair_complete=web_research_pair_complete,
        continuation_capable_families=continuation_capable_families,
        last_tool_name=last_tool_name,
        active_intent_kind=active_intent_kind,
    )
