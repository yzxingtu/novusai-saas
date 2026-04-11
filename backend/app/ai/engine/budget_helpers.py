"""Budget-related response helpers extracted from BaseEngine."""

from __future__ import annotations

from app.ai.types import ChatMessage, ChatResponse


def budget_exit_response(total_tokens: int) -> ChatResponse:
    return ChatResponse(
        message=ChatMessage(role="assistant", content=""),
        total_tokens=total_tokens,
    )
