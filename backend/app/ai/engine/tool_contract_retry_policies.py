"""Tool contract retry policy helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

from .contract_diagnostics_helpers import build_contract_recovery_system_message
from .tool_policy_helpers import (
    allowed_tool_names_for_families,
    build_required_policy_for_family,
    detect_requested_turn_intents,
    extract_textual_tool_call_names,
    looks_like_explicit_web_research_request,
    response_denies_family_capability,
    tool_family_for_name,
    tool_semantic_family,
)
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_last_user_text,
    is_title_only_fetch_response,
)
from .types import ResearchContinuationContext, ToolUsePolicy


def build_post_tool_retry_policy(
    *,
    breach_type: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    current_policy: ToolUsePolicy,
    leaked_tool_names: list[str] | None = None,
    unfinished_intents: list[str] | None = None,
) -> ToolUsePolicy | None:
    families: list[str] = []

    for tool_name in leaked_tool_names or []:
        family = tool_family_for_name(tool_name, input_variables)
        if family != "none" and family not in families:
            families.append(family)

    for intent in unfinished_intents or []:
        if str(intent or "").startswith("page_"):
            family = "page_ops"
        elif intent in {"weather", "rail_ticket_research"}:
            if (
                any(tool_semantic_family(tool, input_variables) == "weather" for tool in tools)
                and intent == "weather"
            ):
                family = "weather"
            else:
                family = "web_research"
        else:
            family = "none"
        if family != "none" and family not in families:
            families.append(family)

    if not families and current_policy.family != "none":
        families.append(current_policy.family)
    if not families:
        return None

    allowed_names = allowed_tool_names_for_families(families, tools, input_variables)
    if not allowed_names:
        return None

    reason_suffix_parts = [*(unfinished_intents or []), *(leaked_tool_names or [])]
    return ToolUsePolicy(
        family=families[0],
        mode="required",
        allowed_tool_names=allowed_names,
        retry_on_contract_breach=False,
        reason=f"{breach_type}:{','.join(reason_suffix_parts)}",
    )


def resolve_breach_retry_policy(
    *,
    response_text: str,
    tools: list[ToolDefinition],
    current_policy: ToolUsePolicy,
    input_variables: dict[str, Any] | None,
) -> ToolUsePolicy | None:
    if not tools:
        return None

    normalized = " ".join((response_text or "").strip().lower().split())
    if not normalized:
        return None

    leaked_tool_names = extract_textual_tool_call_names(response_text, tools)
    for tool_name in leaked_tool_names:
        family = tool_family_for_name(tool_name, input_variables)
        if family == "none" and current_policy.family != "none":
            family = current_policy.family
        allowed_names = allowed_tool_names_for_families([family], tools, input_variables)
        if allowed_names:
            return build_required_policy_for_family(
                family,
                tools,
                input_variables,
                reason=f"textual_tool_call_leak:{tool_name}",
            )

    if current_policy.mode == "required" and current_policy.family != "none":
        return build_required_policy_for_family(
            current_policy.family,
            tools,
            input_variables,
            reason=f"required_retry:{current_policy.reason or current_policy.family}",
        )

    if current_policy.family != "none" and current_policy.allowed_tool_names:
        return build_required_policy_for_family(
            current_policy.family,
            tools,
            input_variables,
            reason=f"capability_denial:{current_policy.family}",
        )

    for family in ("web_research", "weather", "time_ops", "page_ops"):
        if not response_denies_family_capability(
            normalized_text=normalized,
            family=family,
            tools=tools,
            input_variables=input_variables,
        ):
            continue
        allowed_names = allowed_tool_names_for_families([family], tools, input_variables)
        if allowed_names:
            return build_required_policy_for_family(
                family,
                tools,
                input_variables,
                reason=f"capability_denial:{family}",
            )
    return None


def should_retry_tool_contract_breach(
    *,
    response: ChatResponse,
    current_policy: ToolUsePolicy,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> tuple[bool, ToolUsePolicy | None, str]:
    if response.tool_calls:
        return False, None, ""

    response_text = (response.message.content or "").strip()
    if not response_text:
        return False, None, ""

    retry_policy = resolve_breach_retry_policy(
        response_text=response_text,
        tools=tools,
        current_policy=current_policy,
        input_variables=input_variables,
    )
    if retry_policy is None:
        return False, None, ""
    return True, retry_policy, response_text


def should_retry_web_research_contract_breach(
    *,
    messages: list[ChatMessage],
    response: ChatResponse,
    current_policy: ToolUsePolicy,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    continuation: ResearchContinuationContext | None,
) -> tuple[bool, ToolUsePolicy | None, str]:
    if response.tool_calls:
        return False, None, ""

    response_text = (response.message.content or "").strip()
    if not response_text:
        return False, None, ""

    tool_names = {tool.name for tool in tools}
    if not {"web_search", "fetch_url"} <= tool_names:
        return False, None, ""

    search_queries, fetched_urls = collect_web_research_evidence(messages)
    if not search_queries:
        return False, None, ""

    current_user_text = extract_last_user_text(messages)
    requested_intents = detect_requested_turn_intents(
        current_user_text,
        tools=tools,
        input_variables=input_variables,
    )
    explicit_web_request = looks_like_explicit_web_research_request(
        current_user_text,
        tools,
    )
    web_research_requested = (
        current_policy.family == "web_research"
        or bool(continuation and continuation.active)
        or explicit_web_request
        or any(intent in {"weather", "rail_ticket_research"} for intent in requested_intents)
    )
    if not web_research_requested:
        return False, None, ""

    if not fetched_urls:
        retry_policy = build_required_policy_for_family(
            "web_research",
            tools,
            input_variables,
            reason="web_research_summary_without_fetch",
        )
        if current_policy.reason.startswith("web_research_summary_without_fetch"):
            retry_policy.retry_on_contract_breach = False
        return True, retry_policy, response_text

    if current_policy.reason.startswith("web_research_title_only_after_fetch"):
        return False, None, ""
    if not is_title_only_fetch_response(
        messages=messages,
        response_text=response_text,
        user_text=current_user_text,
    ):
        return False, None, ""

    messages.append(
        build_contract_recovery_system_message(
            breach_type="web_research_title_only_after_fetch",
            diagnostics={},
        )
    )
    return (
        True,
        ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="web_research_title_only_after_fetch",
        ),
        response_text,
    )
