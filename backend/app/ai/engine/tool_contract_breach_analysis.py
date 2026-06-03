"""Tool contract breach analysis helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse

from .tool_contract_retry_policies import build_post_tool_retry_policy
from .tool_policy_helpers import (
    collect_completed_turn_intents,
    detect_requested_turn_intents,
    extract_textual_tool_call_names,
    looks_like_tool_planning_leak,
)
from .types import ToolUsePolicy


def _extract_last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if str(getattr(message, "role", "") or "") != "user":
            continue
        text = str(getattr(message, "content", "") or "").strip()
        if text:
            return text
    return ""


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
    user_text = _extract_last_user_text(messages)
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
            },
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
        },
    )
