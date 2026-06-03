"""
Error-persistence support for agent chat stream completion.
"""

from __future__ import annotations

from typing import Any

from app.ai.engine.types import ExecutionResult


async def persist_stream_last_error_marker(
    orchestrator: Any,
    *,
    error_type: str,
    error_message: str,
    friendly_message: str,
    partial: bool,
    extra_payload: dict[str, Any] | None = None,
    memory_runtime_policy: dict[str, Any] | None = None,
) -> bool:
    deps = orchestrator._deps()
    async with deps.session_factory() as marker_db:
        marker_conv_svc = deps.conversation_service_cls(
            marker_db,
            orchestrator.tenant_id,
        )
        return await marker_conv_svc.persist_stream_last_error_marker(
            conversation_id=orchestrator.conversation_id,
            error_type=error_type,
            error_message=error_message,
            friendly_message=friendly_message,
            partial=partial,
            extra_payload=extra_payload,
            memory_runtime_policy=memory_runtime_policy,
        )


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


__all__ = [
    "persist_stream_last_error_marker",
    "save_error_message_to_conversation",
]
