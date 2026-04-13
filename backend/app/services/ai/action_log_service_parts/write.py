"""Write helpers for AI action logs."""

from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.agent import ActionStatusEnum, ActionTypeEnum
from app.middleware.trace import trace_id_var
from app.models.ai.action_log import AIActionLog
from app.services.ai.action_log_service_parts.normalization import (
    _normalize_audit_payload,
    _normalize_operator_type,
)
from app.services.ai.action_log_service_parts.snapshots import (
    _load_agent_snapshot,
    _load_operator_snapshot,
)


async def write_ai_action_log(
    db: AsyncSession,
    *,
    tenant_id: int,
    agent_id: int,
    action_name: str,
    action_level: str,
    action_type: str = ActionTypeEnum.ACTION.value,
    status: str = ActionStatusEnum.SUCCESS.value,
    operator_id: int | None = None,
    operator_type: str | None = None,
    conversation_id: int | None = None,
    execution_decision_id: int | None = None,
    trace_id: str | None = None,
    tool_call_id: str | None = None,
    skill_id: int | None = None,
    request_data: dict[str, Any] | None = None,
    response_data: dict[str, Any] | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    normalize_payload_fn: Callable[
        [dict[str, Any] | None],
        dict[str, Any] | None,
    ] = _normalize_audit_payload,
    load_agent_snapshot_fn: Callable[
        [AsyncSession, int],
        Awaitable[dict[str, Any]],
    ] = _load_agent_snapshot,
    load_operator_snapshot_fn: Callable[..., Awaitable[dict[str, Any]]] = (
        _load_operator_snapshot
    ),
    normalize_operator_type_fn: Callable[
        [str | None],
        str | None,
    ] = _normalize_operator_type,
) -> AIActionLog:
    """
    写入 AI 操作审计日志 / Persist an AI action audit log row.
    """
    normalized_request_data = normalize_payload_fn(request_data)
    normalized_response_data = normalize_payload_fn(response_data)
    agent_snapshot = await load_agent_snapshot_fn(db, agent_id)
    operator_snapshot = (
        await load_operator_snapshot_fn(
            db,
            tenant_id=tenant_id,
            operator_id=operator_id,
            operator_type=operator_type,
        )
        if operator_id
        else {"operator_type": normalize_operator_type_fn(operator_type)}
    )

    log = AIActionLog(
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        execution_decision_id=execution_decision_id,
        trace_id=trace_id or trace_id_var.get() or None,
        tool_call_id=tool_call_id,
        skill_id=skill_id,
        operator_id=operator_id,
        operator_type=operator_snapshot.get("operator_type"),
        agent_name_snapshot=agent_snapshot.get("agent_name_snapshot"),
        agent_avatar_snapshot=agent_snapshot.get("agent_avatar_snapshot"),
        operator_name_snapshot=operator_snapshot.get("operator_name_snapshot"),
        operator_nickname_snapshot=operator_snapshot.get(
            "operator_nickname_snapshot",
        ),
        operator_avatar_snapshot=operator_snapshot.get("operator_avatar_snapshot"),
        operator_snapshot=operator_snapshot.get("operator_snapshot"),
        action_name=action_name,
        action_type=action_type,
        action_level=action_level,
        request_data=normalized_request_data,
        response_data=normalized_response_data,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(log)
    await db.flush()
    return log


__all__ = ["write_ai_action_log"]
