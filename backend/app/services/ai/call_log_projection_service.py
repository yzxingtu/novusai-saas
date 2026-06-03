"""
Call log observability projection helpers.
"""

from __future__ import annotations

from typing import Any

from app.core.base_model import utc_now
from app.core.response import serialize_datetime_for_api
from app.enums.ai import CallStatusEnum
from app.services.ai.call_log_support import CallLogSupport
from app.services.ai.conversation_diagnostics_projector_support import (
    normalize_turn_skill_activation_payload,
    resolve_live_selected_name_list,
)
from app.services.ai.turn_failure_normalizer import resolve_failure_projection


class CallLogProjectionMixin(CallLogSupport):
    @classmethod
    def _inject_turn_hints(
        cls,
        request_data: dict[str, Any] | None,
        *,
        turn_record: Any = None,
        selected_tool_names: list[str] | None = None,
        selected_skill_names: list[str] | None = None,
        protocol_path: str | None = None,
        context_sources: list[dict[str, Any]] | None = None,
        fallback_history: list[dict[str, Any]] | None = None,
        sync_rescue: bool | None = None,
        should_record_call_log: bool | None = None,
    ) -> dict[str, Any]:
        payload = dict(request_data or {})
        normalized_turn_record = (
            cls._normalize_turn_record_payload(payload.get("turn_record")) or {}
        )

        incoming_turn_record = cls._normalize_turn_record_payload(turn_record)
        if incoming_turn_record:
            normalized_turn_record.update(incoming_turn_record)

        turn_record_metadata = (
            dict(normalized_turn_record.get("metadata") or {})
            if isinstance(normalized_turn_record.get("metadata"), dict)
            else {}
        )
        turn_record_diagnostics = (
            dict(turn_record_metadata.get("turn_diagnostics") or {})
            if isinstance(turn_record_metadata.get("turn_diagnostics"), dict)
            else {}
        )
        turn_skill_activation = normalize_turn_skill_activation_payload(
            normalized_turn_record.get("turn_skill_activation")
            or turn_record_diagnostics.get("turn_skill_activation")
            or payload.get("turn_skill_activation")
        )
        if selected_tool_names is not None:
            normalized_tools = cls._normalize_string_list(selected_tool_names)
            normalized_tools_explicit = True
        else:
            normalized_tools, normalized_tools_explicit = (
                resolve_live_selected_name_list(
                    "selected_tool_names",
                    normalized_turn_record,
                    turn_record_diagnostics,
                    payload,
                    turn_skill_activation=turn_skill_activation,
                )
            )
        if selected_skill_names is not None:
            normalized_skills = cls._normalize_string_list(selected_skill_names)
            normalized_skills_explicit = True
        else:
            normalized_skills, normalized_skills_explicit = (
                resolve_live_selected_name_list(
                    "selected_skill_names",
                    normalized_turn_record,
                    turn_record_diagnostics,
                    payload,
                    turn_skill_activation=turn_skill_activation,
                )
            )
        normalized_protocol = cls._to_non_empty_str(
            protocol_path
            if protocol_path is not None
            else normalized_turn_record.get("protocol_path")
        )
        normalized_sources = cls._normalize_context_sources(
            context_sources
            if context_sources is not None
            else normalized_turn_record.get("context_sources")
        )
        normalized_fallback = cls._normalize_fallback_history(
            fallback_history
            if fallback_history is not None
            else normalized_turn_record.get("fallback_history")
        )

        sync_rescue_value = cls._pick_first_bool(
            [
                sync_rescue,
                (
                    normalized_turn_record.get("metadata", {}).get("sync_rescue")
                    if isinstance(normalized_turn_record.get("metadata"), dict)
                    else None
                ),
                normalized_turn_record.get("sync_rescue"),
            ]
        )
        should_record_value = cls._pick_first_bool(
            [
                should_record_call_log,
                (
                    normalized_turn_record.get("metadata", {}).get(
                        "should_record_call_log"
                    )
                    if isinstance(normalized_turn_record.get("metadata"), dict)
                    else None
                ),
                normalized_turn_record.get("should_record_call_log"),
            ]
        )

        if normalized_tools_explicit:
            payload["selected_tool_names"] = normalized_tools
            normalized_turn_record["selected_tool_names"] = normalized_tools
        if normalized_skills_explicit:
            payload["selected_skill_names"] = normalized_skills
            normalized_turn_record["selected_skill_names"] = normalized_skills
        if normalized_protocol:
            payload["protocol_path"] = normalized_protocol
            normalized_turn_record["protocol_path"] = normalized_protocol
        if normalized_sources:
            payload["context_sources"] = normalized_sources
            normalized_turn_record["context_sources"] = normalized_sources
        if normalized_fallback:
            payload["fallback_history"] = normalized_fallback
            normalized_turn_record["fallback_history"] = normalized_fallback
        if sync_rescue_value is not None:
            payload["sync_rescue"] = sync_rescue_value
            metadata = (
                dict(normalized_turn_record.get("metadata") or {})
                if isinstance(normalized_turn_record.get("metadata"), dict)
                else {}
            )
            metadata["sync_rescue"] = sync_rescue_value
            normalized_turn_record["metadata"] = metadata
        if should_record_value is not None:
            payload["should_record_call_log"] = should_record_value
            metadata = (
                dict(normalized_turn_record.get("metadata") or {})
                if isinstance(normalized_turn_record.get("metadata"), dict)
                else {}
            )
            metadata["should_record_call_log"] = should_record_value
            normalized_turn_record["metadata"] = metadata

        if normalized_turn_record:
            payload["turn_record"] = normalized_turn_record
        return payload

    @classmethod
    def _build_turn_diagnostics(
        cls,
        *,
        request_data: dict[str, Any] | None,
        response_data: dict[str, Any] | None,
        status: str,
        error_message: str | None,
    ) -> dict[str, Any]:
        req = request_data if isinstance(request_data, dict) else {}
        rsp = response_data if isinstance(response_data, dict) else {}

        turn_record = cls._normalize_turn_record_payload(
            req.get("turn_record")
        ) or cls._normalize_turn_record_payload(rsp.get("turn_record"))
        turn_record_metadata = (
            dict((turn_record or {}).get("metadata") or {})
            if isinstance((turn_record or {}).get("metadata"), dict)
            else {}
        )
        incoming = (
            req.get("turn_diagnostics")
            if isinstance(req.get("turn_diagnostics"), dict)
            else {}
        )

        turn_outcome = cls._to_non_empty_str(
            (turn_record or {}).get("turn_outcome")
            or incoming.get("turn_outcome")
            or req.get("turn_outcome")
        )
        termination_reason = cls._to_non_empty_str(
            (turn_record or {}).get("termination_reason")
            or incoming.get("termination_reason")
            or req.get("termination_reason")
        )
        protocol_path = cls._to_non_empty_str(
            (turn_record or {}).get("protocol_path")
            or incoming.get("protocol_path")
            or req.get("protocol_path")
        )
        raw_tool_planner = (
            (turn_record or {}).get("tool_planner")
            or incoming.get("tool_planner")
            or req.get("tool_planner")
        )
        tool_planner = (
            cls._make_json_safe(dict(raw_tool_planner))
            if isinstance(raw_tool_planner, dict)
            else None
        )
        turn_skill_activation = normalize_turn_skill_activation_payload(
            (turn_record or {}).get("turn_skill_activation")
            or incoming.get("turn_skill_activation")
            or req.get("turn_skill_activation")
            or turn_record_metadata.get("turn_diagnostics", {}).get(
                "turn_skill_activation"
            )
        )
        selected_tool_names, _selected_tools_explicit = resolve_live_selected_name_list(
            "selected_tool_names",
            turn_record,
            incoming,
            req,
            turn_skill_activation=turn_skill_activation,
        )
        selected_skill_names, _selected_skills_explicit = (
            resolve_live_selected_name_list(
                "selected_skill_names",
                turn_record,
                incoming,
                req,
                turn_skill_activation=turn_skill_activation,
            )
        )
        context_sources = (
            cls._normalize_context_sources((turn_record or {}).get("context_sources"))
            or cls._normalize_context_sources(incoming.get("context_sources"))
            or cls._normalize_context_sources(req.get("context_sources"))
        )
        fallback_history = (
            cls._normalize_fallback_history((turn_record or {}).get("fallback_history"))
            or cls._normalize_fallback_history(incoming.get("fallback_history"))
            or cls._normalize_fallback_history(req.get("fallback_history"))
        )
        sync_rescue = cls._pick_first_bool(
            [
                turn_record_metadata.get("sync_rescue"),
                (turn_record or {}).get("sync_rescue"),
                incoming.get("sync_rescue"),
                req.get("sync_rescue"),
            ]
        )
        should_record_call_log = cls._pick_first_bool(
            [
                turn_record_metadata.get("should_record_call_log"),
                (turn_record or {}).get("should_record_call_log"),
                incoming.get("should_record_call_log"),
                req.get("should_record_call_log"),
            ]
        )
        last_tool_name = cls._to_non_empty_str(
            (turn_record or {}).get("last_tool_name")
            or incoming.get("last_tool_name")
            or req.get("last_tool_name")
        )
        interrupted_stage = cls._to_non_empty_str(
            (turn_record or {}).get("interrupted_stage")
            or incoming.get("interrupted_stage")
            or req.get("interrupted_stage")
        )
        active_intent_id = cls._to_non_empty_str(
            (turn_record or {}).get("active_intent_id")
            or incoming.get("active_intent_id")
            or req.get("active_intent_id")
        )
        continuation_source = cls._to_non_empty_str(
            (turn_record or {}).get("continuation_source")
            or incoming.get("continuation_source")
            or req.get("continuation_source")
        )
        conversation_outcome = cls._to_non_empty_str(
            (turn_record or {}).get("conversation_outcome")
            or incoming.get("conversation_outcome")
            or req.get("conversation_outcome")
            or turn_outcome
        )
        assistant_claimed_tool_call_without_tool_event = cls._pick_first_bool(
            [
                turn_record_metadata.get(
                    "assistant_claimed_tool_call_without_tool_event"
                ),
                (turn_record or {}).get(
                    "assistant_claimed_tool_call_without_tool_event"
                ),
                incoming.get("assistant_claimed_tool_call_without_tool_event"),
                req.get("assistant_claimed_tool_call_without_tool_event"),
            ]
        )
        tool_loop_progress = (
            dict((turn_record or {}).get("tool_loop_progress") or {})
            if isinstance((turn_record or {}).get("tool_loop_progress"), dict)
            else (
                dict(incoming.get("tool_loop_progress") or {})
                if isinstance(incoming.get("tool_loop_progress"), dict)
                else (
                    dict(req.get("tool_loop_progress") or {})
                    if isinstance(req.get("tool_loop_progress"), dict)
                    else {}
                )
            )
        )

        if not turn_outcome:
            turn_outcome = (
                "success" if status == CallStatusEnum.SUCCESS.value else "failed"
            )
        if not termination_reason:
            termination_reason = (
                "completed" if status == CallStatusEnum.SUCCESS.value else "error"
            )
        failure_kind = cls._to_non_empty_str(
            (turn_record or {}).get("failure_kind")
            or incoming.get("failure_kind")
            or turn_record_metadata.get("failure_kind")
            or turn_record_metadata.get("provider_failure_kind")
            or req.get("failure_kind")
        )
        normalized_failure = resolve_failure_projection(
            diagnostics={
                "turn_record": turn_record,
                "turn_outcome": turn_outcome,
                "termination_reason": termination_reason,
                "failure_kind": failure_kind,
                "error_message": error_message,
            }
        )
        turn_outcome = (
            cls._to_non_empty_str(normalized_failure.get("turn_outcome"))
            or turn_outcome
        )
        termination_reason = (
            cls._to_non_empty_str(normalized_failure.get("termination_reason"))
            or termination_reason
        )
        normalized_failure_kind = cls._to_non_empty_str(
            normalized_failure.get("failure_kind")
        )
        failure_kind = (
            normalized_failure_kind
            if normalized_failure.get("authoritative_completed_success")
            else normalized_failure_kind or failure_kind
        )
        if turn_record:
            turn_record = dict(turn_record)
            turn_record["turn_outcome"] = turn_outcome
            turn_record["termination_reason"] = termination_reason
            if failure_kind:
                turn_record["failure_kind"] = failure_kind

        diagnostics: dict[str, Any] = {
            "turn_outcome": turn_outcome,
            "conversation_outcome": conversation_outcome,
            "termination_reason": termination_reason,
            "selected_tool_names": selected_tool_names,
            "selected_skill_names": selected_skill_names,
            "context_sources": context_sources,
        }
        if protocol_path:
            diagnostics["protocol_path"] = protocol_path
        if tool_planner:
            diagnostics["tool_planner"] = tool_planner
        if fallback_history:
            diagnostics["fallback_history"] = fallback_history
        if sync_rescue is not None:
            diagnostics["sync_rescue"] = sync_rescue
        if should_record_call_log is not None:
            diagnostics["should_record_call_log"] = should_record_call_log
        if last_tool_name:
            diagnostics["last_tool_name"] = last_tool_name
        if interrupted_stage:
            diagnostics["interrupted_stage"] = interrupted_stage
        if active_intent_id:
            diagnostics["active_intent_id"] = active_intent_id
        if continuation_source:
            diagnostics["continuation_source"] = continuation_source
        if assistant_claimed_tool_call_without_tool_event is not None:
            diagnostics["assistant_claimed_tool_call_without_tool_event"] = (
                assistant_claimed_tool_call_without_tool_event
            )
        if tool_loop_progress:
            diagnostics["tool_loop_progress"] = tool_loop_progress
        if turn_record:
            diagnostics["turn_record"] = turn_record
        if failure_kind:
            diagnostics["failure_kind"] = failure_kind
        if status != CallStatusEnum.SUCCESS.value and error_message:
            diagnostics["error_message"] = error_message
        return diagnostics

    @classmethod
    def _build_request_metadata_payload(
        cls,
        *,
        request_data: dict[str, Any] | None,
        response_data: Any,
        turn_diagnostics: dict[str, Any] | None,
        agent_id: int | None,
        conversation_id: int | None,
        routed_model_id: int | None,
        route_reason: str | None,
        caller_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return cls._make_json_safe(
            {
                "request": cls._sanitize_request(request_data),
                "response": cls._truncate_response(response_data),
                "turn_diagnostics": turn_diagnostics,
                "timestamp": serialize_datetime_for_api(utc_now()),
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "routed_model_id": routed_model_id,
                "route_reason": route_reason,
                "caller_snapshot": caller_snapshot,
            }
        )


__all__ = ["CallLogProjectionMixin"]
