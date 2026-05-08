"""
AI 操作审计日志 Service / AI Action Log Service

提供审计日志的查询、统计与写入辅助能力
Provides audit log query/statistics services and write helpers.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import TenantService
from app.enums.agent import ActionStatusEnum, ActionTypeEnum
from app.models.ai.action_log import AIActionLog
from app.repositories.ai.action_log_repository import AIActionLogRepository
from app.services.ai.action_log_service_parts.normalization import (
    _normalize_audit_payload,
    _normalize_operator_type,
    resolve_action_level,
)
from app.services.ai.action_log_service_parts.snapshots import (
    _default_agent_meta,
    _default_operator_meta,
    _load_agent_snapshot,
    _load_operator_snapshot,
    _resolve_agent_meta,
    _resolve_operator_meta,
)
from app.services.ai.action_log_service_parts.tenant_queries import (
    load_agent_meta_map as _load_tenant_agent_meta_map,
)
from app.services.ai.action_log_service_parts.tenant_queries import (
    load_operator_meta_map as _load_tenant_operator_meta_map,
)
from app.services.ai.action_log_service_parts.write import (
    write_ai_action_log as _write_ai_action_log,
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
) -> AIActionLog:
    """
    写入 AI 操作审计日志 / Persist an AI action audit log row.
    """
    return await _write_ai_action_log(
        db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        action_name=action_name,
        action_level=action_level,
        action_type=action_type,
        status=status,
        operator_id=operator_id,
        operator_type=operator_type,
        conversation_id=conversation_id,
        execution_decision_id=execution_decision_id,
        trace_id=trace_id,
        tool_call_id=tool_call_id,
        skill_id=skill_id,
        request_data=request_data,
        response_data=response_data,
        error_message=error_message,
        duration_ms=duration_ms,
        normalize_payload_fn=_normalize_audit_payload,
        load_agent_snapshot_fn=_load_agent_snapshot,
        load_operator_snapshot_fn=_load_operator_snapshot,
        normalize_operator_type_fn=_normalize_operator_type,
    )


class AIActionLogService(TenantService[AIActionLog, AIActionLogRepository]):
    """
    AI 操作审计日志 Service / AI Action Log Service.

    只读服务，不提供 create/update/delete
    """

    model = AIActionLog
    repository_class = AIActionLogRepository

    async def _load_agent_meta_map(
        self,
        agent_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        return await _load_tenant_agent_meta_map(self.db, agent_ids)

    @staticmethod
    def _resolve_operator_live_meta(
        operator_meta_map: dict[tuple[str, int], dict[str, Any]],
        operator_type: str | None,
        operator_id: int | None,
    ) -> dict[str, Any]:
        if not operator_id:
            return {}
        normalized_type = _normalize_operator_type(operator_type)
        if normalized_type:
            return operator_meta_map.get((normalized_type, operator_id), {})
        return operator_meta_map.get(
            ("tenant_admin", operator_id), {}
        ) or operator_meta_map.get(
            ("tenant_user", operator_id),
            {},
        )

    async def _load_operator_meta_map(
        self,
        operator_refs: set[tuple[str | None, int]],
    ) -> dict[tuple[str, int], dict[str, Any]]:
        return await _load_tenant_operator_meta_map(
            self.db,
            self.tenant_id,
            operator_refs,
        )

    async def serialize_log(self, log: AIActionLog) -> dict[str, Any]:
        item = log.to_dict()
        agent_meta_map = await self._load_agent_meta_map(
            {item["agent_id"]} if item.get("agent_id") else set(),
        )
        operator_meta_map = await self._load_operator_meta_map(
            {
                (
                    _normalize_operator_type(item.get("operator_type")),
                    item["operator_id"],
                )
            }
            if item.get("operator_id")
            else set(),
        )
        item.update(_default_agent_meta())
        item.update(_default_operator_meta())
        item.update(
            _resolve_agent_meta(
                item,
                agent_meta_map.get(item.get("agent_id"), {}),
            ),
        )
        item.update(
            _resolve_operator_meta(
                item,
                self._resolve_operator_live_meta(
                    operator_meta_map,
                    item.get("operator_type"),
                    item.get("operator_id"),
                ),
            ),
        )
        return item

    async def serialize_logs(self, logs: list[AIActionLog]) -> list[dict[str, Any]]:
        agent_meta_map = await self._load_agent_meta_map(
            {log.agent_id for log in logs if log.agent_id},
        )
        operator_meta_map = await self._load_operator_meta_map(
            {
                (_normalize_operator_type(log.operator_type), log.operator_id)
                for log in logs
                if log.operator_id
            },
        )

        items: list[dict[str, Any]] = []
        for log in logs:
            item = log.to_dict()
            item.update(_default_agent_meta())
            item.update(_default_operator_meta())
            item.update(
                _resolve_agent_meta(item, agent_meta_map.get(log.agent_id, {})),
            )
            item.update(
                _resolve_operator_meta(
                    item,
                    self._resolve_operator_live_meta(
                        operator_meta_map,
                        log.operator_type,
                        log.operator_id,
                    ),
                ),
            )
            items.append(item)
        return items

    async def get_stats(self) -> dict:
        """获取审计统计信息 / Get audit statistics."""
        return await self.repo.get_stats()

    async def get_type_distribution(self) -> list[dict]:
        """获取操作类型分布 / Get action type distribution."""
        return await self.repo.get_type_distribution()


__all__ = [
    "AIActionLogService",
    "resolve_action_level",
    "write_ai_action_log",
]
