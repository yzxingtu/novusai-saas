"""Conversation-turn diagnostics projector helpers for runtime diagnostics."""

from __future__ import annotations

from typing import Any

from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.runtime_root_cause_projector import RuntimeRootCauseProjector

_ANCHOR_METADATA_KEYS = (
    "turn_record",
    "context_diagnostics",
    "last_run_summary",
    "turn_outcome",
    "termination_reason",
    "protocol_path",
)

_ANCHOR_DIAGNOSTIC_KEYS = (
    "turn_outcome",
    "conversation_outcome",
    "termination_reason",
    "failure_kind",
    "unfinished_intents",
    "candidate_tool_names",
    "selected_tool_names",
    "retry_events",
    "provider_events",
)


class RuntimeDiagnosticsTurnProjector:
    """Build stable conversation-turn diagnostics without facade backdoors."""

    @staticmethod
    def message_metadata(message: Any) -> dict[str, Any]:
        raw_metadata = getattr(message, "metadata_", {})
        return dict(raw_metadata) if isinstance(raw_metadata, dict) else {}

    @staticmethod
    def _has_meaningful_value(value: Any) -> bool:
        return value not in (None, "", [], {}, ())

    @staticmethod
    def tool_calls(message: Any) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in (getattr(message, "tool_calls", None) or [])
            if isinstance(item, dict)
        ]

    @classmethod
    def assistant_message_is_turn_anchor(cls, message: Any) -> bool:
        metadata = cls.message_metadata(message)
        if not metadata:
            return False

        if any(
            cls._has_meaningful_value(metadata.get(key))
            for key in _ANCHOR_METADATA_KEYS
        ):
            return True

        diagnostics = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                metadata
            )
        )
        return any(
            cls._has_meaningful_value(diagnostics.get(key))
            for key in _ANCHOR_DIAGNOSTIC_KEYS
        )

    @classmethod
    def build_conversation_turn_payload(
        cls,
        *,
        conversation_id: int,
        message: Any,
    ) -> dict[str, Any]:
        metadata = cls.message_metadata(message)
        diagnostics = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                metadata
            )
        )
        content = str(getattr(message, "content", "") or "")
        tool_calls = cls.tool_calls(message)
        if RuntimeRootCauseProjector.detect_claimed_tool_call_without_event(
            content=content,
            diagnostics=diagnostics,
            tool_calls=tool_calls,
        ):
            diagnostics["assistant_claimed_tool_call_without_tool_event"] = True
            diagnostics.setdefault(
                "contract_breach_type",
                "assistant_claimed_tool_call_without_tool_event",
            )

        return {
            "message_id": getattr(message, "id", None),
            "conversation_id": conversation_id,
            "assistant_content": content,
            "tool_calls": tool_calls,
            "metadata": metadata,
            "diagnostics": diagnostics,
        }


__all__ = ["RuntimeDiagnosticsTurnProjector"]
