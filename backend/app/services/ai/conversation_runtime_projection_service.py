"""Conversation detail runtime projection helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.json_safe import normalize_json_safe_dict
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)
from app.services.ai.turn_failure_normalizer import resolve_failure_projection


class ConversationRuntimeProjectionService:
    """Builds detail payloads and runtime diagnostics outside the facade."""

    def __init__(
        self,
        *,
        message_repo: Any,
        read_model_service: Any,
        get_accessible_conversation: Callable[..., Awaitable[Any]],
        get_context_compaction_snapshot: Callable[
            [int], Awaitable[dict[str, Any] | None]
        ],
    ) -> None:
        self.message_repo = message_repo
        self.read_model_service = read_model_service
        self.get_accessible_conversation = get_accessible_conversation
        self.get_context_compaction_snapshot = get_context_compaction_snapshot

    async def get_conversation_detail(
        self,
        *,
        conversation_id: int,
        message_skip: int,
        message_limit: int,
        user_id: int | None,
        owner_type: str | None,
    ) -> dict[str, Any]:
        conversation = await self.get_accessible_conversation(
            conversation_id,
            user_id=user_id,
            owner_type=owner_type,
        )
        messages = await self.message_repo.get_by_conversation(
            conversation_id=conversation_id,
            skip=message_skip,
            limit=message_limit,
        )
        message_count = await self.message_repo.count_by_conversation(conversation_id)

        message_list = await self.read_model_service.serialize_conversation_messages(
            messages
        )
        result = self.read_model_service.build_conversation_detail_base(
            conversation,
            message_list=message_list,
            message_count=message_count,
        )

        latest_assistant_loader = getattr(
            self.message_repo,
            "get_latest_assistant_message",
            None,
        )
        last_assistant_message = (
            await self.read_model_service.resolve_last_assistant_message(
                conversation_id=conversation_id,
                message_list=message_list,
                latest_assistant_loader=latest_assistant_loader,
            )
        )
        conversation_metadata = (
            dict(conversation.metadata_)
            if isinstance(conversation.metadata_, dict)
            else {}
        )
        conversation_last_error = self.normalize_json_safe_dict(
            conversation_metadata.get("last_error")
        )
        thread_memory_state = self._conversation_thread_memory_state(
            conversation_metadata
        )
        compaction_snapshot = await self.get_context_compaction_snapshot(
            conversation.id
        )
        _interaction_mode_requested, interaction_mode_effective = (
            self.read_model_service.extract_interaction_modes(conversation_metadata)
        )
        downgrade_reason = conversation_metadata.get(
            "interaction_mode_downgrade_reason"
        )

        if last_assistant_message is not None:
            result["turn_flow"] = (
                ConversationTurnFlowProjector.project_from_message_payload(
                    last_assistant_message
                )
            )
            result["context_diagnostics"] = self.build_context_diagnostics_payload(
                last_assistant_message,
                compaction_snapshot=compaction_snapshot,
                interaction_mode_effective=interaction_mode_effective,
                thread_memory_state=thread_memory_state,
            )
            result["last_run_summary"] = self.build_last_run_summary_payload(
                last_assistant_message,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=downgrade_reason,
                thread_memory_state=thread_memory_state,
            )
            return result

        result.update(
            self.read_model_service.build_error_only_runtime_projection(
                conversation_last_error=conversation_last_error,
                compaction_snapshot=compaction_snapshot,
                interaction_mode_effective=interaction_mode_effective,
                downgrade_reason=downgrade_reason,
            )
        )
        cls = type(self)
        cls._apply_thread_memory_projection(
            result.get("context_diagnostics"),
            thread_memory_state=thread_memory_state,
        )
        cls._apply_thread_memory_projection(
            result.get("last_run_summary"),
            thread_memory_state=thread_memory_state,
        )
        return result

    @staticmethod
    def normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
        return normalize_json_safe_dict(raw)

    @classmethod
    def build_context_diagnostics_payload(
        cls,
        last_assistant_message: dict[str, Any] | None,
        *,
        compaction_snapshot: dict[str, Any] | None,
        interaction_mode_effective: str,
        thread_memory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del interaction_mode_effective
        metadata = cls._message_metadata(last_assistant_message)
        turn_meta = cls.extract_turn_diagnostics_from_metadata(metadata)
        memory_runtime_policy = cls._resolve_memory_runtime_policy(
            metadata,
            thread_memory_state=thread_memory_state,
        )
        return {
            "estimated_tokens": (
                last_assistant_message.get("token_count")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "context_compacted": bool(metadata.get("context_compacted")),
            "compact_summary_present": bool((compaction_snapshot or {}).get("summary")),
            "memory_recalled": bool(metadata.get("memory_recalled")),
            "memory_flush_triggered": bool(metadata.get("memory_flush_triggered")),
            "external_context_polluted": bool(
                memory_runtime_policy.get("external_context_polluted")
            ),
            "external_context_reason": memory_runtime_policy.get(
                "external_context_reason"
            ),
            "prune_stats": metadata.get("prune_stats"),
            "rag_source_kinds": list(metadata.get("rag_source_kinds") or []),
            "last_interrupted": bool(metadata.get("interrupted"))
            or (turn_meta.get("termination_reason") == "interrupted"),
            **cls._shared_turn_projection(turn_meta, metadata=metadata),
        }

    @classmethod
    def build_last_run_summary_payload(
        cls,
        last_assistant_message: dict[str, Any] | None,
        *,
        interaction_mode_effective: str,
        downgrade_reason: Any,
        thread_memory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del interaction_mode_effective, downgrade_reason
        metadata = cls._message_metadata(last_assistant_message)
        turn_meta = cls.extract_turn_diagnostics_from_metadata(metadata)
        memory_runtime_policy = cls._resolve_memory_runtime_policy(
            metadata,
            thread_memory_state=thread_memory_state,
        )
        shared_projection = cls._shared_turn_projection(turn_meta, metadata=metadata)
        completion_reason = turn_meta.get("termination_reason") or metadata.get(
            "completion_reason"
        )
        completion_reason = (
            shared_projection.get("termination_reason") or completion_reason
        )
        interrupted = bool(metadata.get("interrupted")) or (
            completion_reason == "interrupted"
        )
        return {
            "completion_reason": completion_reason,
            "created_at": (
                last_assistant_message.get("created_at")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "interrupted": interrupted,
            "provider_name": (
                last_assistant_message.get("provider_name")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "runtime_model_name": (
                last_assistant_message.get("model_name")
                if isinstance(last_assistant_message, dict)
                else None
            ),
            "external_context_polluted": bool(
                memory_runtime_policy.get("external_context_polluted")
            ),
            "external_context_reason": memory_runtime_policy.get(
                "external_context_reason"
            ),
            **shared_projection,
        }

    @staticmethod
    def _message_metadata(
        last_assistant_message: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(last_assistant_message, dict):
            return {}
        raw_metadata = last_assistant_message.get("metadata")
        return dict(raw_metadata) if isinstance(raw_metadata, dict) else {}

    @staticmethod
    def _conversation_thread_memory_state(
        conversation_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(conversation_metadata, dict):
            return {}
        raw_thread_memory_state = conversation_metadata.get("thread_memory_state")
        return (
            dict(raw_thread_memory_state)
            if isinstance(raw_thread_memory_state, dict)
            else {}
        )

    @staticmethod
    def _resolve_memory_runtime_policy(
        metadata: dict[str, Any] | None,
        *,
        thread_memory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_memory_runtime_policy = (
            metadata.get("memory_runtime_policy")
            if isinstance(metadata, dict)
            else None
        )
        if isinstance(raw_memory_runtime_policy, dict):
            return dict(raw_memory_runtime_policy)
        if isinstance(thread_memory_state, dict):
            return dict(thread_memory_state)
        return {}

    @staticmethod
    def _apply_thread_memory_projection(
        payload: dict[str, Any] | None,
        *,
        thread_memory_state: dict[str, Any] | None,
    ) -> None:
        if not isinstance(payload, dict) or not isinstance(thread_memory_state, dict):
            return
        if thread_memory_state.get("external_context_polluted") is not None:
            payload["external_context_polluted"] = bool(
                thread_memory_state.get("external_context_polluted")
            )
        if thread_memory_state.get("external_context_reason"):
            payload["external_context_reason"] = thread_memory_state.get(
                "external_context_reason"
            )

    @staticmethod
    def _shared_turn_projection(
        turn_meta: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        projection = resolve_failure_projection(
            diagnostics=turn_meta,
            turn_flow=(metadata or {}).get("turn_flow")
            if isinstance((metadata or {}).get("turn_flow"), dict)
            else None,
        )
        return {
            "turn_outcome": projection.get("turn_outcome")
            or turn_meta.get("turn_outcome"),
            "termination_reason": projection.get("termination_reason")
            or turn_meta.get("termination_reason"),
            "protocol_path": turn_meta.get("protocol_path"),
            "tool_planner": turn_meta.get("tool_planner"),
            "selected_tool_names": turn_meta.get("selected_tool_names") or [],
            "selected_skill_names": turn_meta.get("selected_skill_names") or [],
            "context_sources": turn_meta.get("context_sources") or [],
            "execution_path": turn_meta.get("execution_path"),
            "active_intent_id": turn_meta.get("active_intent_id"),
            "continuation_source": turn_meta.get("continuation_source"),
            "conversation_outcome": turn_meta.get("conversation_outcome"),
            "intent_plan": turn_meta.get("intent_plan") or [],
            "budget": turn_meta.get("budget"),
            "budget_status": turn_meta.get("budget_status"),
            "budget_exit_reason": projection.get("budget_exit_reason")
            or turn_meta.get("budget_exit_reason"),
            "candidate_tool_names": turn_meta.get("candidate_tool_names") or [],
            "retry_events": turn_meta.get("retry_events") or [],
            "partial_exit_reason": turn_meta.get("partial_exit_reason"),
            "failure_kind": projection.get("failure_kind")
            or turn_meta.get("failure_kind"),
            "final_output_source": projection.get("final_output_source")
            or turn_meta.get("final_output_source"),
            "provider_events": turn_meta.get("provider_events") or [],
            "contract_breach_type": turn_meta.get("contract_breach_type"),
            "tool_leak_detected": bool(turn_meta.get("tool_leak_detected")),
            "assistant_claimed_tool_call_without_tool_event": bool(
                turn_meta.get("assistant_claimed_tool_call_without_tool_event")
            ),
            "unfinished_intents": turn_meta.get("unfinished_intents") or [],
            "leaked_tool_names": turn_meta.get("leaked_tool_names") or [],
            "recovered_via_retry": turn_meta.get("recovered_via_retry"),
            "last_tool_name": turn_meta.get("last_tool_name"),
            "last_page_key": turn_meta.get("last_page_key"),
            "last_page_op": turn_meta.get("last_page_op"),
            "interrupted_stage": turn_meta.get("interrupted_stage"),
            "tool_loop_progress": turn_meta.get("tool_loop_progress") or {},
            "sync_rescue": turn_meta.get("sync_rescue"),
            "should_record_call_log": turn_meta.get("should_record_call_log"),
        }

    @staticmethod
    def extract_turn_diagnostics_from_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
            metadata
        )
