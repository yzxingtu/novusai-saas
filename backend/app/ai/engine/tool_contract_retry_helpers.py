"""Tool contract retry and logging helpers extracted from BaseEngine."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

from .base_helpers import truncate_preview as _truncate_preview_impl
from .contract_diagnostics_helpers import build_contract_recovery_system_message
from .tool_policy_helpers import (
    allowed_tool_names_for_families,
    build_required_policy_for_family,
    collect_completed_turn_intents,
    detect_requested_turn_intents,
    extract_textual_tool_call_names,
    looks_like_explicit_web_research_request,
    looks_like_tool_planning_leak,
    response_denies_family_capability,
    response_has_native_web_search_evidence,
    tool_family_for_name,
    tool_semantic_family,
)
from .turn_research_helpers import (
    collect_web_research_evidence,
    extract_last_user_text,
    is_title_only_fetch_response,
)
from .types import ResearchContinuationContext, ToolUsePolicy

logger = LogManager.get_logger("ai.engine")


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
        if intent == "page_summary":
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


def analyze_post_tool_contract_breach(
    *,
    messages: list[ChatMessage],
    response: ChatResponse,
    current_policy: ToolUsePolicy,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
    if response.tool_calls:
        return None, None, {}

    response_text = (response.message.content or "").strip()
    if not response_text:
        return None, None, {}

    leaked_tool_names = extract_textual_tool_call_names(response_text, tools)
    planning_leak = looks_like_tool_planning_leak(response_text, tools)
    user_text = extract_last_user_text(messages)
    requested_intents = detect_requested_turn_intents(
        user_text,
        tools=tools,
        input_variables=input_variables,
    )
    completed_intents = collect_completed_turn_intents(
        messages,
        tools=tools,
        input_variables=input_variables,
    )
    native_web_search_evidence = False
    if (
        current_policy.family == "web_research"
        and requested_intents
        and any(intent not in completed_intents for intent in requested_intents)
        and response_has_native_web_search_evidence(response)
    ):
        completed_intents.update(requested_intents)
        native_web_search_evidence = True
    unfinished_intents = [
        intent for intent in requested_intents if intent not in completed_intents
    ]

    if leaked_tool_names or planning_leak:
        return (
            "assistant_claimed_tool_call_without_tool_event",
            build_post_tool_retry_policy(
                breach_type="assistant_claimed_tool_call_without_tool_event",
                tools=tools,
                input_variables=input_variables,
                current_policy=current_policy,
                leaked_tool_names=leaked_tool_names,
                unfinished_intents=unfinished_intents,
            ),
            {
                "tool_leak_detected": True,
                "assistant_claimed_tool_call_without_tool_event": True,
                "leaked_tool_names": leaked_tool_names,
                "requested_intents": requested_intents,
                "completed_intents": sorted(completed_intents),
                "unfinished_intents": unfinished_intents,
                "native_web_search_evidence": native_web_search_evidence,
            },
        )

    if unfinished_intents:
        return (
            "unfinished_multi_intent_reply",
            build_post_tool_retry_policy(
                breach_type="unfinished_multi_intent_reply",
                tools=tools,
                input_variables=input_variables,
                current_policy=current_policy,
                unfinished_intents=unfinished_intents,
            ),
            {
                "tool_leak_detected": False,
                "leaked_tool_names": [],
                "requested_intents": requested_intents,
                "completed_intents": sorted(completed_intents),
                "unfinished_intents": unfinished_intents,
                "native_web_search_evidence": native_web_search_evidence,
            },
        )

    tool_names = {tool.name for tool in tools}
    if (
        current_policy.family == "web_research"
        and {"web_search", "fetch_url"} <= tool_names
        and is_title_only_fetch_response(
            messages=messages,
            response_text=response_text,
            user_text=user_text,
        )
    ):
        diagnostics = {
            "tool_leak_detected": False,
            "assistant_claimed_tool_call_without_tool_event": False,
            "leaked_tool_names": [],
            "requested_intents": requested_intents,
            "completed_intents": ["web_research"],
            "unfinished_intents": [],
            "native_web_search_evidence": native_web_search_evidence,
        }
        messages.append(
            build_contract_recovery_system_message(
                breach_type="web_research_title_only_after_fetch",
                diagnostics=diagnostics,
            )
        )
        return (
            "web_research_title_only_after_fetch",
            ToolUsePolicy(
                family="none",
                mode="none",
                allowed_tool_names=[],
                retry_on_contract_breach=False,
                reason="web_research_title_only_after_fetch",
            ),
            diagnostics,
        )

    return (
        None,
        None,
        {
            "tool_leak_detected": False,
            "assistant_claimed_tool_call_without_tool_event": False,
            "leaked_tool_names": [],
            "requested_intents": requested_intents,
            "completed_intents": sorted(completed_intents),
            "unfinished_intents": [],
            "native_web_search_evidence": native_web_search_evidence,
        },
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


def collect_tool_family_evidence(messages: list[ChatMessage]) -> dict[str, int]:
    counts = {"web_research": 0, "weather": 0, "page_ops": 0}
    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            if tool_call.get("success") is not True:
                continue
            family = tool_family_for_name(
                str(
                    (tool_call.get("function") or {}).get("name")
                    or tool_call.get("name")
                    or ""
                ).strip()
            )
            if family in counts:
                counts[family] += 1
    return counts


def log_tool_contract_diagnostics(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
    conversation_id: int | None,
    breach_type: str,
    retry_result: str,
    continuation: ResearchContinuationContext | None = None,
    truncate_preview,
) -> None:
    if not tools:
        return

    response_text = (response.message.content or "").strip() if response is not None else ""
    current_user_text = extract_last_user_text(messages)
    target_text = (
        continuation.research_target_text
        if continuation and continuation.research_target_text
        else ""
    )
    trace_id = ""
    try:
        from app.middleware.trace import trace_id_var

        trace_id = trace_id_var.get() or ""
    except Exception:
        trace_id = ""

    family_evidence = collect_tool_family_evidence(messages)
    search_queries, fetched_urls = collect_web_research_evidence(messages)
    status = {
        "retrying": "policy_retry_started",
        "succeeded": "policy_retry_succeeded",
        "failed": "policy_retry_failed",
        "logged": "policy_logged_only",
        "no_retry": "policy_loaded_but_no_retry",
    }.get(retry_result, retry_result or "policy_unknown")
    logger.warning(
        "Tool contract breach: status={} type={} retry_result={} agent_id={} conversation_id={} trace_id={} family={} tool_choice={} allowed_tool_names={} current_user_text={} response_preview={} research_target={} family_evidence={} search_query_count={} fetched_url_count={}",
        status,
        breach_type,
        retry_result,
        getattr(agent, "id", None),
        conversation_id,
        trace_id,
        policy.family,
        policy.mode,
        policy.allowed_tool_names,
        truncate_preview(current_user_text),
        truncate_preview(response_text),
        truncate_preview(target_text),
        family_evidence,
        len(search_queries),
        len(fetched_urls),
    )


def log_web_research_contract_diagnostics(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse,
    tools: list[ToolDefinition],
    continuation: ResearchContinuationContext | None,
    conversation_id: int | None,
    truncate_preview,
) -> None:
    if not tools:
        return

    tool_names = [tool.name for tool in tools]
    if "web_search" not in tool_names:
        return

    response_text = (response.message.content or "").strip()
    search_queries, fetched_urls = collect_web_research_evidence(messages)
    search_count = len(search_queries)
    fetch_count = len(fetched_urls)

    def _emit(breach_type: str) -> None:
        log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=build_required_policy_for_family(
                "web_research",
                tools,
                None,
                reason=breach_type,
            ),
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result="logged",
            continuation=continuation,
            truncate_preview=truncate_preview,
        )

    if not continuation or not continuation.active:
        return
    if response.tool_calls or not response_text:
        return

    if search_count == 0:
        _emit("web_research_capability_denial_or_no_tool_use")
        return

    if "fetch_url" in tool_names and search_count > 0 and fetch_count == 0:
        _emit("web_research_summary_without_fetch")
        return
    if is_title_only_fetch_response(
        messages=messages,
        response_text=response_text,
        user_text=extract_last_user_text(messages),
    ):
        _emit("web_research_title_only_after_fetch")


def log_tool_contract_diagnostics_default(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
    conversation_id: int | None,
    breach_type: str,
    retry_result: str,
    continuation: ResearchContinuationContext | None = None,
) -> None:
    log_tool_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=tools,
        policy=policy,
        conversation_id=conversation_id,
        breach_type=breach_type,
        retry_result=retry_result,
        continuation=continuation,
        truncate_preview=_truncate_preview_impl,
    )


def log_web_research_contract_diagnostics_default(
    *,
    agent: Any,
    messages: list[ChatMessage],
    response: ChatResponse,
    tools: list[ToolDefinition],
    continuation: ResearchContinuationContext | None,
    conversation_id: int | None,
) -> None:
    log_web_research_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=tools,
        continuation=continuation,
        conversation_id=conversation_id,
        truncate_preview=_truncate_preview_impl,
    )
