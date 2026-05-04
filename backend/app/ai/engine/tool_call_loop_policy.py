"""
Focused policies for the tool call loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage


@dataclass(frozen=True, slots=True)
class ToolCallLoopPolicy:
    messages_have_blocking_pending_interaction: Callable[[list[ChatMessage]], bool]
    first_incomplete_requested_family: Callable[[list[str], set[str]], str | None]
    allowed_tool_names_for_family: Callable[
        [str, list[ToolDefinition], dict[str, Any] | None],
        list[str],
    ]
    build_ordered_capability_hint: Callable[
        [list[str] | None, list[ToolDefinition], dict[str, Any] | None],
        str | None,
    ]
    needs_fetch_url_before_summary: Callable[[list[ChatMessage]], bool]
    apply_fetch_url_only_gate: Callable[
        [list[ChatMessage], list[ToolDefinition], list[ToolDefinition]],
        list[ToolDefinition],
    ]
    restrict_tools_to_names: Callable[
        [list[ToolDefinition], list[str] | None],
        list[ToolDefinition],
    ]


__all__ = ["ToolCallLoopPolicy"]
