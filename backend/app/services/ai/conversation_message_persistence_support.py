"""
Support helpers for conversation message persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.types import ChatMessage


def _message_signature(message: ChatMessage | dict[str, Any]) -> tuple[Any, ...]:
    if isinstance(message, ChatMessage):
        return (
            message.role,
            str(message.content or ""),
            message.tool_call_id,
            message.tool_calls or [],
            message.attachments or [],
        )
    return (
        str(message.get("role") or ""),
        str(message.get("content") or ""),
        message.get("tool_call_id"),
        message.get("tool_calls") or [],
        message.get("attachments") or [],
    )


def resolve_new_message_start(
    *,
    result_messages: list[dict[str, Any]] | None,
    history_count: int,
    history_messages: list[ChatMessage] | None = None,
) -> int:
    if not result_messages:
        return 0

    if history_messages:
        history_signatures = [
            _message_signature(message) for message in history_messages[-history_count:]
        ]
        leading_system_count = 0
        for msg in result_messages:
            if msg.get("role") == "system":
                leading_system_count += 1
            else:
                break

        max_offset = min(leading_system_count, len(result_messages))
        for offset in range(max_offset + 1):
            end = offset + len(history_signatures)
            if end > len(result_messages):
                break
            window = [
                _message_signature(message) for message in result_messages[offset:end]
            ]
            if window == history_signatures:
                return end

    system_count = 0
    for msg_dict in result_messages:
        if msg_dict.get("role") == "system":
            system_count += 1
        else:
            break
    return min(len(result_messages), system_count + max(history_count, 0))


@dataclass(frozen=True)
class TurnPersistenceContext:
    rag_sources: Any
    turn_record_payload: dict[str, Any] | None
    turn_outcome: str | None
    turn_termination_reason: str | None
    turn_protocol_path: Any
    turn_selected_tools: list[str]
    turn_selected_skills: list[str]
    turn_context_sources: list[dict[str, Any]]
    memory_runtime_policy: dict[str, Any]
    effective_context_diagnostics: dict[str, Any]
    effective_last_run_summary: dict[str, Any]


def build_turn_persistence_context(
    service: Any,
    *,
    result: Any,
    context_diagnostics: dict[str, Any] | None,
    last_run_summary: dict[str, Any] | None,
) -> TurnPersistenceContext:
    rag_sources = getattr(result, "rag_sources", None)
    turn_meta = service._extract_turn_diagnostics_from_metadata(
        {
            "turn_record": getattr(result, "turn_record", None),
            "completion_reason": getattr(result, "completion_reason", None),
            "partial": bool(getattr(result, "partial", False)),
            "interrupted": bool(getattr(result, "interrupted", False)),
        }
    )
    turn_record_payload = turn_meta.get("turn_record")
    turn_outcome = turn_meta.get("turn_outcome")
    turn_termination_reason = turn_meta.get("termination_reason")
    turn_protocol_path = turn_meta.get("protocol_path")
    turn_selected_tools = turn_meta.get("selected_tool_names") or []
    turn_selected_skills = turn_meta.get("selected_skill_names") or []
    turn_context_sources = turn_meta.get("context_sources") or []
    raw_memory_runtime_policy = getattr(result, "memory_runtime_policy", None)
    if not isinstance(raw_memory_runtime_policy, dict):
        raw_memory_runtime_policy = getattr(result, "_memory_runtime_policy", None)
    memory_runtime_policy = (
        dict(raw_memory_runtime_policy or {})
        if isinstance(raw_memory_runtime_policy, dict)
        else {}
    )
    result_completion_reason = service._to_non_empty_str(
        getattr(result, "completion_reason", None)
    )
    if bool(getattr(result, "partial", False)) or bool(
        getattr(result, "interrupted", False)
    ):
        turn_outcome = "partial"
        if bool(getattr(result, "interrupted", False)) or (
            result_completion_reason == "interrupted"
        ):
            turn_termination_reason = "interrupted"
        elif result_completion_reason:
            turn_termination_reason = result_completion_reason

    effective_context_diagnostics = (
        dict(context_diagnostics) if isinstance(context_diagnostics, dict) else {}
    )
    if turn_outcome:
        effective_context_diagnostics["turn_outcome"] = turn_outcome
    if turn_termination_reason:
        effective_context_diagnostics["termination_reason"] = turn_termination_reason
    if turn_protocol_path:
        effective_context_diagnostics["protocol_path"] = turn_protocol_path
    for key in (
        "tool_planner",
        "execution_path",
        "active_intent_id",
        "continuation_source",
        "conversation_outcome",
        "intent_plan",
        "budget",
        "budget_status",
        "budget_exit_reason",
        "candidate_tool_names",
        "retry_events",
        "partial_exit_reason",
        "failure_kind",
        "provider_events",
        "contract_breach_type",
        "unfinished_intents",
        "leaked_tool_names",
        "last_tool_name",
        "last_page_key",
        "last_page_op",
        "interrupted_stage",
        "tool_loop_progress",
    ):
        value = turn_meta.get(key)
        if value:
            effective_context_diagnostics[key] = value
    if turn_selected_tools:
        effective_context_diagnostics["selected_tool_names"] = turn_selected_tools
    if turn_selected_skills:
        effective_context_diagnostics["selected_skill_names"] = turn_selected_skills
    if turn_context_sources:
        effective_context_diagnostics["context_sources"] = turn_context_sources
    if memory_runtime_policy:
        effective_context_diagnostics["memory_runtime_policy"] = memory_runtime_policy
        if memory_runtime_policy.get("external_context_polluted") is not None:
            effective_context_diagnostics["external_context_polluted"] = bool(
                memory_runtime_policy.get("external_context_polluted")
            )
        if memory_runtime_policy.get("external_context_reason"):
            effective_context_diagnostics["external_context_reason"] = (
                memory_runtime_policy.get("external_context_reason")
            )
    if turn_meta.get("tool_leak_detected"):
        effective_context_diagnostics["tool_leak_detected"] = True
    if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
        effective_context_diagnostics[
            "assistant_claimed_tool_call_without_tool_event"
        ] = True
    if turn_meta.get("recovered_via_retry") is not None:
        effective_context_diagnostics["recovered_via_retry"] = turn_meta[
            "recovered_via_retry"
        ]
    if turn_meta.get("sync_rescue") is not None:
        effective_context_diagnostics["sync_rescue"] = turn_meta["sync_rescue"]
    if turn_meta.get("should_record_call_log") is not None:
        effective_context_diagnostics["should_record_call_log"] = turn_meta[
            "should_record_call_log"
        ]
    effective_context_diagnostics.setdefault(
        "last_interrupted",
        bool(getattr(result, "interrupted", False))
        or turn_termination_reason == "interrupted",
    )

    effective_last_run_summary = (
        dict(last_run_summary) if isinstance(last_run_summary, dict) else {}
    )
    if turn_outcome:
        effective_last_run_summary["turn_outcome"] = turn_outcome
    if turn_termination_reason:
        effective_last_run_summary["termination_reason"] = turn_termination_reason
        effective_last_run_summary.setdefault(
            "completion_reason", turn_termination_reason
        )
    if turn_protocol_path:
        effective_last_run_summary["protocol_path"] = turn_protocol_path
    for key in (
        "tool_planner",
        "execution_path",
        "active_intent_id",
        "continuation_source",
        "conversation_outcome",
        "intent_plan",
        "budget",
        "budget_status",
        "budget_exit_reason",
        "candidate_tool_names",
        "retry_events",
        "partial_exit_reason",
        "failure_kind",
        "provider_events",
        "contract_breach_type",
        "unfinished_intents",
        "leaked_tool_names",
        "last_tool_name",
        "last_page_key",
        "last_page_op",
        "interrupted_stage",
        "tool_loop_progress",
    ):
        value = turn_meta.get(key)
        if value:
            effective_last_run_summary[key] = value
    if turn_selected_tools:
        effective_last_run_summary["selected_tool_names"] = turn_selected_tools
    if turn_selected_skills:
        effective_last_run_summary["selected_skill_names"] = turn_selected_skills
    if turn_context_sources:
        effective_last_run_summary["context_sources"] = turn_context_sources
    if memory_runtime_policy:
        effective_last_run_summary["memory_runtime_policy"] = memory_runtime_policy
        if memory_runtime_policy.get("external_context_polluted") is not None:
            effective_last_run_summary["external_context_polluted"] = bool(
                memory_runtime_policy.get("external_context_polluted")
            )
        if memory_runtime_policy.get("external_context_reason"):
            effective_last_run_summary["external_context_reason"] = (
                memory_runtime_policy.get("external_context_reason")
            )
    if turn_meta.get("tool_leak_detected"):
        effective_last_run_summary["tool_leak_detected"] = True
    if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
        effective_last_run_summary["assistant_claimed_tool_call_without_tool_event"] = (
            True
        )
    if turn_meta.get("recovered_via_retry") is not None:
        effective_last_run_summary["recovered_via_retry"] = turn_meta[
            "recovered_via_retry"
        ]
    if turn_meta.get("sync_rescue") is not None:
        effective_last_run_summary["sync_rescue"] = turn_meta["sync_rescue"]
    if turn_meta.get("should_record_call_log") is not None:
        effective_last_run_summary["should_record_call_log"] = turn_meta[
            "should_record_call_log"
        ]
    if (
        bool(getattr(result, "interrupted", False))
        or turn_termination_reason == "interrupted"
    ):
        effective_last_run_summary["interrupted"] = True

    return TurnPersistenceContext(
        rag_sources=rag_sources,
        turn_record_payload=turn_record_payload,
        turn_outcome=turn_outcome,
        turn_termination_reason=turn_termination_reason,
        turn_protocol_path=turn_protocol_path,
        turn_selected_tools=turn_selected_tools,
        turn_selected_skills=turn_selected_skills,
        turn_context_sources=turn_context_sources,
        memory_runtime_policy=memory_runtime_policy,
        effective_context_diagnostics=effective_context_diagnostics,
        effective_last_run_summary=effective_last_run_summary,
    )


__all__ = [
    "TurnPersistenceContext",
    "build_turn_persistence_context",
    "resolve_new_message_start",
]
