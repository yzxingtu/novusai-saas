"""Conversation-side stream persistence contract helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.enums.agent import MessageRoleEnum


class ConversationStreamPersistenceService:
    """Owns stream completion/error persistence on the conversation side."""

    def __init__(self, service: Any) -> None:
        self.service = service

    async def persist_stream_completion(
        self,
        *,
        conversation_id: int,
        result: ExecutionResult,
        history_count: int,
        agent_id: int | None,
        route_source: str | None,
        context_diagnostics: dict[str, Any] | None,
        last_run_summary: dict[str, Any] | None,
        current_agent: Any,
    ) -> int:
        conversation = await self.service.repo.get_by_id(conversation_id)
        if conversation is None:
            return 0
        _tool_calls, persisted_count = await self.service.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics,
            last_run_summary=last_run_summary,
        )
        await self.service.update_stats(
            conversation,
            result,
            current_agent=current_agent,
        )
        await self.service.db.commit()
        return persisted_count

    async def persist_stream_last_error_marker(
        self,
        *,
        conversation_id: int,
        error_type: str,
        error_message: str,
        friendly_message: str,
        partial: bool,
        extra_payload: dict[str, Any] | None = None,
    ) -> bool:
        conversation = await self.service.repo.get_by_id(conversation_id)
        if conversation is None:
            return False
        conversation_metadata = dict(conversation.metadata_ or {})
        marker_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": str(error_message or "")[:500],
            "friendly_message": friendly_message,
            "partial": bool(partial),
        }
        if isinstance(extra_payload, dict) and extra_payload:
            marker_payload["details"] = normalize_json_safe(extra_payload)
        conversation_metadata["last_error"] = marker_payload
        conversation.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
        await self.service.db.commit()
        return True

    async def save_stream_error_message(
        self,
        *,
        conversation_id: int,
        tenant_id: int,
        agent_id: int,
        error_text: str,
        user_message: str,
        result: ExecutionResult,
        context_diagnostics_payload: dict[str, Any],
        last_run_summary_payload: dict[str, Any],
        persist_user_message: bool,
        build_stream_error_display: Any,
    ) -> int:
        conversation = await self.service.repo.get_by_id(conversation_id)
        if conversation is None:
            return 0

        current_count = await self.service.message_repo.count_by_conversation(
            conversation_id
        )
        next_seq = await self.service.message_repo.get_next_sequence(conversation_id)
        persisted_rows = 0
        error_display = build_stream_error_display(
            result.error or error_text,
            failure_kind=str(
                getattr(result, "provider_failure_kind", "") or ""
            ).strip()
            or None,
        )
        error_message = str(
            error_display.get("message") or error_text or _("common.server_error")
        ).strip() or _("common.server_error")
        normalized_user_message = str(user_message or "").strip()

        if persist_user_message and normalized_user_message:
            await self.service.message_repo.create(
                {
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "role": MessageRoleEnum.USER.value,
                    "content": normalized_user_message,
                    "sequence": next_seq,
                    "token_count": estimate_tokens(normalized_user_message),
                    "agent_id": None,
                    "model_id": None,
                    "metadata_": normalize_json_safe_dict(
                        {
                            "recovered_from_failed_stream": True,
                            "stream_error_recovered": True,
                        }
                    )
                    or {},
                }
            )
            next_seq += 1
            persisted_rows += 1

        error_metadata: dict[str, Any] = {
            "error": True,
            "error_debug_message": error_display.get("debug_message"),
            "error_message": error_message,
            "error_only": bool(error_display.get("error_only")),
            "error_trace_id": error_display.get("trace_id"),
            "error_type": error_display.get("error_type") or "stream_execution_error",
            "raw_error_message": str(result.error or "")[:500],
            "partial_output": result.output or "",
            "total_tokens": result.total_tokens or 0,
            "duration_ms": result.duration_ms or 0,
            "user_message_preview": normalized_user_message[:200],
        }
        if context_diagnostics_payload:
            error_metadata["context_diagnostics"] = normalize_json_safe(
                context_diagnostics_payload
            )
        if last_run_summary_payload:
            error_metadata["last_run_summary"] = normalize_json_safe(
                last_run_summary_payload
            )
        error_metadata = normalize_json_safe_dict(error_metadata) or {}

        await self.service.message_repo.create(
            {
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "role": MessageRoleEnum.ASSISTANT.value,
                "content": error_message,
                "sequence": next_seq,
                "token_count": estimate_tokens(error_message),
                "agent_id": agent_id,
                "model_id": result.runtime_model_id,
                "metadata_": error_metadata,
            }
        )
        persisted_rows += 1

        conversation_metadata = dict(conversation.metadata_ or {})
        conversation_metadata["last_error"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "debug_message": error_display.get("debug_message"),
            "error_message": str(result.error or "")[:500],
            "error_type": error_display.get("error_type") or "stream_execution_error",
            "friendly_message": error_message,
            "partial": bool(result.partial),
            "trace_id": error_display.get("trace_id"),
        }
        if persisted_rows:
            conversation.message_count = max(
                int(getattr(conversation, "message_count", 0) or 0),
                int(current_count or 0),
            ) + persisted_rows
        conversation.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
        await self.service.db.commit()
        return int(persisted_rows or 0)


__all__ = ["ConversationStreamPersistenceService"]
