"""Turn-level research helpers extracted from BaseEngine."""

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

from .base_helpers import (
    parse_tool_arguments,
    stable_unique_text_list,
    tool_call_name,
    tool_call_operation_name,
)
from .types import ResearchContinuationContext


def extract_recent_successful_tool_names(
    messages: list[ChatMessage],
    *,
    limit: int = 12,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for msg in reversed(messages):
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            if not tool_name or tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
            if len(names) >= limit:
                return names

    return names


def extract_recent_web_queries(
    messages: list[ChatMessage],
    *,
    limit: int = 5,
) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    for msg in reversed(messages):
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            if tool_name != "web_search":
                continue
            arguments = parse_tool_arguments(
                (tool_call.get("function") or {}).get("arguments")
            )
            query = str(arguments.get("query") or "").strip()
            if not query or query in seen:
                continue
            queries.append(query)
            seen.add(query)
            if len(queries) >= limit:
                return queries

    return queries


def collect_web_research_evidence(
    messages: list[ChatMessage],
) -> tuple[list[str], list[str]]:
    search_queries: list[str] = []
    fetched_urls: list[str] = []
    seen_queries: set[str] = set()
    seen_urls: set[str] = set()

    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            tool_name = tool_call_name(tool_call)
            arguments = parse_tool_arguments(
                (tool_call.get("function") or {}).get("arguments")
            )
            if tool_name == "web_search":
                query = str(arguments.get("query") or "").strip()
                if query and query not in seen_queries:
                    search_queries.append(query)
                    seen_queries.add(query)
            elif tool_name == "fetch_url":
                url = str(arguments.get("url") or "").strip()
                if url and url not in seen_urls:
                    fetched_urls.append(url)
                    seen_urls.add(url)

    return search_queries, fetched_urls


def extract_fetch_title_from_output(output: str) -> str:
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if line.startswith("Title: "):
            return line.removeprefix("Title: ").strip()
    return ""


def normalize_web_research_contract_text(text: str) -> str:
    value = " ".join(str(text or "").split())
    if not value:
        return ""
    if value.startswith("[") and "](" in value and value.endswith(")"):
        value = value[1 : value.index("](")].strip()
    for prefix in (
        "title:",
        "标题:",
        "标题是",
        "网页标题:",
        "页面标题:",
        "source:",
        "来源:",
    ):
        if value.casefold().startswith(prefix.casefold()):
            value = value[len(prefix) :].strip()
            break
    return value.strip(" \t\r\n\"'`[](){}<>.,;:!?。，；：！？、").casefold()


def collect_current_turn_fetch_titles(messages: list[ChatMessage]) -> list[str]:
    last_user_index = -1
    for index, msg in enumerate(messages):
        if msg.role == "user":
            last_user_index = index

    turn_messages = messages[last_user_index + 1 :] if last_user_index >= 0 else messages
    fetch_call_ids: set[str] = set()
    titles: list[str] = []
    seen_titles: set[str] = set()

    for msg in turn_messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            if tool_call_name(tool_call) != "fetch_url":
                continue
            tool_call_id = str(
                tool_call.get("id") or tool_call.get("tool_call_id") or ""
            ).strip()
            if tool_call_id:
                fetch_call_ids.add(tool_call_id)

    for msg in turn_messages:
        if msg.role != "tool":
            continue
        tool_call_id = str(getattr(msg, "tool_call_id", "") or "").strip()
        if fetch_call_ids:
            if tool_call_id and tool_call_id not in fetch_call_ids:
                continue
            if not tool_call_id and "Content from " not in str(msg.content or ""):
                continue

        title = extract_fetch_title_from_output(msg.content or "")
        if not title:
            continue
        normalized = normalize_web_research_contract_text(title)
        if not normalized or normalized in seen_titles:
            continue
        titles.append(title)
        seen_titles.add(normalized)

    return titles


def looks_like_explicit_title_request(user_text: str) -> bool:
    normalized = " ".join(str(user_text or "").casefold().split())
    if not normalized:
        return False
    return any(
        term in normalized
        for term in (
            "标题",
            "headline",
            "page title",
            "article title",
            "title of",
            "what is the title",
        )
    )


def is_title_only_fetch_response(
    *,
    messages: list[ChatMessage],
    response_text: str,
    user_text: str,
) -> bool:
    if looks_like_explicit_title_request(user_text):
        return False

    normalized_response = normalize_web_research_contract_text(response_text)
    if not normalized_response:
        return False

    fetched_titles = collect_current_turn_fetch_titles(messages)
    if not fetched_titles:
        return False

    return any(
        normalized_response == normalize_web_research_contract_text(title)
        for title in fetched_titles
    )


def needs_fetch_url_before_summary(messages: list[ChatMessage]) -> bool:
    """True when web_search succeeded but fetch_url has not been attempted yet."""
    has_success_search_with_candidates = False
    fetch_attempted = False
    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            name = tool_call_name(tool_call)
            if name == "web_search" and tool_call.get("success") is True:
                payload = tool_call.get("summary_payload")
                payload = payload if isinstance(payload, dict) else {}
                items = payload.get("items")
                candidate_urls = (
                    [
                        str(item.get("url") or "").strip()
                        for item in items
                        if isinstance(item, dict)
                        and str(item.get("url") or "").strip()
                    ]
                    if isinstance(items, list)
                    else []
                )
                raw_count = payload.get("result_count")
                try:
                    result_count = int(raw_count) if raw_count is not None else None
                except (TypeError, ValueError):
                    result_count = None
                if result_count is None:
                    result_count = len(candidate_urls)
                if result_count > 0 and candidate_urls:
                    has_success_search_with_candidates = True
            if name == "fetch_url":
                fetch_attempted = True
    return bool(has_success_search_with_candidates and not fetch_attempted)


def apply_fetch_url_only_gate(
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    all_tools: list[ToolDefinition] | None,
) -> list[ToolDefinition]:
    if not needs_fetch_url_before_summary(messages):
        return tools
    fetch_defs = [tool for tool in (all_tools or tools) if tool.name == "fetch_url"]
    return fetch_defs if fetch_defs else tools


def extract_last_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        text = (msg.content or "").strip()
        if text:
            return text
    return ""


def extract_recent_research_instruction_texts(
    prior_messages: list[ChatMessage],
    current_user_text: str,
    *,
    limit: int = 3,
) -> list[str]:
    texts: list[str] = []
    if current_user_text:
        texts.append(current_user_text)

    for msg in reversed(prior_messages):
        if msg.role != "user":
            continue
        text = (msg.content or "").strip()
        if not text or text in texts:
            continue
        texts.append(text)
        if len(texts) >= limit:
            break

    return list(reversed(texts))


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


def extract_latest_turn_runtime_facts(messages: list[ChatMessage]) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "last_tool_name": "",
        "last_page_key": "",
        "last_page_op": "",
        "active_intent_kind": None,
    }

    def _candidate_dicts(message: ChatMessage) -> list[dict[str, Any]]:
        metadata = dict(message.metadata or {}) if isinstance(message.metadata, dict) else {}
        candidates = [metadata]
        for key in ("turn_record", "context_diagnostics", "last_run_summary"):
            value = metadata.get(key)
            if isinstance(value, dict):
                candidates.append(dict(value))
        turn_record = metadata.get("turn_record")
        if isinstance(turn_record, dict):
            turn_record_metadata = turn_record.get("metadata")
            if isinstance(turn_record_metadata, dict):
                candidates.append(dict(turn_record_metadata))
                diagnostics = turn_record_metadata.get("turn_diagnostics")
                if isinstance(diagnostics, dict):
                    candidates.append(dict(diagnostics))
        return candidates

    for message in reversed(messages):
        if message.role != "assistant":
            continue

        if not facts["active_intent_kind"]:
            for candidate in _candidate_dicts(message):
                tool_planner = candidate.get("tool_planner")
                if isinstance(tool_planner, dict):
                    intent_kind = str(tool_planner.get("intent") or "").strip()
                    if intent_kind:
                        facts["active_intent_kind"] = intent_kind
                        break
                intent_kind = str(candidate.get("active_intent_kind") or "").strip()
                if intent_kind:
                    facts["active_intent_kind"] = intent_kind
                    break

        for tool_call in reversed(message.tool_calls or []):
            if tool_call.get("success") is not True:
                continue
            if not facts["last_tool_name"]:
                facts["last_tool_name"] = tool_call_name(tool_call)
            if not facts["last_page_op"]:
                facts["last_page_op"] = tool_call_operation_name(tool_call)
            if not facts["last_page_key"]:
                arguments = parse_tool_arguments(
                    (tool_call.get("function") or {}).get("arguments")
                )
                facts["last_page_key"] = str(arguments.get("page_key") or "").strip()
            if (
                facts["last_tool_name"]
                and facts["last_page_op"]
                and facts["last_page_key"]
                and facts["active_intent_kind"]
            ):
                return facts
        if facts["last_tool_name"] and facts["active_intent_kind"]:
            return facts

    return facts


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

    active = False
    family: str | None = None
    if (
        "page_ops" in continuation_capable_families
        and (
            last_tool_family == "page_ops"
            or str(active_intent_kind or "").startswith("page_")
        )
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
