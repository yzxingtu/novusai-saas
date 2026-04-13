"""
Conversation diagnostics/read-model projector.
"""

from __future__ import annotations

from app.services.ai.conversation_diagnostics_projector_support import (
    assistant_has_content_or_signal,
    copy_metadata,
    enrich_tool_calls_for_persistence,
    extract_turn_diagnostics_from_metadata,
    has_pending_state,
    normalize_context_sources,
    normalize_intent_plan,
    normalize_json_dict,
    normalize_json_safe,
    normalize_json_safe_dict,
    normalize_provider_events,
    normalize_retry_events,
    normalize_string_list,
    normalize_turn_record_payload,
    sanitize_tool_messages,
    to_non_empty_str,
)


class ConversationDiagnosticsProjector:
    copy_metadata = staticmethod(copy_metadata)
    normalize_json_safe = staticmethod(normalize_json_safe)
    normalize_json_safe_dict = staticmethod(normalize_json_safe_dict)
    normalize_turn_record_payload = staticmethod(normalize_turn_record_payload)
    to_non_empty_str = staticmethod(to_non_empty_str)
    normalize_string_list = staticmethod(normalize_string_list)
    normalize_context_sources = staticmethod(normalize_context_sources)
    normalize_json_dict = staticmethod(normalize_json_dict)
    normalize_intent_plan = staticmethod(normalize_intent_plan)
    normalize_retry_events = staticmethod(normalize_retry_events)
    normalize_provider_events = staticmethod(normalize_provider_events)
    extract_turn_diagnostics_from_metadata = staticmethod(
        extract_turn_diagnostics_from_metadata
    )
    has_pending_state = staticmethod(has_pending_state)
    assistant_has_content_or_signal = staticmethod(assistant_has_content_or_signal)
    sanitize_tool_messages = staticmethod(sanitize_tool_messages)
    enrich_tool_calls_for_persistence = staticmethod(enrich_tool_calls_for_persistence)


__all__ = ["ConversationDiagnosticsProjector"]
