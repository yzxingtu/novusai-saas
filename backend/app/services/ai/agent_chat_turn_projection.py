"""
Agent chat turn diagnostics projection helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)

TurnMetaExtractor = Callable[[dict[str, Any]], dict[str, Any]]
DEFAULT_TURN_META_EXTRACTOR: TurnMetaExtractor = (
    ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata
)


def extract_turn_meta_from_result(
    result: ExecutionResult,
    *,
    extractor: TurnMetaExtractor = DEFAULT_TURN_META_EXTRACTOR,
) -> dict[str, Any]:
    return extractor(
        {
            "turn_record": getattr(result, "turn_record", None),
            "completion_reason": getattr(result, "completion_reason", None),
            "partial": bool(getattr(result, "partial", False)),
            "interrupted": bool(getattr(result, "interrupted", False)),
        }
    )


def build_context_diagnostics(
    result: ExecutionResult,
    *,
    interaction_mode_effective: str,
    extractor: TurnMetaExtractor = DEFAULT_TURN_META_EXTRACTOR,
) -> dict[str, Any]:
    del interaction_mode_effective
    turn_meta = extract_turn_meta_from_result(result, extractor=extractor)
    payload: dict[str, Any] = {
        "estimated_tokens": result.total_tokens,
        "context_compacted": bool(result.context_compacted),
        "compact_summary_present": bool(result.context_compacted),
        "memory_recalled": bool(result.memory_recalled),
        "memory_flush_triggered": bool(result.memory_flush_triggered),
        "prune_stats": result.prune_stats,
        "rag_source_kinds": list(result.rag_source_kinds or []),
        "last_interrupted": bool(result.interrupted),
        "tool_planner": result.tool_planner,
    }
    if turn_meta.get("turn_outcome"):
        payload["turn_outcome"] = turn_meta["turn_outcome"]
    if turn_meta.get("termination_reason"):
        payload["termination_reason"] = turn_meta["termination_reason"]
    if turn_meta.get("protocol_path"):
        payload["protocol_path"] = turn_meta["protocol_path"]
    if turn_meta.get("active_intent_id"):
        payload["active_intent_id"] = turn_meta["active_intent_id"]
    if turn_meta.get("continuation_source"):
        payload["continuation_source"] = turn_meta["continuation_source"]
    if turn_meta.get("conversation_outcome"):
        payload["conversation_outcome"] = turn_meta["conversation_outcome"]
    if turn_meta.get("selected_tool_names"):
        payload["selected_tool_names"] = turn_meta["selected_tool_names"]
    if turn_meta.get("selected_skill_names"):
        payload["selected_skill_names"] = turn_meta["selected_skill_names"]
    if turn_meta.get("turn_skill_activation"):
        payload["turn_skill_activation"] = turn_meta["turn_skill_activation"]
    if turn_meta.get("context_sources"):
        payload["context_sources"] = turn_meta["context_sources"]
    if turn_meta.get("contract_breach_type"):
        payload["contract_breach_type"] = turn_meta["contract_breach_type"]
    if turn_meta.get("tool_leak_detected"):
        payload["tool_leak_detected"] = True
    if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
        payload["assistant_claimed_tool_call_without_tool_event"] = True
    if turn_meta.get("unfinished_intents"):
        payload["unfinished_intents"] = turn_meta["unfinished_intents"]
    if turn_meta.get("leaked_tool_names"):
        payload["leaked_tool_names"] = turn_meta["leaked_tool_names"]
    if turn_meta.get("recovered_via_retry") is not None:
        payload["recovered_via_retry"] = turn_meta["recovered_via_retry"]
    if turn_meta.get("last_tool_name"):
        payload["last_tool_name"] = turn_meta["last_tool_name"]
    if turn_meta.get("interrupted_stage"):
        payload["interrupted_stage"] = turn_meta["interrupted_stage"]
    if turn_meta.get("tool_loop_progress"):
        payload["tool_loop_progress"] = turn_meta["tool_loop_progress"]
    return payload


def build_last_run_summary(
    result: ExecutionResult,
    *,
    interaction_mode_effective: str,
    downgrade_reason: str | None,
    extractor: TurnMetaExtractor = DEFAULT_TURN_META_EXTRACTOR,
) -> dict[str, Any]:
    del interaction_mode_effective, downgrade_reason
    turn_meta = extract_turn_meta_from_result(result, extractor=extractor)
    payload: dict[str, Any] = {
        "duration_ms": result.duration_ms,
        "runtime_model_name": result.runtime_model_name,
        "runtime_provider_name": result.runtime_provider_name,
        "success": bool(result.success),
        "total_tokens": result.total_tokens,
        "tool_planner": result.tool_planner,
    }
    completion_reason = (
        turn_meta.get("termination_reason")
        or str(getattr(result, "completion_reason", "") or "").strip()
        or None
    )
    if completion_reason:
        payload["completion_reason"] = completion_reason
        payload["termination_reason"] = completion_reason
    if turn_meta.get("turn_outcome"):
        payload["turn_outcome"] = turn_meta["turn_outcome"]
    if turn_meta.get("protocol_path"):
        payload["protocol_path"] = turn_meta["protocol_path"]
    if turn_meta.get("active_intent_id"):
        payload["active_intent_id"] = turn_meta["active_intent_id"]
    if turn_meta.get("continuation_source"):
        payload["continuation_source"] = turn_meta["continuation_source"]
    if turn_meta.get("conversation_outcome"):
        payload["conversation_outcome"] = turn_meta["conversation_outcome"]
    if turn_meta.get("selected_tool_names"):
        payload["selected_tool_names"] = turn_meta["selected_tool_names"]
    if turn_meta.get("selected_skill_names"):
        payload["selected_skill_names"] = turn_meta["selected_skill_names"]
    if turn_meta.get("turn_skill_activation"):
        payload["turn_skill_activation"] = turn_meta["turn_skill_activation"]
    if turn_meta.get("context_sources"):
        payload["context_sources"] = turn_meta["context_sources"]
    if turn_meta.get("contract_breach_type"):
        payload["contract_breach_type"] = turn_meta["contract_breach_type"]
    if turn_meta.get("tool_leak_detected"):
        payload["tool_leak_detected"] = True
    if turn_meta.get("assistant_claimed_tool_call_without_tool_event"):
        payload["assistant_claimed_tool_call_without_tool_event"] = True
    if turn_meta.get("unfinished_intents"):
        payload["unfinished_intents"] = turn_meta["unfinished_intents"]
    if turn_meta.get("leaked_tool_names"):
        payload["leaked_tool_names"] = turn_meta["leaked_tool_names"]
    if turn_meta.get("recovered_via_retry") is not None:
        payload["recovered_via_retry"] = turn_meta["recovered_via_retry"]
    if turn_meta.get("last_tool_name"):
        payload["last_tool_name"] = turn_meta["last_tool_name"]
    if turn_meta.get("interrupted_stage"):
        payload["interrupted_stage"] = turn_meta["interrupted_stage"]
    if turn_meta.get("tool_loop_progress"):
        payload["tool_loop_progress"] = turn_meta["tool_loop_progress"]
    return payload
