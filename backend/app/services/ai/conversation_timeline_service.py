"""
Conversation timeline read-model helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.action_log import AIActionLog
from app.models.ai.call_log import AICallLog
from app.models.ai.execution_decision import ExecutionDecision
from app.services.ai.agent_chat_interaction_support import (
    strip_legacy_interaction_mode_fields,
)
from app.services.ai.conversation_payload_sanitizer import (
    strip_assistant_legacy_turn_projection_fields,
)


class ConversationTimelineService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        memory_tenant_id: int,
        format_dt: Callable[[datetime | None], str | None],
    ) -> None:
        self.db = db
        self.memory_tenant_id = memory_tenant_id
        self._format_dt = format_dt

    async def get_conversation_timeline(
        self,
        *,
        conversation_id: int,
        conversation: Any,
        messages: list[Any],
    ) -> list[dict[str, Any]]:
        _conversation = conversation
        items: list[dict[str, Any]] = []
        for message in messages:
            metadata = strip_legacy_interaction_mode_fields(
                dict(getattr(message, "metadata_", {}) or {})
            )
            message_payload = strip_assistant_legacy_turn_projection_fields(
                {"role": message.role, "metadata": metadata}
            )
            metadata = message_payload.get("metadata")
            items.append(
                {
                    "type": f"message:{message.role}",
                    "occurred_at": self._format_dt(message.created_at) or "",
                    "status": "completed",
                    "title": f"message.{message.role}",
                    "summary": (message.content or "")[:300] or None,
                    "tool_name": message.tool_name,
                    "risk_level": None,
                    "auto_approved": None,
                    "correlation_key": None,
                    "trace_id": None,
                    "detail_payload": {
                        "message_id": message.id,
                        "metadata": metadata or None,
                        "tool_call_id": message.tool_call_id,
                    },
                }
            )

        decisions = (
            (
                await self.db.execute(
                    select(ExecutionDecision)
                    .where(
                        ExecutionDecision.tenant_id == self.memory_tenant_id,
                        ExecutionDecision.conversation_id == conversation_id,
                        ExecutionDecision.is_deleted.is_(False),
                    )
                    .order_by(ExecutionDecision.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for decision in decisions:
            items.append(
                {
                    "type": "execution_decision",
                    "occurred_at": self._format_dt(decision.created_at) or "",
                    "status": decision.status,
                    "title": decision.decision_type,
                    "summary": decision.reason,
                    "tool_name": decision.tool_name,
                    "risk_level": decision.risk_level,
                    "auto_approved": bool(decision.auto_approved),
                    "correlation_key": decision.correlation_key,
                    "trace_id": None,
                    "detail_payload": strip_legacy_interaction_mode_fields(
                        decision.to_dict()
                    ),
                }
            )

        action_logs = (
            (
                await self.db.execute(
                    select(AIActionLog)
                    .where(
                        AIActionLog.tenant_id == self.memory_tenant_id,
                        AIActionLog.conversation_id == conversation_id,
                        AIActionLog.is_deleted.is_(False),
                    )
                    .order_by(AIActionLog.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for action_log in action_logs:
            items.append(
                {
                    "type": "action_log",
                    "occurred_at": self._format_dt(action_log.created_at) or "",
                    "status": action_log.status,
                    "title": action_log.action_name,
                    "summary": action_log.error_message or None,
                    "tool_name": action_log.action_name,
                    "risk_level": action_log.action_level,
                    "auto_approved": None,
                    "correlation_key": None,
                    "trace_id": action_log.trace_id,
                    "detail_payload": action_log.to_dict(),
                }
            )

        call_logs = (
            (
                await self.db.execute(
                    select(AICallLog)
                    .where(
                        AICallLog.tenant_id == self.memory_tenant_id,
                        AICallLog.conversation_id == conversation_id,
                        AICallLog.is_deleted.is_(False),
                    )
                    .order_by(AICallLog.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        for call_log in call_logs:
            items.append(
                {
                    "type": "call_log",
                    "occurred_at": self._format_dt(call_log.created_at) or "",
                    "status": call_log.status,
                    "title": call_log.request_type,
                    "summary": call_log.error_message or None,
                    "tool_name": None,
                    "risk_level": None,
                    "auto_approved": None,
                    "correlation_key": None,
                    "trace_id": call_log.trace_id,
                    "detail_payload": call_log.to_dict(),
                }
            )

        call_log_summary = await self.build_call_log_summary(conversation_id)
        if call_log_summary:
            items.append(
                {
                    "type": "call_log_summary",
                    "occurred_at": self._format_dt(call_log_summary.get("last_call_at"))
                    or "",
                    "status": "summary",
                    "title": "call_log_summary",
                    "summary": (
                        f"{call_log_summary['call_count']} calls, "
                        f"{call_log_summary['total_tokens']} tokens"
                    ),
                    "tool_name": None,
                    "risk_level": None,
                    "auto_approved": None,
                    "correlation_key": None,
                    "trace_id": None,
                    "detail_payload": call_log_summary,
                }
            )

        items.sort(key=lambda item: item.get("occurred_at") or "")
        return items

    async def build_call_log_summary(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        stmt = select(
            func.count(AICallLog.id).label("call_count"),
            func.coalesce(func.sum(AICallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost), 0).label("total_cost"),
            func.max(AICallLog.created_at).label("last_call_at"),
        ).where(
            AICallLog.tenant_id == self.memory_tenant_id,
            AICallLog.conversation_id == conversation_id,
            AICallLog.is_deleted.is_(False),
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if not row or (row.call_count or 0) == 0:
            return None
        return {
            "call_count": row.call_count or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "last_call_at": row.last_call_at,
        }
