"""
Runtime diagnostics query/read-model helpers.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, select

from app.core.base_model import utc_now
from app.enums.agent import MessageRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.call_log import AICallLog
from app.services.ai.conversation_diagnostics_projector import (
    ConversationDiagnosticsProjector,
)
from app.services.ai.conversation_service import ConversationService
from app.services.ai.monitoring_read_model_projector import (
    MonitoringReadModelProjector,
)
from app.services.ai.runtime_diagnostics_turn_projector import (
    RuntimeDiagnosticsTurnProjector,
)
from app.services.ai.turn_failure_normalizer import resolve_failure_projection

if TYPE_CHECKING:
    from app.services.ai.runtime_diagnostics_service import RuntimeDiagnosticsService


class RuntimeDiagnosticsQueryService:
    def __init__(self, service: RuntimeDiagnosticsService) -> None:
        self.service = service

    @staticmethod
    def _logical_turn_key(log: AICallLog) -> str:
        trace_id = str(getattr(log, "trace_id", "") or "").strip()
        if trace_id:
            return f"trace:{trace_id}"
        return f"log:{getattr(log, 'id', 0)}"

    @classmethod
    def _group_logs_by_turn(
        cls,
        logs: list[AICallLog],
    ) -> list[list[AICallLog]]:
        grouped: dict[str, list[AICallLog]] = {}
        ordered_keys: list[str] = []
        for log in logs:
            key = cls._logical_turn_key(log)
            if key not in grouped:
                grouped[key] = []
                ordered_keys.append(key)
            grouped[key].append(log)
        return [grouped[key] for key in ordered_keys]

    @staticmethod
    def _message_role(message: Any) -> str:
        return str(getattr(message, "role", "") or "").strip()

    @classmethod
    def _assistant_message_has_authoritative_completed_output(
        cls,
        message: Any,
    ) -> bool:
        if cls._message_role(message) != MessageRoleEnum.ASSISTANT.value:
            return False
        if not str(getattr(message, "content", "") or "").strip():
            return False

        metadata = RuntimeDiagnosticsTurnProjector.message_metadata(message)
        diagnostics = (
            ConversationDiagnosticsProjector.extract_turn_diagnostics_from_metadata(
                metadata
            )
        )
        turn_flow = (
            metadata.get("turn_flow")
            if isinstance(metadata.get("turn_flow"), dict)
            else diagnostics.get("turn_flow")
        )
        projection = resolve_failure_projection(
            diagnostics=diagnostics,
            turn_flow=turn_flow if isinstance(turn_flow, dict) else None,
        )
        return bool(
            projection.get("authoritative_completed_success")
            and projection.get("turn_outcome") == "success"
            and not projection.get("failure_kind")
        )

    @classmethod
    def _group_messages_by_user_turn(cls, messages: list[Any]) -> list[list[Any]]:
        groups: list[list[Any]] = []
        current_group: list[Any] = []
        for message in messages:
            role = cls._message_role(message)
            if role == MessageRoleEnum.USER.value:
                if current_group:
                    groups.append(current_group)
                current_group = [message]
                continue
            if current_group:
                current_group.append(message)
            elif role == MessageRoleEnum.ASSISTANT.value:
                groups.append([message])
        if current_group:
            groups.append(current_group)
        return groups

    @classmethod
    def _select_terminal_assistant_message(
        cls,
        assistant_messages: list[Any],
    ) -> Any | None:
        if not assistant_messages:
            return None
        for message in reversed(assistant_messages):
            if cls._assistant_message_has_authoritative_completed_output(message):
                return message

        anchor_messages = [
            message
            for message in assistant_messages
            if RuntimeDiagnosticsTurnProjector.assistant_message_is_turn_anchor(message)
        ]
        for message in reversed(anchor_messages):
            if str(getattr(message, "content", "") or "").strip():
                return message
        if anchor_messages:
            return anchor_messages[-1]
        return assistant_messages[-1]

    @classmethod
    def _select_conversation_turn_message(
        cls,
        messages: list[Any],
        *,
        turn: int,
    ) -> Any | None:
        user_turn_groups = cls._group_messages_by_user_turn(messages)
        if 0 < turn <= len(user_turn_groups):
            assistant_messages = [
                message
                for message in user_turn_groups[turn - 1]
                if cls._message_role(message) == MessageRoleEnum.ASSISTANT.value
            ]
            selected_message = cls._select_terminal_assistant_message(
                assistant_messages
            )
            if selected_message is not None:
                return selected_message

        assistant_messages = [
            message
            for message in messages
            if cls._message_role(message) == MessageRoleEnum.ASSISTANT.value
        ]
        turn_anchor_messages = [
            message
            for message in assistant_messages
            if RuntimeDiagnosticsTurnProjector.assistant_message_is_turn_anchor(message)
        ]
        target_messages = turn_anchor_messages or assistant_messages
        if turn <= 0 or turn > len(target_messages):
            return None
        return target_messages[turn - 1]

    @staticmethod
    def _conversation_turn_has_authoritative_completed_output(
        conversation_turn: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(conversation_turn, dict):
            return False
        if not str(conversation_turn.get("assistant_content") or "").strip():
            return False
        diagnostics = (
            dict(conversation_turn.get("diagnostics") or {})
            if isinstance(conversation_turn.get("diagnostics"), dict)
            else {}
        )
        metadata = (
            dict(conversation_turn.get("metadata") or {})
            if isinstance(conversation_turn.get("metadata"), dict)
            else {}
        )
        turn_flow = metadata.get("turn_flow") or diagnostics.get("turn_flow")
        projection = resolve_failure_projection(
            diagnostics=diagnostics,
            turn_flow=turn_flow if isinstance(turn_flow, dict) else None,
        )
        return bool(
            projection.get("authoritative_completed_success")
            and projection.get("turn_outcome") == "success"
            and not projection.get("failure_kind")
        )

    @classmethod
    def _select_related_call_log(
        cls,
        logs: list[AICallLog],
        *,
        conversation_turn: dict[str, Any] | None = None,
    ) -> AICallLog | None:
        if not logs:
            return None
        if cls._conversation_turn_has_authoritative_completed_output(conversation_turn):
            for log in reversed(logs):
                if str(getattr(log, "status", "") or "").strip() == "success":
                    return log
        return logs[-1]

    async def aggregate_recent_failures(
        self,
        *,
        tenant_id: int | None,
    ) -> list[dict[str, Any]]:
        base = self.service
        since = utc_now() - timedelta(hours=24)
        stmt: Select[tuple[AICallLog]] = (
            select(AICallLog)
            .where(
                AICallLog.is_deleted.is_(False),
                AICallLog.created_at >= since,
            )
            .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
            .limit(500)
        )
        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        result = await base.db.execute(stmt)
        logs = list(result.scalars().all())

        failure_counter: Counter[tuple[str | None, ...]] = Counter()
        collected = 0
        for log in logs:
            diagnostics = MonitoringReadModelProjector.extract_call_trace_diagnostics(
                log.request_metadata
            )
            if not base._is_failed_call(log, diagnostics):
                continue
            selected_tools = diagnostics.get("selected_tool_names") or []
            key = (
                diagnostics.get("failure_kind"),
                getattr(log, "provider_name_snapshot", None),
                getattr(log, "model_name_snapshot", None),
                getattr(log, "agent_name_snapshot", None),
                selected_tools[0] if selected_tools else None,
                diagnostics.get("contract_breach_type"),
            )
            failure_counter[key] += 1
            collected += 1
            if collected >= 50:
                break

        return [
            {
                "failure_kind": failure_kind,
                "provider": provider_name,
                "model": model_name,
                "agent": agent_name,
                "tool": tool_name,
                "contract_breach_type": contract,
                "count": count,
            }
            for (
                failure_kind,
                provider_name,
                model_name,
                agent_name,
                tool_name,
                contract,
            ), count in failure_counter.most_common()
        ]

    async def resolve_conversation_turn(
        self,
        *,
        conversation_id: int,
        turn: int,
    ) -> dict[str, Any]:
        base = self.service
        service, conversation = await ConversationService.get_service_for_conversation(
            base.db,
            conversation_id,
        )
        messages = await service.get_messages_for_conversation(conversation_id)
        target_message = self._select_conversation_turn_message(messages, turn=turn)
        if target_message is None:
            raise NotFoundException(message="Conversation turn not found")

        return RuntimeDiagnosticsTurnProjector.build_conversation_turn_payload(
            conversation_id=conversation.id,
            message=target_message,
        )

    async def resolve_related_call_log_for_conversation_turn(
        self,
        *,
        conversation_id: int,
        turn: int,
        conversation_turn: dict[str, Any] | None = None,
    ) -> AICallLog | None:
        base = self.service
        result = await base.db.execute(
            select(AICallLog)
            .where(
                AICallLog.conversation_id == conversation_id,
                AICallLog.is_deleted.is_(False),
            )
            .order_by(AICallLog.created_at.asc(), AICallLog.id.asc())
        )
        logs = list(result.scalars().all())
        groups = self._group_logs_by_turn(logs)
        if turn <= 0 or turn > len(groups):
            return None
        return self._select_related_call_log(
            groups[turn - 1],
            conversation_turn=conversation_turn,
        )

    async def resolve_conversation_turn_for_call_log(
        self,
        *,
        call_log: AICallLog | None,
    ) -> dict[str, Any] | None:
        if call_log is None:
            return None
        conversation_id = getattr(call_log, "conversation_id", None)
        if conversation_id is None:
            return None
        result = await self.service.db.execute(
            select(AICallLog)
            .where(
                AICallLog.conversation_id == conversation_id,
                AICallLog.is_deleted.is_(False),
            )
            .order_by(AICallLog.created_at.asc(), AICallLog.id.asc())
        )
        logs = list(result.scalars().all())
        key = self._logical_turn_key(call_log)
        groups = self._group_logs_by_turn(logs)
        turn = next(
            (
                index + 1
                for index, group in enumerate(groups)
                if group and self._logical_turn_key(group[0]) == key
            ),
            None,
        )
        if turn is None:
            return None
        try:
            return await self.resolve_conversation_turn(
                conversation_id=conversation_id,
                turn=turn,
            )
        except NotFoundException:
            return None

    async def resolve_call_log(
        self,
        *,
        trace_id: str | None,
        call_log_id: int | None,
        conversation_id: int | None,
        turn: int | None,
    ) -> AICallLog:
        base = self.service
        if call_log_id is not None:
            result = await base.db.execute(
                select(AICallLog).where(
                    AICallLog.id == call_log_id,
                    AICallLog.is_deleted.is_(False),
                )
            )
            call_log = result.scalar_one_or_none()
            if call_log is None:
                raise NotFoundException(message="AI call log not found")
            return call_log

        if trace_id:
            result = await base.db.execute(
                select(AICallLog)
                .where(
                    AICallLog.trace_id == trace_id,
                    AICallLog.is_deleted.is_(False),
                )
                .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
                .limit(1)
            )
            call_log = result.scalar_one_or_none()
            if call_log is None:
                raise NotFoundException(message="AI call log not found")
            return call_log

        if conversation_id is not None and turn is not None:
            result = await base.db.execute(
                select(AICallLog)
                .where(
                    AICallLog.conversation_id == conversation_id,
                    AICallLog.is_deleted.is_(False),
                )
                .order_by(AICallLog.created_at.asc(), AICallLog.id.asc())
            )
            logs = list(result.scalars().all())
            groups = self._group_logs_by_turn(logs)
            if turn <= 0 or turn > len(groups):
                raise NotFoundException(message="AI call log not found")
            return groups[turn - 1][-1]

        raise BusinessException(
            message="trace_id, call_log_id, or conversation_id+turn is required"
        )
