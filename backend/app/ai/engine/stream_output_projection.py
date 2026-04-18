# FROZEN: do not add new dependencies
"""Pure-ish stream output and round-limit helpers."""

from __future__ import annotations

from typing import Any

from app.ai.page_locale import resolve_page_locale
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage, ChatResponse
from app.core.i18n import _

from .final_output_policy import is_trusted_assistant_final_output_source


def tool_loop_round_limit(handler: Any, tools: list[ToolDefinition]) -> int:
    budget = getattr(handler.prep, "execution_budget", None)
    if budget is not None and budget.max_tool_rounds > 0:
        return (
            int(budget.max_tool_rounds)
            + max(1, int(budget.max_retry_per_intent or 0))
            + 1
        )
    tool_count = len(getattr(handler.prep, "all_tools", None) or tools or [])
    intent_count = len(getattr(handler.prep, "intent_plan", None) or [])
    return max(3, min(6, tool_count + max(1, intent_count) + 1))


def build_text_round_response(
    *,
    content: str,
    reasoning_content: str,
    total_tokens: int,
) -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content or None,
        ),
        total_tokens=total_tokens,
        finish_reason="stop",
    )


def last_visible_assistant_content(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role != "assistant" or message.tool_calls:
            continue
        content = str(message.content or "").strip()
        if content:
            return content
    return ""


def assistant_message_has_content(
    messages: list[ChatMessage],
    content: str,
) -> bool:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return False
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        if str(message.content or "").strip() == normalized_content:
            return True
    return False


def current_turn_has_finalized_output(
    *,
    messages: list[ChatMessage],
    streamed_output: str,
    finalized_output: str,
) -> bool:
    _ = streamed_output
    if not finalized_output:
        return False
    return assistant_message_has_content(messages, finalized_output)


def should_replay_finalized_output(
    *,
    streamed_output: str,
    finalized_output: str,
) -> bool:
    if not finalized_output:
        return False
    return streamed_output != finalized_output


def is_streamed_prefix_expansion(
    *,
    streamed_output: str,
    finalized_output: str,
) -> bool:
    if not streamed_output or not finalized_output:
        return False
    if streamed_output == finalized_output:
        return False
    if len(streamed_output) <= len(finalized_output):
        return False
    return streamed_output.startswith(finalized_output)


def should_preserve_streamed_assistant_output(
    *,
    final_output_source: str | None,
    streamed_output: str,
    finalized_output: str,
) -> bool:
    if not is_trusted_assistant_final_output_source(final_output_source):
        return False
    return is_streamed_prefix_expansion(
        streamed_output=streamed_output,
        finalized_output=finalized_output,
    )


def resolve_budget_exit_locale(input_variables: dict[str, Any] | None) -> str:
    return resolve_page_locale(input_variables)


def build_budget_exit_fallback_output(
    handler: Any,
    *,
    tool_results: list[Any],
) -> str:
    locale = resolve_budget_exit_locale(
        getattr(handler.request, "input_variables", None)
    )
    del tool_results
    return _("ai.stream.partial.budget_exit", locale=locale)
