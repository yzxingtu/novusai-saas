"""
AI 操作审计日志 Service / AI Action Log Service

提供审计日志的查询、统计与写入辅助能力
Provides audit log query/statistics services and write helpers.
"""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel
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


def _normalize_audit_value(value: Any) -> Any:
    """
    Normalize audit payload values to JSON-safe structures.
    将审计日志值规范化为 JSON 安全结构。
    """
    if value is None or isinstance(value, (bool, float, int, str)):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return {
            key: _normalize_audit_value(item)
            for key, item in value.to_dict().items()
        }

    if is_dataclass(value) and not isinstance(value, type):
        return _normalize_audit_value(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): _normalize_audit_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, set, tuple)):
        return [_normalize_audit_value(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _normalize_audit_value(model_dump())

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _normalize_audit_value(to_dict())
        except TypeError:
            pass

    return str(value)


def _normalize_audit_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Normalize top-level audit payload before persisting.
    写入前规范化顶层审计载荷。
    """
    if payload is None:
        return None

    normalized = _normalize_audit_value(payload)
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


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
    normalized_request_data = _normalize_audit_payload(request_data)
    normalized_response_data = _normalize_audit_payload(response_data)

    log = AIActionLog(
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        skill_id=skill_id,
        operator_id=operator_id,
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
