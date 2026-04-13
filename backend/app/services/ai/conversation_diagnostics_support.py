"""
Conversation diagnostics normalization helpers.
"""

from __future__ import annotations

from typing import Any

from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.conversation_runtime_projection_service import (
    ConversationRuntimeProjectionService,
)


def build_context_diagnostics_payload(
    last_assistant_message: dict[str, Any] | None,
    *,
    compaction_snapshot: dict[str, Any] | None,
    interaction_mode_effective: str,
) -> dict[str, Any]:
    return ConversationRuntimeProjectionService.build_context_diagnostics_payload(
        last_assistant_message,
        compaction_snapshot=compaction_snapshot,
        interaction_mode_effective=interaction_mode_effective,
    )


def build_last_run_summary_payload(
    last_assistant_message: dict[str, Any] | None,
    *,
    interaction_mode_effective: str,
    downgrade_reason: Any,
) -> dict[str, Any]:
    return ConversationRuntimeProjectionService.build_last_run_summary_payload(
        last_assistant_message,
        interaction_mode_effective=interaction_mode_effective,
        downgrade_reason=downgrade_reason,
    )


def normalize_turn_record_payload(turn_record: Any) -> dict[str, Any] | None:
    return ConversationDiagnosticsProjector.normalize_turn_record_payload(turn_record)


def to_non_empty_str(value: Any) -> str | None:
    return ConversationDiagnosticsProjector.to_non_empty_str(value)


def normalize_string_list(value: Any) -> list[str]:
    return ConversationDiagnosticsProjector.normalize_string_list(value)


def normalize_context_sources(value: Any) -> list[dict[str, Any]]:
    return ConversationDiagnosticsProjector.normalize_context_sources(value)


def normalize_json_dict(value: Any) -> dict[str, Any] | None:
    return ConversationDiagnosticsProjector.normalize_json_dict(value)


def normalize_intent_plan(value: Any) -> list[dict[str, Any]]:
    return ConversationDiagnosticsProjector.normalize_intent_plan(value)


def normalize_retry_events(value: Any) -> list[dict[str, Any]]:
    return ConversationDiagnosticsProjector.normalize_retry_events(value)


def normalize_provider_events(value: Any) -> list[dict[str, Any]]:
    return ConversationDiagnosticsProjector.normalize_provider_events(value)


def extract_turn_diagnostics_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return ConversationRuntimeProjectionService.extract_turn_diagnostics_from_metadata(
        metadata
    )


def normalize_json_safe_value(value: Any) -> Any:
    return normalize_json_safe(value)


def normalize_json_safe_dict_value(raw: Any) -> dict[str, Any] | None:
    return normalize_json_safe_dict(raw)


def copy_metadata(raw: Any) -> dict[str, Any] | None:
    return normalize_json_safe_dict(raw)
