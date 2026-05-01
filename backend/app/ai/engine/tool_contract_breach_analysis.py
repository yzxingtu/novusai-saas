"""Tool contract breach analysis helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

from .contract_diagnostics_helpers import build_contract_recovery_system_message
from .tool_contract_retry_policies import build_post_tool_retry_policy
from .tool_policy_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
    extract_textual_tool_call_names,
    looks_like_tool_planning_leak,
    response_has_native_web_search_evidence,
)
from .turn_research_helpers import (
    extract_last_user_text,
    is_title_only_fetch_response,
)
from .types import ToolUsePolicy


def _native_web_completed_intents(requested_intents: list[str]) -> list[str]:
    return [
        intent
        for intent in requested_intents
        if intent in {"weather", "rail_ticket_research", "web_research"}
    ]


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
        and response_has_native_web_search_evidence(response)
    ):
        if not requested_intents:
            requested_intents = ["web_research"]
        if any(intent not in completed_intents for intent in requested_intents):
            completed_intents.update(_native_web_completed_intents(requested_intents))
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
