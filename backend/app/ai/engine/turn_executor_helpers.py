"""Helper functions extracted from TurnExecutor."""

from __future__ import annotations

from typing import Any

from app.ai.types import ChatMessage


def active_intent(state: Any) -> Any | None:
    for intent in state.intent_plan:
        if intent.status in {"completed", "failed", "skipped"}:
            continue
        if intent.family == "none" or not intent.requires_tools:
            continue
        return intent
    return None


def assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return sum(
        1
        for message in messages
        if message.role == "assistant" and bool(message.tool_calls)
    )


def register_tool_round_delta(
    state: Any,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = max(0, assistant_tool_round_count(messages) - before_count)
    for _round_idx in range(delta):
        state.register_tool_round()


def current_turn_start_index(messages: list[ChatMessage]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return 0


def current_turn_messages(
    messages: list[ChatMessage],
    *,
    start_index: int,
) -> list[ChatMessage]:
    if start_index <= 0:
        return list(messages)
    return list(messages[start_index:])

