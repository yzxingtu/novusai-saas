"""
Helpers for BaseEngine tool-loop session state and follow-up policy decisions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager

from .intent_plan_accessors import resolve_intent_plan_from_input_variables
from .intent_planner import IntentPlanner
from .types import ExecutionBudget, ResearchContinuationContext, ToolUsePolicy

logger = LogManager.get_logger("ai.engine")


@dataclass(slots=True)
class ToolLoopSession:
    current_response: ChatResponse
    tools_full: list[ToolDefinition]
    all_tools_full: list[ToolDefinition]
    effective_policy: ToolUsePolicy
    ordered_requested_families: list[str]
    has_fetch_url_in_toolset: bool
    total_tokens: int
    completion_tokens_used: int
    tracked_tool_rounds: int
    tracked_tool_result_bytes: int
    all_tool_results: list[ToolResult] = field(default_factory=list)
    completed_families: set[str] = field(default_factory=set)
    issued_progress_hint_keys: set[str] = field(default_factory=set)
    forced_tool_names: list[str] | None = None
    fetch_gate_message_sent: bool = False


def build_tool_loop_session(
    *,
    response: ChatResponse,
    tools: list[ToolDefinition],
    all_tools: list[ToolDefinition] | None,
    request: Any,
    continuation_context: ResearchContinuationContext | None,
    tool_use_policy: ToolUsePolicy | None,
    execution_budget: ExecutionBudget | None,
    starting_total_tokens: int | None,
    starting_completion_tokens: int | None,
    ordered_requested_families_from_intents: Callable[..., list[str]],
) -> ToolLoopSession:
    tools_full = list(tools)
    resolved_all_tools = list(all_tools or tools_full)
    effective_policy = tool_use_policy or request.tool_use_policy or ToolUsePolicy()
    ordered_requested_families = ordered_requested_families_from_intents(
        intents=IntentPlanner.plan_turn(
            messages=request.messages,
            tools=resolved_all_tools,
            input_variables=request.input_variables,
            continuation_context=continuation_context,
        ),
    )
    return ToolLoopSession(
        current_response=response,
        tools_full=tools_full,
        all_tools_full=resolved_all_tools,
        effective_policy=effective_policy,
        ordered_requested_families=ordered_requested_families,
        has_fetch_url_in_toolset=any(
            tool.name == "fetch_url" for tool in resolved_all_tools
        ),
        total_tokens=(
            int(starting_total_tokens)
            if starting_total_tokens is not None
            else int(response.total_tokens or 0)
        ),
        completion_tokens_used=(
            int(starting_completion_tokens)
            if starting_completion_tokens is not None
            else int(
                response.output_tokens
                if response.output_tokens is not None
                else (response.total_tokens or 0)
            )
        ),
        tracked_tool_rounds=int(
            execution_budget.tool_rounds_used if execution_budget is not None else 0
        ),
        tracked_tool_result_bytes=int(
            execution_budget.tool_result_bytes_used
            if execution_budget is not None
            else 0
        ),
    )


def sync_sandbox_runtime_model_info(
    *,
    sandbox: Any,
    response: ChatResponse | None,
) -> None:
    if sandbox is None or not hasattr(sandbox, "set_runtime_model_info"):
        return
    metadata = getattr(response, "metadata", None)
    runtime_model_info = (
        metadata.get("runtime_model_info") if isinstance(metadata, dict) else None
    )
    sandbox.set_runtime_model_info(runtime_model_info)


def prepare_round_tools_for_followup(
    *,
    session: ToolLoopSession,
    messages: list[ChatMessage],
    processor: Any,
    all_tools: list[ToolDefinition] | None,
    needs_fetch_url_before_summary: Callable[[list[ChatMessage]], bool],
    apply_fetch_url_only_gate: Callable[
        [list[ChatMessage], list[ToolDefinition], list[ToolDefinition]],
        list[ToolDefinition],
    ],
    restrict_tools_to_names: Callable[
        [list[ToolDefinition], list[str] | None],
        list[ToolDefinition],
    ],
) -> list[ToolDefinition]:
    if needs_fetch_url_before_summary(messages) and not session.fetch_gate_message_sent:
        messages.append(
            ChatMessage(
                role="system",
                content=render_prompt_contract("fetch_url_gate"),
            )
        )
        session.fetch_gate_message_sent = True
    resolved_all_tools = list(all_tools or session.all_tools_full)
    round_tools = apply_fetch_url_only_gate(
        messages,
        session.tools_full,
        resolved_all_tools,
    )
    round_tools = restrict_tools_to_names(round_tools, session.forced_tool_names)
    processor.tools = round_tools
    return round_tools


def build_round_policy(
    *,
    session: ToolLoopSession,
    round_tools: list[ToolDefinition],
) -> ToolUsePolicy:
    round_tool_names = [tool.name for tool in round_tools]
    if not round_tool_names:
        return session.effective_policy
    if round_tool_names == list(session.effective_policy.allowed_tool_names or []):
        return session.effective_policy
    reason_suffix = (
        "forced_tool_names" if session.forced_tool_names else "round_tool_subset"
    )
    return ToolUsePolicy(
        family=session.effective_policy.family,
        mode=session.effective_policy.mode,
        allowed_tool_names=round_tool_names,
        retry_on_contract_breach=session.effective_policy.retry_on_contract_breach,
        reason=(
            f"{session.effective_policy.reason}|{reason_suffix}"
            if session.effective_policy.reason
            else reason_suffix
        ),
    )


def _target_page_recovery_intent(
    intent_plan: list[Any],
    *,
    intent_kind: str,
) -> Any | None:
    unfinished = [
        intent
        for intent in intent_plan
        if getattr(intent, "family", None) == "page_ops"
        and getattr(intent, "status", None) not in {"completed", "failed", "skipped"}
    ]
    for intent in unfinished:
        if str(getattr(intent, "kind", "") or "").strip() == intent_kind:
            return intent
    if unfinished:
        return unfinished[0]
    for intent in intent_plan:
        if (
            getattr(intent, "family", None) == "page_ops"
            and str(getattr(intent, "kind", "") or "").strip() == intent_kind
        ):
            return intent
    return None


def _project_page_recovery_into_runtime_intent_plan(
    *,
    input_variables: dict[str, Any] | None,
    recovery_diagnostics: dict[str, Any],
    recovery_tool_names: list[str],
) -> None:
    if not isinstance(input_variables, dict) or not recovery_tool_names:
        return
    intent_plan = resolve_intent_plan_from_input_variables(input_variables)
    if not intent_plan:
        return

    target_intent_kind = str(recovery_diagnostics.get("intent_kind") or "").strip()
    if not target_intent_kind:
        return
    target_intent = _target_page_recovery_intent(
        intent_plan,
        intent_kind=target_intent_kind,
    )
    if target_intent is None:
        return

    page_workflow_progress = (
        dict(recovery_diagnostics.get("page_workflow_progress") or {})
        if isinstance(recovery_diagnostics.get("page_workflow_progress"), dict)
        else {}
    )
    if not page_workflow_progress:
        return

    metadata = dict(getattr(target_intent, "metadata", {}) or {})
    metadata["page_workflow_stage"] = str(
        recovery_diagnostics.get("workflow_stage")
        or metadata.get("page_workflow_stage")
        or ""
    ).strip()
    metadata["page_workflow_phase"] = str(
        recovery_diagnostics.get("workflow_phase")
        or metadata.get("page_workflow_phase")
        or ""
    ).strip()
    metadata["page_workflow_goal"] = str(
        recovery_diagnostics.get("workflow_goal")
        or metadata.get("page_workflow_goal")
        or ""
    ).strip()
    if isinstance(recovery_diagnostics.get("workflow_state"), dict):
        metadata["page_workflow_state"] = dict(
            recovery_diagnostics.get("workflow_state") or {}
        )
    if isinstance(recovery_diagnostics.get("workflow_completion"), dict):
        metadata["page_workflow_completion"] = dict(
            recovery_diagnostics.get("workflow_completion") or {}
        )
    metadata["page_workflow_progress"] = page_workflow_progress
    metadata["page_workflow_continuation_required"] = bool(
        page_workflow_progress.get("continuation_required", True)
    )
    metadata["page_no_progress_recovery"] = {
        "reason": str(recovery_diagnostics.get("reason") or "").strip(),
        "allowed_tool_names": list(recovery_tool_names),
        "round_tool_names": list(recovery_diagnostics.get("round_tool_names") or []),
    }
    target_intent.metadata = metadata
    target_intent.status = "pending"
    target_intent.cached_result = None
    target_intent.completed_by_tool_names = []

    runtime_intent_facts = input_variables.get("_runtime_intent_facts")
    if not isinstance(runtime_intent_facts, dict):
        runtime_intent_facts = {}
        input_variables["_runtime_intent_facts"] = runtime_intent_facts
    runtime_intent_facts["active_intent_kind"] = target_intent.kind
    input_variables["_runtime_intent_plan"] = [
        intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
        for intent in intent_plan
    ]


def append_ordered_progress_hint(
    *,
    session: ToolLoopSession,
    messages: list[ChatMessage],
    all_tools: list[ToolDefinition] | None,
    input_variables: dict[str, Any] | None,
    build_ordered_capability_hint: Callable[
        [list[str], list[ToolDefinition], dict[str, Any] | None],
        str | None,
    ],
) -> None:
    if len(session.ordered_requested_families) <= 1:
        return
    if not session.completed_families:
        return
    remaining_families = [
        family
        for family in session.ordered_requested_families
        if family not in session.completed_families
    ]
    if not remaining_families:
        return
    done_names = [
        family
        for family in session.ordered_requested_families
        if family in session.completed_families
    ]
    hint_key = f"{'->'.join(done_names)}|{'->'.join(remaining_families)}"
    if hint_key in session.issued_progress_hint_keys:
        return
    session.issued_progress_hint_keys.add(hint_key)
    hint = build_ordered_capability_hint(
        session.ordered_requested_families,
        list(all_tools or session.all_tools_full),
        input_variables,
    )
    if not hint:
        return
    messages.append(
        ChatMessage(
            role="system",
            content=(
                f"{hint}\n"
                f"Completed families: {', '.join(done_names)}.\n"
                f"Next family to prioritize: {remaining_families[0]}."
            ),
        )
    )


def apply_round_recovery_and_focus(
    *,
    session: ToolLoopSession,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    round_tool_results: list[ToolResult],
    all_tools: list[ToolDefinition] | None,
    input_variables: dict[str, Any] | None,
    build_page_no_progress_recovery: Callable[
        ...,
        tuple[list[str], dict[str, Any]],
    ],
    messages_have_blocking_pending_interaction: Callable[[list[ChatMessage]], bool],
    first_incomplete_requested_family: Callable[[list[str], set[str]], str | None],
    allowed_tool_names_for_family: Callable[
        [str, list[ToolDefinition], dict[str, Any] | None],
        list[str],
    ],
    conversation_id: int | None,
) -> None:
    resolved_all_tools = list(all_tools or session.all_tools_full)
    recovery_tool_names, recovery_diagnostics = build_page_no_progress_recovery(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=round_tool_results,
        tools=resolved_all_tools,
        input_variables=input_variables,
    )
    if recovery_tool_names:
        session.forced_tool_names = recovery_tool_names
        _project_page_recovery_into_runtime_intent_plan(
            input_variables=input_variables,
            recovery_diagnostics=recovery_diagnostics,
            recovery_tool_names=recovery_tool_names,
        )
        logger.info(
            "Activated page-workflow recovery subset after no-progress page round: conversation_id={} diagnostics={}",
            conversation_id,
            recovery_diagnostics,
        )
        return
    if len(session.ordered_requested_families) > 1:
        if messages_have_blocking_pending_interaction(messages):
            return
        focus = first_incomplete_requested_family(
            session.ordered_requested_families,
            session.completed_families,
        )
        session.forced_tool_names = (
            None
            if focus is None
            else allowed_tool_names_for_family(
                focus,
                resolved_all_tools,
                input_variables,
            )
        )
        return
    if session.forced_tool_names:
        session.forced_tool_names = None


__all__ = [
    "ToolLoopSession",
    "append_ordered_progress_hint",
    "apply_round_recovery_and_focus",
    "build_round_policy",
    "build_tool_loop_session",
    "prepare_round_tools_for_followup",
    "sync_sandbox_runtime_model_info",
]
