"""Tool policy and semantic helpers extracted from BaseEngine."""

from __future__ import annotations

from typing import Any

from app.ai.runtime.execution_trust_policy import (
    allows_tool as trust_policy_allows_tool,
)
from app.ai.text_semantics import (
    extract_textual_tool_call_names as extract_textual_tool_call_names_from_text,
)
from app.ai.text_semantics import (
    has_capability_denial_phrase,
    has_question_indicator,
    has_tool_planning_leak_phrase,
    mentions_page_detail_operation,
    mentions_rail_ticket,
)
from app.ai.tools.semantic_defaults import (
    FAMILY_HINT_TAGS as _SEMANTIC_FAMILY_HINT_TAGS,
)
from app.ai.tools.semantic_defaults import (
    tool_family_from_name as _tool_family_from_name_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_family as _tool_semantic_family_unified,
)
from app.ai.tools.semantic_defaults import (
    tool_semantic_tags as _tool_semantic_tags_unified,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag

from .base_helpers import truncate_preview as _truncate_preview_impl
from .intent_plan_accessors import resolve_intent_plan_from_input_variables
from .intent_planner import IntentPlanner
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_recent_successful_tool_names,
    has_page_context,
)
from .types import IntentPlan, ToolUsePolicy

logger = LogManager.get_logger("ai.engine")


def tool_family_for_name(
    tool_name: str,
    input_variables: dict[str, Any] | None = None,
) -> str:
    return _tool_family_from_name_unified(tool_name, input_variables)


def tool_semantic_family(
    tool: ToolDefinition,
    input_variables: dict[str, Any] | None = None,
) -> str:
    return _tool_semantic_family_unified(tool, input_variables)


def tool_semantic_tags(tool: ToolDefinition) -> list[str]:
    return _tool_semantic_tags_unified(tool)


def messages_have_blocking_pending_interaction(messages: list[ChatMessage]) -> bool:
    tail = messages[-8:] if len(messages) > 8 else messages
    for message in reversed(tail):
        meta = message.metadata or {}
        pending_consent = meta.get("pending_consent")
        if isinstance(pending_consent, dict) and not pending_consent.get("resolved"):
            return True
        pending_confirmation = meta.get("pending_confirmation")
        if isinstance(pending_confirmation, dict) and not pending_confirmation.get(
            "resolved"
        ):
            return True
        for tool_call in message.tool_calls or []:
            if isinstance(tool_call.get("pending_consent"), dict) and not tool_call[
                "pending_consent"
            ].get("resolved"):
                return True
            if isinstance(tool_call.get("pending_confirmation"), dict) and not tool_call[
                "pending_confirmation"
            ].get("resolved"):
                return True
    return False


def first_incomplete_requested_family(
    ordered_requested_families: list[str],
    completed_families: set[str],
) -> str | None:
    for family in ordered_requested_families:
        if family not in completed_families:
            return family
    return None


def mark_multi_family_progress(
    *,
    func_name: str,
    success: bool,
    ordered_requested_families: list[str],
    completed_families: set[str],
    has_fetch_url_in_toolset: bool,
    input_variables: dict[str, Any] | None,
) -> None:
    if not success:
        return
    family = tool_family_for_name(func_name, input_variables)
    if family == "web_research":
        if func_name == "fetch_url" or (
            func_name == "web_search" and not has_fetch_url_in_toolset
        ):
            completed_families.add("web_research")
        return
    if family in ordered_requested_families:
        completed_families.add(family)


def family_capability_terms(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> set[str]:
    from app.ai.tools.optimizer import _tokenize

    terms: set[str] = set()
    for hint in _SEMANTIC_FAMILY_HINT_TAGS.get(family, ()):
        normalized_hint = hint.strip().lower()
        if len(normalized_hint) >= 2:
            terms.add(normalized_hint)
        terms |= {token for token in _tokenize(hint) if len(token) >= 2}

    for tool in tools:
        if tool_semantic_family(tool, input_variables) != family:
            continue
        for value in [tool.name, tool.description or "", *tool_semantic_tags(tool)]:
            text = str(value or "").strip().lower()
            if len(text) >= 2:
                terms.add(text)
            terms |= {token for token in _tokenize(text) if len(token) >= 2}
    return terms


def response_denies_family_capability(
    *,
    normalized_text: str,
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> bool:
    if not has_capability_denial_phrase(normalized_text):
        return False
    capability_terms = family_capability_terms(family, tools, input_variables)
    return any(term in normalized_text for term in capability_terms)


def extract_textual_tool_call_names(
    response_text: str,
    tools: list[ToolDefinition],
) -> list[str]:
    text = " ".join((response_text or "").strip().split())
    if not text:
        return []

    known_tool_names = {tool.name for tool in tools} if tools else None
    tool_aliases: dict[str, str] = {}
    for tool in tools or []:
        tool_aliases[tool.name] = tool.name
        underlying_operation = str(
            (tool.config or {}).get("underlying_operation") or ""
        ).strip()
        if underlying_operation:
            tool_aliases[underlying_operation] = tool.name
    return extract_textual_tool_call_names_from_text(
        text,
        alias_to_tool_name=tool_aliases,
        known_tool_names=known_tool_names,
    )


def looks_like_tool_planning_leak(
    response_text: str,
    tools: list[ToolDefinition],
) -> bool:
    text = " ".join((response_text or "").strip().split())
    if not text:
        return False
    if not has_tool_planning_leak_phrase(text):
        return False
    return bool(extract_textual_tool_call_names(text, tools))


def detect_requested_turn_intents(
    user_text: str,
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> list[str]:
    normalized = (user_text or "").strip()
    if not normalized:
        return []

    planned = resolve_intent_plan_from_input_variables(input_variables)
    if not planned:
        planned = IntentPlanner.plan_turn(
            messages=[ChatMessage(role="user", content=normalized)],
            tools=tools,
            input_variables=input_variables,
            continuation_context=None,
            capability_bundle=None,
        )
    intents: list[str] = []

    def _push(intent_name: str) -> None:
        if intent_name not in intents:
            intents.append(intent_name)

    for intent in planned:
        if intent.family == "none" or not intent.requires_tools:
            continue
        if intent.kind == "weather_query":
            _push("weather")
            continue
        if intent.family == "page_ops":
            _push("page_summary")
            continue
        if intent.kind == "web_research":
            label = str(intent.user_visible_label or "").strip()
            if label == "weather_web_research":
                _push("weather")
                continue
            if label == "rail_search" or mentions_rail_ticket(normalized):
                _push("rail_ticket_research")

    return intents


def collect_completed_turn_intents(
    messages: list[ChatMessage],
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> set[str]:
    completed: set[str] = set()
    successful_tool_names = set(extract_recent_successful_tool_names(messages, limit=50))
    successful_queries, fetched_urls = collect_web_research_evidence(messages)
    weather_tool_names = {
        tool.name
        for tool in tools
        if tool_semantic_family(tool, input_variables) == "weather"
    }

    if successful_tool_names & (
        weather_tool_names | {"get_current_weather", "get_weather_forecast"}
    ):
        completed.add("weather")
    if any(
        any(
            token in url.lower()
            for token in ("weather", "cma.cn", "qweather", "weather.com")
        )
        for url in fetched_urls
    ):
        completed.add("weather")

    if successful_tool_names & {
        "ui_get_snapshot",
        "ui_read_region",
        "ui_read_table",
        "ui_list_interactables",
    }:
        completed.add("page_summary")

    rail_search_seen = any(mentions_rail_ticket(query) for query in successful_queries)
    rail_fetch_seen = any(
        any(token in url.lower() for token in ("12306", "gaotie", "huoche", "trains"))
        for url in fetched_urls
    )
    if rail_fetch_seen or (rail_search_seen and rail_fetch_seen):
        completed.add("rail_ticket_research")

    return completed


def response_has_native_web_search_evidence(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    raw_response = getattr(response, "raw_response", None)
    if not isinstance(raw_response, dict):
        return False

    for item in raw_response.get("output") or []:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "web_search_call":
            action = item.get("action")
            if not isinstance(action, dict):
                return True
            sources = action.get("sources")
            if isinstance(sources, list) and any(
                isinstance(source, dict)
                and str(source.get("url") or "").startswith(("http://", "https://"))
                for source in sources
            ):
                return True
            continue
        if item_type != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if str(content.get("type") or "").strip() != "output_text":
                continue
            for annotation in content.get("annotations") or []:
                if not isinstance(annotation, dict):
                    continue
                if str(annotation.get("type") or "").strip() != "url_citation":
                    continue
                if str(annotation.get("url") or "").startswith(("http://", "https://")):
                    return True
    return False


def looks_like_generic_follow_up(user_text: str) -> bool:
    raw = (user_text or "").strip()
    if not raw:
        return False
    if "?" in raw or "？" in raw:
        return False
    if has_question_indicator(raw):
        return False
    normalized = " ".join(raw.lower().split())
    if len(normalized) <= 24:
        return True
    return len(normalized) <= 44 and len(normalized.split()) <= 6


def allowed_tool_names_for_family(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> list[str]:
    if family == "none":
        return [tool.name for tool in tools]

    allowed: list[str] = []
    for tool in tools:
        if tool_semantic_family(tool, input_variables) == family:
            allowed.append(tool.name)
    return allowed or [tool.name for tool in tools]


def allowed_tool_names_for_families(
    families: list[str],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> list[str]:
    ordered: list[str] = []
    for family in families:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none":
            continue
        for name in allowed_tool_names_for_family(normalized, tools, input_variables):
            if name not in ordered:
                ordered.append(name)
    return ordered


def filter_tools_for_policy(
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
) -> list[ToolDefinition]:
    if not tools or not policy.allowed_tool_names:
        return tools
    allowed = set(policy.allowed_tool_names)
    filtered = [tool for tool in tools if tool.name in allowed]
    return filtered or tools


def restrict_tools_to_names(
    tools: list[ToolDefinition],
    allowed_names: list[str] | None,
) -> list[ToolDefinition]:
    if not allowed_names:
        return tools
    allowed = {str(name).strip() for name in allowed_names if str(name).strip()}
    restricted = [tool for tool in tools if tool.name in allowed]
    return restricted or tools


def restore_explicit_family_tools(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    policy: ToolUsePolicy,
) -> tuple[list[ToolDefinition], bool]:
    if policy.family == "none" or not policy.allowed_tool_names or not all_tools:
        return selected_tools, False

    allowed = set(policy.allowed_tool_names)
    if any(tool.name in allowed for tool in selected_tools):
        return selected_tools, False

    restored = [tool for tool in all_tools if tool.name in allowed]
    if restored:
        return restored, True
    return selected_tools, False


def ensure_explicit_family_coverage(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    explicit_requested_families: list[str],
    input_variables: dict[str, Any] | None = None,
) -> tuple[list[ToolDefinition], list[str]]:
    ordered_families: list[str] = []
    for family in explicit_requested_families:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none" or normalized in ordered_families:
            continue
        ordered_families.append(normalized)
    if len(ordered_families) <= 1:
        return selected_tools, []

    selected_names = {tool.name for tool in selected_tools}
    selected_by_family: set[str] = set()
    for tool in selected_tools:
        family = tool_semantic_family(tool, input_variables)
        if family:
            selected_by_family.add(family)

    missing_families = [
        family for family in ordered_families if family not in selected_by_family
    ]
    if not missing_families:
        return selected_tools, []

    restored = list(selected_tools)
    restored_families: list[str] = []
    for family in missing_families:
        candidates = allowed_tool_names_for_family(family, all_tools, input_variables)
        restored_any = False
        for name in candidates:
            if name in selected_names:
                continue
            candidate = next((tool for tool in all_tools if tool.name == name), None)
            if candidate is None:
                continue
            restored.append(candidate)
            selected_names.add(name)
            restored_any = True
            break
        if restored_any:
            restored_families.append(family)

    return restored, restored_families


def ensure_web_research_tool_pair(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    explicit_requested_families: list[str],
    policy: ToolUsePolicy,
) -> tuple[list[ToolDefinition], bool]:
    if not selected_tools or not all_tools:
        return selected_tools, False

    explicit_families = {
        str(family or "").strip() for family in explicit_requested_families
    }
    selected_names = {tool.name for tool in selected_tools}
    all_by_name = {tool.name: tool for tool in all_tools}
    if not ({"web_search", "fetch_url"} <= set(all_by_name)):
        return selected_tools, False

    web_research_active = (
        policy.family == "web_research"
        or "web_research" in explicit_families
        or bool({"web_search", "fetch_url"} & selected_names)
    )
    if not web_research_active:
        return selected_tools, False

    restored = list(selected_tools)
    restored_any = False
    for tool_name in ("web_search", "fetch_url"):
        if tool_name in selected_names:
            continue
        candidate = all_by_name.get(tool_name)
        if candidate is None:
            continue
        restored.append(candidate)
        selected_names.add(tool_name)
        restored_any = True
    return restored, restored_any


def looks_like_explicit_web_research_request(
    user_text: str,
    tools: list[ToolDefinition],
) -> bool:
    if not user_text or not tools:
        return False
    web_tools = [
        tool
        for tool in tools
        if tool_semantic_family(tool) == "web_research"
        or tool.name in {"web_search", "fetch_url"}
    ]
    if not web_tools:
        return False

    from app.ai.tools.optimizer import _tokenize

    query_text = user_text.lower()
    query_tokens = _tokenize(user_text)
    semantic_tokens: set[str] = set()
    for tool in web_tools:
        semantic_source = " ".join(
            [tool.name, tool.description or "", *tool_semantic_tags(tool)]
        )
        semantic_tokens |= _tokenize(semantic_source)

    if query_tokens & semantic_tokens:
        return True

    return any(
        tool.name.lower() in query_text
        or tool.name.lower().replace("_", " ") in query_text
        for tool in web_tools
    )


def first_page_intent_kind(
    *,
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str | None:
    intents = resolve_intent_plan_from_input_variables(input_variables)
    if not intents:
        intents = IntentPlanner.plan_turn(
            messages=[ChatMessage(role="user", content=user_text)],
            tools=tools,
            input_variables=input_variables,
            continuation_context=None,
            capability_bundle=None,
        )
    for intent in intents:
        if intent.family == "page_ops":
            return intent.kind
    return None


def looks_like_generic_page_summary_request(
    user_text: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> bool:
    normalized = (user_text or "").strip()
    if not normalized:
        return False
    page_intent_kind = first_page_intent_kind(
        user_text=normalized,
        tools=tools,
        input_variables=input_variables,
    )
    if page_intent_kind != "page_summary":
        return False
    if mentions_page_detail_operation(normalized):
        return False
    return bool(
        has_page_context(input_variables)
        or any(tool.name in {"ui_get_snapshot"} for tool in tools)
    )


def restrict_page_tools_for_generic_summary(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    user_text: str,
    input_variables: dict[str, Any] | None = None,
) -> tuple[list[ToolDefinition], bool]:
    if not looks_like_generic_page_summary_request(
        user_text,
        all_tools,
        input_variables,
    ):
        return selected_tools, False

    page_context_tool = next(
        (tool for tool in all_tools if tool.name in {"ui_get_snapshot"}),
        None,
    )
    if page_context_tool is None:
        return selected_tools, False

    restricted: list[ToolDefinition] = []
    seen_names: set[str] = set()
    for tool in selected_tools:
        if tool.name in {"ui_get_snapshot"}:
            if tool.name not in seen_names:
                restricted.append(tool)
                seen_names.add(tool.name)
            continue

        if tool_semantic_family(tool, input_variables) == "page_ops":
            continue

        if tool.name not in seen_names:
            restricted.append(tool)
            seen_names.add(tool.name)

    if page_context_tool.name not in seen_names:
        restricted.append(page_context_tool)

    restricted_names = [tool.name for tool in restricted]
    selected_names = [tool.name for tool in selected_tools]
    return restricted, restricted_names != selected_names


def looks_like_explicit_time_request(
    user_text: str,
    tools: list[ToolDefinition],
) -> bool:
    if not user_text or not tools:
        return False
    time_tools = [
        tool
        for tool in tools
        if tool_semantic_family(tool) == "time_ops" or tool.name == "get_current_time"
    ]
    if not time_tools:
        return False

    from app.ai.tools.optimizer import _tokenize

    query_tokens = _tokenize(user_text)
    semantic_tokens: set[str] = set()
    for tool in time_tools:
        semantic_source = " ".join(
            [tool.name, tool.description or "", *tool_semantic_tags(tool)]
        )
        semantic_tokens |= _tokenize(semantic_source)
    return bool(query_tokens & semantic_tokens)


def log_tool_selection_status(
    *,
    status: str,
    agent: Any,
    conversation_id: int | None,
    current_user_text: str,
    family: str,
    all_tool_names: list[str],
    selected_tool_names: list[str],
    page_context_present: bool,
    optimizer_total: int,
    optimizer_selected: int,
) -> None:
    logger.warning(
        "Tool selection status: status={} runtime={} agent_id={} conversation_id={} family={} current_user_text={} all_tool_names={} selected_tool_names={} page_context_present={} optimizer_total={} optimizer_selected={}",
        status,
        get_runtime_identity_tag(),
        getattr(agent, "id", None),
        conversation_id,
        family,
        _truncate_preview_impl(current_user_text),
        all_tool_names,
        selected_tool_names,
        page_context_present,
        optimizer_total,
        optimizer_selected,
    )


def ordered_requested_families_from_intents(*, intents: list[IntentPlan]) -> list[str]:
    ordered: list[str] = []
    for intent in intents:
        family = str(intent.family or "").strip()
        if not family or family == "none" or family in ordered:
            continue
        ordered.append(family)
    return ordered


def build_required_policy_for_family(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    reason: str,
) -> ToolUsePolicy:
    return ToolUsePolicy(
        family=family,
        mode="required",
        allowed_tool_names=allowed_tool_names_for_family(
            family,
            tools,
            input_variables,
        ),
        retry_on_contract_breach=False,
        reason=reason,
    )


def apply_execution_trust_policy(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    tool_consent_modes: dict[str, str],
    trust_policy_ref: dict[str, Any] | None,
    interaction_mode: str = "confirm",
) -> dict[str, str]:
    is_trusted_auto = str(interaction_mode or "confirm").strip() == "trusted_auto"
    has_policy = isinstance(trust_policy_ref, dict)

    if not is_trusted_auto:
        if not tools or not has_policy:
            return tool_consent_modes
        updated = dict(tool_consent_modes)
        for tool in tools:
            current_mode = updated.get(tool.name, "auto")
            if current_mode != "ask":
                continue
            tool_family = tool_semantic_family(tool, input_variables)
            if trust_policy_allows_tool(
                tool_name=tool.name,
                tool_family=tool_family,
                policy_ref=trust_policy_ref,
            ):
                updated[tool.name] = "auto"
        return updated

    if not tools:
        return tool_consent_modes

    from .tool_processor import is_trusted_auto_read_only_tool_call

    updated = dict(tool_consent_modes)
    for tool in tools:
        current_mode = updated.get(tool.name, "auto")
        if current_mode != "ask":
            continue
        if has_policy:
            tool_family = tool_semantic_family(tool, input_variables)
            if trust_policy_allows_tool(
                tool_name=tool.name,
                tool_family=tool_family,
                policy_ref=trust_policy_ref,
            ):
                updated[tool.name] = "auto"
                continue
        if is_trusted_auto_read_only_tool_call(tool.name):
            updated[tool.name] = "auto"
    return updated
