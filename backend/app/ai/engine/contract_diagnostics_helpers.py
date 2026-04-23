"""Contract breach diagnostics helpers extracted from BaseEngine."""

from __future__ import annotations

from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.runtime.types import TurnRecord
from app.ai.types import ChatMessage


def build_contract_recovery_system_message(
    *,
    breach_type: str,
    diagnostics: dict[str, Any],
    render_contract=render_prompt_contract,
) -> ChatMessage:
    leaked_tool_names = diagnostics.get("leaked_tool_names") or []
    unfinished_intents = diagnostics.get("unfinished_intents") or []
    completed_intents = diagnostics.get("completed_intents") or []
    breach_guidance = ""
    if breach_type in {
        "leaked_textual_tool_call",
        "assistant_claimed_tool_call_without_tool_event",
    }:
        breach_guidance = render_contract("contract_recovery_leak_guidance") + "\n"
    elif breach_type == "web_research_title_only_after_fetch":
        breach_guidance = render_contract("contract_recovery_web_research_guidance") + "\n"
    unfinished_line = ""
    if unfinished_intents:
        unfinished_line = f"Unfinished requested intents: {', '.join(str(item) for item in unfinished_intents)}.\n"
    completed_line = ""
    if completed_intents:
        completed_line = (
            "Already completed intents with real tool evidence: "
            f"{', '.join(str(item) for item in completed_intents)}.\n"
        )
    leaked_line = ""
    if leaked_tool_names:
        leaked_line = (
            "Leaked tool names or tool-output markers detected: "
            f"{', '.join(str(item) for item in leaked_tool_names)}.\n"
        )
    return ChatMessage(
        role="system",
        content=render_contract(
            "contract_recovery",
            breach_guidance=breach_guidance,
            unfinished_line=unfinished_line,
            completed_line=completed_line,
            leaked_line=leaked_line,
        ),
        internal_only=True,
    )


def merge_contract_diagnostics_into_turn_record(
    turn_record: TurnRecord | dict[str, Any] | None,
    *,
    breach_type: str | None,
    diagnostics: dict[str, Any],
    recovered_via_retry: bool,
) -> TurnRecord | dict[str, Any] | None:
    if not breach_type and not diagnostics:
        return turn_record

    if turn_record is None:
        turn_record = TurnRecord()

    if isinstance(turn_record, dict):
        metadata = (
            dict(turn_record.get("metadata") or {})
            if isinstance(turn_record.get("metadata"), dict)
            else {}
        )
        turn_record["metadata"] = metadata
    else:
        metadata = (
            dict(getattr(turn_record, "metadata", {}) or {})
            if isinstance(getattr(turn_record, "metadata", {}), dict)
            else {}
        )
        turn_record.metadata = metadata

    if breach_type:
        metadata["contract_breach_type"] = breach_type
    metadata["tool_leak_detected"] = bool(diagnostics.get("tool_leak_detected"))
    metadata["assistant_claimed_tool_call_without_tool_event"] = bool(
        diagnostics.get("assistant_claimed_tool_call_without_tool_event")
    )
    metadata["unfinished_intents"] = list(diagnostics.get("unfinished_intents") or [])
    metadata["recovered_via_retry"] = bool(recovered_via_retry)
    leaked_tool_names = list(diagnostics.get("leaked_tool_names") or [])
    if leaked_tool_names:
        metadata["leaked_tool_names"] = leaked_tool_names
    return turn_record
