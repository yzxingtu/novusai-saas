"""
AI 操作审计日志 Service / AI Action Log Service

提供审计日志的查询、统计与写入辅助能力
Provides audit log query/statistics services and write helpers.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import GlobalService, TenantService
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.models.ai.action_log import AIActionLog
from app.repositories.ai.action_log_repository import (
    AIActionLogRepository,
    AdminAIActionLogRepository,
)


def resolve_action_level(
    action_name: str,
    *,
    default: str = ActionLevelEnum.SAFE_WRITE.value,
) -> str:
    """
    根据动作名推断安全等级 / Infer action level from action name.
    """
    normalized = (action_name or "").strip().lower()
    if normalized.startswith(("delete", "remove", "drop")):
        return ActionLevelEnum.DANGEROUS.value
    if normalized.startswith(("get", "list", "read", "search", "view", "refresh")):
        return ActionLevelEnum.READ.value
    return default


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
    conversation_id: int | None = None,
    skill_id: int | None = None,
    request_data: dict[str, Any] | None = None,
    response_data: dict[str, Any] | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> AIActionLog:
    """
    写入 AI 操作审计日志 / Persist an AI action audit log row.
    """
    log = AIActionLog(
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        skill_id=skill_id,
        operator_id=operator_id,
        action_name=action_name,
        action_type=action_type,
        action_level=action_level,
        request_data=request_data,
        response_data=response_data,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(log)
    await db.flush()
    return log


class AIActionLogService(TenantService[AIActionLog, AIActionLogRepository]):
    """
    AI 操作审计日志 Service / AI Action Log Service.

    只读服务，不提供 create/update/delete
    """

    model = AIActionLog
    repository_class = AIActionLogRepository

    async def get_stats(self) -> dict:
        """获取审计统计信息 / Get audit statistics."""
        return await self.repo.get_stats()

    async def get_type_distribution(self) -> list[dict]:
        """获取操作类型分布 / Get action type distribution."""
        return await self.repo.get_type_distribution()


class AdminAIActionLogService(GlobalService[AIActionLog, AdminAIActionLogRepository]):
    """
    平台端 AI 操作审计日志 Service / Admin AI Action Log Service.
    """

    model = AIActionLog
    repository_class = AdminAIActionLogRepository

    async def get_stats(self) -> dict:
        return await self.repo.get_stats()

    async def get_type_distribution(self) -> list[dict]:
        return await self.repo.get_type_distribution()


__all__ = [
    "AIActionLogService",
    "AdminAIActionLogService",
    "resolve_action_level",
    "write_ai_action_log",
]
