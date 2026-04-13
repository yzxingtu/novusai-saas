"""
Error-persistence support for agent chat stream completion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ai.engine.types import ExecutionResult
from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import MessageRoleEnum

logger = LogManager.get_logger("ai.agent_chat_service")


async def persist_stream_last_error_marker(
    orchestrator: Any,
    *,
    error_type: str,
    error_message: str,
    friendly_message: str,
    partial: bool,
    extra_payload: dict[str, Any] | None = None,
) -> bool:
    deps = orchestrator._deps()
    async with deps.session_factory() as marker_db:
        marker_conv_svc = deps.conversation_service_cls(
            marker_db,
            orchestrator.tenant_id,
        )
        if orchestrator._has_stream_contract(
            marker_conv_svc,
            "persist_stream_last_error_marker",
        ):
            return await marker_conv_svc.persist_stream_last_error_marker(
                conversation_id=orchestrator.conversation_id,
                error_type=error_type,
                error_message=error_message,
                friendly_message=friendly_message,
                partial=partial,
                extra_payload=extra_payload,
            )
        marker_conv = await marker_conv_svc.repo.get_by_id(orchestrator.conversation_id)
        if marker_conv is None:
            logger.warning(
                "Skip stream error marker because conversation is missing: conversation_id={}",
                orchestrator.conversation_id,
            )
            return False

        conversation_metadata = dict(marker_conv.metadata_ or {})
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
        marker_conv.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
        await marker_db.commit()
        return True


async def save_error_message_to_conversation(
    orchestrator: Any,
    *,
    error_text: str,
    user_message: str,
    result: ExecutionResult,
    context_diagnostics_payload: dict[str, Any],
    last_run_summary_payload: dict[str, Any],
    persist_user_message: bool,
) -> int:
    deps = orchestrator._deps()
    async with deps.session_factory() as err_db:
        err_conv_svc = deps.conversation_service_cls(err_db, orchestrator.tenant_id)
        if orchestrator._has_stream_contract(err_conv_svc, "save_stream_error_message"):
            return await err_conv_svc.save_stream_error_message(
                conversation_id=orchestrator.conversation_id,
                error_text=error_text,
                user_message=user_message,
                result=result,
                context_diagnostics_payload=context_diagnostics_payload,
                last_run_summary_payload=last_run_summary_payload,
                persist_user_message=persist_user_message,
                agent_id=orchestrator.agent_id,
                build_stream_error_display=orchestrator.build_stream_error_display,
            )
        err_conv = await err_conv_svc.repo.get_by_id(orchestrator.conversation_id)
        if err_conv is None:
            logger.warning(
                "Skip stream error persistence because conversation is missing: conversation_id={}",
                orchestrator.conversation_id,
            )
            return 0

        current_count = await err_conv_svc.message_repo.count_by_conversation(
            orchestrator.conversation_id
        )
        next_seq = await err_conv_svc.message_repo.get_next_sequence(
            orchestrator.conversation_id
        )
        persisted_rows = 0
        error_display = orchestrator.build_stream_error_display(
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
            await err_conv_svc.message_repo.create(
                {
                    "tenant_id": orchestrator.tenant_id,
                    "conversation_id": orchestrator.conversation_id,
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
            "user_message_preview": (user_message or "")[:200],
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

        await err_conv_svc.message_repo.create(
            {
                "tenant_id": orchestrator.tenant_id,
                "conversation_id": orchestrator.conversation_id,
                "role": MessageRoleEnum.ASSISTANT.value,
                "content": error_message,
                "sequence": next_seq,
                "token_count": estimate_tokens(error_message),
                "agent_id": orchestrator.agent_id,
                "model_id": result.runtime_model_id,
                "metadata_": error_metadata,
            }
        )
        persisted_rows += 1

        conversation_metadata = dict(err_conv.metadata_ or {})
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
            err_conv.message_count = max(
                int(getattr(err_conv, "message_count", 0) or 0),
                int(current_count or 0),
            ) + persisted_rows
        err_conv.metadata_ = normalize_json_safe_dict(conversation_metadata) or {}
        await err_db.commit()
        logger.info(
            "Stream error message saved: conversation_id={} error_type=stream_execution_error",
            orchestrator.conversation_id,
        )
        return int(persisted_rows or 0)


__all__ = [
    "persist_stream_last_error_marker",
    "save_error_message_to_conversation",
]
