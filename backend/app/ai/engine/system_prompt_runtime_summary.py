"""Runtime summary injection and research continuation helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .system_prompt_capability_hints import build_runtime_capability_hint
from .types import ExecutionBudget, IntentPlan, ResearchContinuationContext


def inject_runtime_summary(
    *,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    continuation_context: ResearchContinuationContext | None = None,
    runtime_capability_summary: dict[str, Any] | None = None,
    ordered_requested_families: list[str] | None = None,
    skip_capability_summary: bool = False,
    intent_plan: list[IntentPlan] | None = None,
    execution_path: str | None = None,
    execution_budget: ExecutionBudget | None = None,
    include_knowledge_base_hint: bool = True,
    include_page_context_hint: bool = True,
    include_memory_hint: bool = True,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> bool:
    """Inject a one-shot runtime summary into the first system message."""
    _ = input_variables
    if not messages or messages[0].role != "system":
        return False

    allowed_tool_names = [t.name for t in tools]
    summarized_intents = intent_plan or []
    capability_summary_injected = False
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
        prompt_budget=(
            execution_budget.max_prompt_tokens if execution_budget is not None else 0
        ),
        tool_round_budget=(
            execution_budget.max_tool_rounds if execution_budget is not None else 0
        ),
        elapsed_budget_ms=(
            execution_budget.max_elapsed_ms if execution_budget is not None else 0
        ),
    )
    hint += "\n\n" + render_contract("tool_usage_rules")
    continuation_hint = build_research_continuation_hint(
        continuation_context,
        render_contract=render_contract,
    )
    if continuation_hint:
        hint += continuation_hint
    if not skip_capability_summary:
        runtime_capability_hint = build_runtime_capability_hint(
            runtime_capability_summary=runtime_capability_summary,
            include_knowledge_base_hint=include_knowledge_base_hint,
            include_page_context_hint=include_page_context_hint,
            include_memory_hint=include_memory_hint,
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
                "budget": (
                    execution_budget.snapshot() if execution_budget is not None else None
                ),
                "runtime_capability_summary": dict(runtime_capability_summary or {}),
                "skip_capability_summary": bool(skip_capability_summary),
                "include_knowledge_base_hint": bool(include_knowledge_base_hint),
                "include_page_context_hint": bool(include_page_context_hint),
                "include_memory_hint": bool(include_memory_hint),
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
    if not continuation or not continuation.active:
        return ""
    if continuation.family != "web_research":
        return ""

    target = continuation.research_target_text
    intro = (
        "This turn continues the previous external web research task."
        if continuation.origin == "continuation"
        else "This turn is an external web research task."
    )
    instruction_lines = (
        "\n".join(f"- {text}" for text in continuation.research_instruction_texts)
        if continuation.research_instruction_texts
        else "- (no recent research instructions captured)"
    )
    extra_guidance = (
        "Search-result tool messages in the conversation history are candidate URL lists. "
        "If fetched detail pages is 0 and fetch_url is available, pick candidate URLs from those lists and fetch them before analysis.\n"
        if continuation.fetched_url_count == 0
        else ""
    )
    return "\n\n" + render_contract(
        "research_state",
        intro=intro,
        target=target or "(same target as previous turn)",
        instruction_lines=instruction_lines,
        recent_queries=(
            ", ".join(continuation.recent_web_queries)
            if continuation.recent_web_queries
            else "(none)"
        ),
        search_query_count=continuation.search_query_count,
        fetched_url_count=continuation.fetched_url_count,
        extra_guidance=extra_guidance.strip(),
    )
