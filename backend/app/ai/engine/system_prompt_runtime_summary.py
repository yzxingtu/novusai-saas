"""Runtime summary injection with a bounded prompt surface."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .system_prompt_capability_hints import (
    build_runtime_capability_hint,
    resolve_live_turn_selected_skill_names,
)
from .types import IntentPlan, ResearchContinuationContext


def inject_runtime_summary(
    *,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    runtime_capability_summary: dict[str, Any] | None = None,
    ordered_requested_families: list[str] | None = None,
    skip_capability_summary: bool = False,
    intent_plan: list[IntentPlan] | None = None,
    execution_path: str | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> bool:
    """Inject a compact one-shot runtime summary into the first system message."""
    if not messages or messages[0].role != "system":
        return False

    allowed_tool_names = [tool.name for tool in tools]
    summarized_intents = intent_plan or []
    intent_summary = (
        ", ".join(intent.user_visible_label for intent in summarized_intents[:4])
        or ", ".join(ordered_requested_families or [])
        or "direct_reply"
    )

    hint = "\n\n" + render_contract(
        "tool_runtime_summary",
        execution_path=execution_path or "fast",
        intent_summary=intent_summary,
        allowed_tools=", ".join(allowed_tool_names) or "none",
    )
    live_turn_selected_skill_names = resolve_live_turn_selected_skill_names(
        runtime_capability_summary=runtime_capability_summary,
    )

    capability_summary_injected = False
    if not skip_capability_summary:
        runtime_capability_hint = build_runtime_capability_hint(
            runtime_capability_summary=runtime_capability_summary,
            render_contract=render_contract,
        )
        if runtime_capability_hint:
            hint += runtime_capability_hint
            capability_summary_injected = True

    signature = hashlib.sha1(
        json.dumps(
            {
                "tools": allowed_tool_names,
                "intent_summary": intent_summary,
                "execution_path": execution_path or "fast",
                "selected_skill_names": live_turn_selected_skill_names,
                "skip_capability_summary": bool(skip_capability_summary),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    metadata = dict(messages[0].metadata or {})
    if metadata.get("runtime_summary_signature") == signature:
        return capability_summary_injected

    metadata["runtime_summary_signature"] = signature
    messages[0] = ChatMessage(
        role="system",
        content=messages[0].content + hint,
        metadata=metadata,
    )
    return capability_summary_injected


def build_research_continuation_hint(
    continuation: ResearchContinuationContext | None,
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    del continuation, render_contract
    return ""
