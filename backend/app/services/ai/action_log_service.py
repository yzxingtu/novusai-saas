"""
AI 操作审计日志 Service / AI Action Log Service

提供审计日志的查询、统计与写入辅助能力
Provides audit log query/statistics services and write helpers.
"""

import inspect
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_model import BaseModel
from app.core.base_service import GlobalService, TenantService
from app.core.response import serialize_datetime_for_api
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.middleware.trace import trace_id_var
from app.models.ai.action_log import AIActionLog
from app.models.ai.agent import Agent
from app.models.system.admin import Admin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_admin import TenantAdmin
from app.models.tenant.tenant_user import TenantUser
from app.repositories.ai.action_log_repository import (
    AdminAIActionLogRepository,
    AIActionLogRepository,
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

    if isinstance(value, datetime):
        return serialize_datetime_for_api(value)

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return {
            key: _normalize_audit_value(item) for key, item in value.to_dict().items()
        }

    if is_dataclass(value) and not isinstance(value, type):
        return _normalize_audit_value(asdict(value))

    if isinstance(value, dict):
        return {str(key): _normalize_audit_value(item) for key, item in value.items()}

    if isinstance(value, (list, set, tuple)):
        return [_normalize_audit_value(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if (
        callable(model_dump)
        and not inspect.iscoroutinefunction(model_dump)
        and not isinstance(model_dump, AsyncMock)
    ):
        return _normalize_audit_value(model_dump())

    to_dict = getattr(value, "to_dict", None)
    if (
        callable(to_dict)
        and not inspect.iscoroutinefunction(to_dict)
        and not isinstance(to_dict, AsyncMock)
    ):
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


def _default_agent_meta() -> dict[str, Any]:
    return {
        "agent_avatar": None,
        "agent_name": None,
    }


def _default_operator_meta() -> dict[str, Any]:
    return {
        "operator_avatar": None,
        "operator_name": None,
        "operator_nickname": None,
        "operator_type": None,
    }


def _normalize_operator_type(operator_type: str | None) -> str | None:
    if not operator_type:
        return None
    if operator_type == "admin":
        return "platform_admin"
    return operator_type


async def _execute_first(
    db: AsyncSession,
    stmt: Any,
) -> Any:
    result = await db.execute(stmt)
    row = result.first()
    if inspect.isawaitable(row):
        row = await row
    return row


def _resolve_agent_meta(
    item: dict[str, Any],
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_meta = live_meta or {}
    return {
        "agent_avatar": item.get("agent_avatar_snapshot")
        or live_meta.get("agent_avatar"),
        "agent_name": item.get("agent_name_snapshot") or live_meta.get("agent_name"),
    }


def _resolve_operator_meta(
    item: dict[str, Any],
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_meta = live_meta or {}
    return {
        "operator_avatar": item.get("operator_avatar_snapshot")
        or live_meta.get("operator_avatar"),
        "operator_name": item.get("operator_name_snapshot")
        or live_meta.get("operator_name"),
        "operator_nickname": item.get("operator_nickname_snapshot")
        or live_meta.get("operator_nickname"),
        "operator_type": _normalize_operator_type(item.get("operator_type"))
        or _normalize_operator_type(live_meta.get("operator_type")),
    }


async def _load_agent_snapshot(
    db: AsyncSession,
    agent_id: int,
) -> dict[str, Any]:
    if not agent_id or agent_id <= 0:
        return {}

    stmt = select(Agent.name, Agent.avatar).where(
        Agent.id == agent_id,
        Agent.is_deleted.is_(False),
    )
    row = await _execute_first(db, stmt)
    if not row:
        return {}
    return {
        "agent_avatar_snapshot": row.avatar,
        "agent_name_snapshot": row.name,
    }


async def _load_operator_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
    operator_id: int,
    operator_type: str | None,
) -> dict[str, Any]:
    normalized_type = _normalize_operator_type(operator_type)
    if not operator_id:
        return {
            "operator_type": normalized_type,
        }

    if normalized_type == "platform_admin" or tenant_id == PLATFORM_TENANT_ID:
        stmt = select(Admin.username, Admin.nickname, Admin.avatar).where(
            Admin.id == operator_id,
            Admin.is_deleted.is_(False),
        )
        row = await _execute_first(db, stmt)
        if row:
            return {
                "operator_avatar_snapshot": row.avatar,
                "operator_name_snapshot": row.username,
                "operator_nickname_snapshot": row.nickname,
                "operator_type": "platform_admin",
            }

    if normalized_type == "tenant_user":
        stmt = select(
            TenantUser.username,
            TenantUser.nickname,
            TenantUser.avatar,
        ).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.id == operator_id,
            TenantUser.is_deleted.is_(False),
        )
        row = await _execute_first(db, stmt)
        if row:
            return {
                "operator_avatar_snapshot": row.avatar,
                "operator_name_snapshot": row.username,
                "operator_nickname_snapshot": row.nickname,
                "operator_type": "tenant_user",
            }

    stmt = select(
        TenantAdmin.username,
        TenantAdmin.nickname,
        TenantAdmin.avatar,
    ).where(
        TenantAdmin.tenant_id == tenant_id,
        TenantAdmin.id == operator_id,
        TenantAdmin.is_deleted.is_(False),
    )
    row = await _execute_first(db, stmt)
    if row:
        return {
            "operator_avatar_snapshot": row.avatar,
            "operator_name_snapshot": row.username,
            "operator_nickname_snapshot": row.nickname,
            "operator_type": "tenant_admin",
        }

    user_stmt = select(
        TenantUser.username,
        TenantUser.nickname,
        TenantUser.avatar,
    ).where(
        TenantUser.tenant_id == tenant_id,
        TenantUser.id == operator_id,
        TenantUser.is_deleted.is_(False),
    )
    user_row = await _execute_first(db, user_stmt)
    if user_row:
        return {
            "operator_avatar_snapshot": user_row.avatar,
            "operator_name_snapshot": user_row.username,
            "operator_nickname_snapshot": user_row.nickname,
            "operator_type": "tenant_user",
        }

    return {
        "operator_type": normalized_type,
    }


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
    normalized_request_data = _normalize_audit_payload(request_data)
    normalized_response_data = _normalize_audit_payload(response_data)
    agent_snapshot = await _load_agent_snapshot(db, agent_id)
    operator_snapshot = (
        await _load_operator_snapshot(
            db,
            tenant_id=tenant_id,
            operator_id=operator_id,
            operator_type=operator_type,
        )
        if operator_id
        else {"operator_type": _normalize_operator_type(operator_type)}
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

    async def _load_agent_meta_map(
        self,
        agent_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        if not agent_ids:
            return {}

        stmt = select(Agent.id, Agent.name, Agent.avatar).where(
            Agent.id.in_(agent_ids),
            Agent.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return {
            row.id: {
                "agent_avatar": row.avatar,
                "agent_name": row.name,
            }
            for row in result.all()
        }

    async def _load_operator_meta_map(
        self,
        operator_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        if not operator_ids:
            return {}

        stmt = select(
            TenantAdmin.id,
            TenantAdmin.username,
            TenantAdmin.nickname,
            TenantAdmin.avatar,
        ).where(
            TenantAdmin.tenant_id == self.tenant_id,
            TenantAdmin.id.in_(operator_ids),
            TenantAdmin.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        operator_meta_map = {
            row.id: {
                "operator_avatar": row.avatar,
                "operator_name": row.username,
                "operator_nickname": row.nickname,
                "operator_type": "tenant_admin",
            }
            for row in result.all()
        }

        missing_ids = operator_ids - set(operator_meta_map)
        if not missing_ids:
            return operator_meta_map

        user_stmt = select(
            TenantUser.id,
            TenantUser.username,
            TenantUser.nickname,
            TenantUser.avatar,
        ).where(
            TenantUser.tenant_id == self.tenant_id,
            TenantUser.id.in_(missing_ids),
            TenantUser.is_deleted.is_(False),
        )
        user_result = await self.db.execute(user_stmt)
        for row in user_result.all():
            operator_meta_map[row.id] = {
                "operator_avatar": row.avatar,
                "operator_name": row.username,
                "operator_nickname": row.nickname,
                "operator_type": "tenant_user",
            }
        return operator_meta_map

    async def serialize_log(self, log: AIActionLog) -> dict[str, Any]:
        item = log.to_dict()
        agent_meta_map = await self._load_agent_meta_map(
            {item["agent_id"]} if item.get("agent_id") else set(),
        )
        operator_meta_map = await self._load_operator_meta_map(
            {item["operator_id"]} if item.get("operator_id") else set(),
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
                operator_meta_map.get(item.get("operator_id"), {}),
            ),
        )
        return item

    async def serialize_logs(self, logs: list[AIActionLog]) -> list[dict[str, Any]]:
        agent_meta_map = await self._load_agent_meta_map(
            {log.agent_id for log in logs if log.agent_id},
        )
        operator_meta_map = await self._load_operator_meta_map(
            {log.operator_id for log in logs if log.operator_id},
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
                    operator_meta_map.get(log.operator_id, {}),
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


class AdminAIActionLogService(GlobalService[AIActionLog, AdminAIActionLogRepository]):
    """
    平台端 AI 操作审计日志 Service / Admin AI Action Log Service.
    """

    model = AIActionLog
    repository_class = AdminAIActionLogRepository

    async def _load_agent_meta_map(
        self,
        agent_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        if not agent_ids:
            return {}

        stmt = select(Agent.id, Agent.name, Agent.avatar).where(
            Agent.id.in_(agent_ids),
            Agent.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return {
            row.id: {
                "agent_avatar": row.avatar,
                "agent_name": row.name,
            }
            for row in result.all()
        }

    async def _load_tenant_meta_map(
        self,
        tenant_ids: set[int],
    ) -> dict[int, dict[str, str | None]]:
        positive_tenant_ids = {
            tenant_id for tenant_id in tenant_ids if tenant_id > PLATFORM_TENANT_ID
        }
        tenant_meta_map: dict[int, dict[str, str | None]] = {
            PLATFORM_TENANT_ID: {
                "tenant_name": None,
                "tenant_code": "platform_admin",
            },
        }

        if not positive_tenant_ids:
            return tenant_meta_map

        stmt = select(Tenant.id, Tenant.name, Tenant.code).where(
            Tenant.id.in_(positive_tenant_ids),
            Tenant.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        for row in result.all():
            tenant_meta_map[row.id] = {
                "tenant_name": row.name,
                "tenant_code": row.code,
            }
        return tenant_meta_map

    async def _load_operator_meta_map(
        self,
        logs: list[AIActionLog],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        platform_operator_ids = {
            log.operator_id
            for log in logs
            if (log.tenant_id or PLATFORM_TENANT_ID) == PLATFORM_TENANT_ID
            and log.operator_id
        }
        tenant_operator_pairs = {
            (log.tenant_id, log.operator_id)
            for log in logs
            if (log.tenant_id or PLATFORM_TENANT_ID) != PLATFORM_TENANT_ID
            and log.tenant_id
            and log.operator_id
        }

        operator_meta_map: dict[tuple[int, int], dict[str, Any]] = {}

        if platform_operator_ids:
            stmt = select(
                Admin.id,
                Admin.username,
                Admin.nickname,
                Admin.avatar,
            ).where(
                Admin.id.in_(platform_operator_ids),
                Admin.is_deleted.is_(False),
            )
            result = await self.db.execute(stmt)
            for row in result.all():
                operator_meta_map[(PLATFORM_TENANT_ID, row.id)] = {
                    "operator_avatar": row.avatar,
                    "operator_name": row.username,
                    "operator_nickname": row.nickname,
                    "operator_type": "platform_admin",
                }

        if tenant_operator_pairs:
            tenant_ids = {tenant_id for tenant_id, _ in tenant_operator_pairs}
            operator_ids = {operator_id for _, operator_id in tenant_operator_pairs}

            stmt = select(
                TenantAdmin.tenant_id,
                TenantAdmin.id,
                TenantAdmin.username,
                TenantAdmin.nickname,
                TenantAdmin.avatar,
            ).where(
                TenantAdmin.tenant_id.in_(tenant_ids),
                TenantAdmin.id.in_(operator_ids),
                TenantAdmin.is_deleted.is_(False),
            )
            result = await self.db.execute(stmt)
            for row in result.all():
                operator_meta_map[(row.tenant_id, row.id)] = {
                    "operator_avatar": row.avatar,
                    "operator_name": row.username,
                    "operator_nickname": row.nickname,
                    "operator_type": "tenant_admin",
                }

            missing_pairs = tenant_operator_pairs - set(operator_meta_map)
            if missing_pairs:
                missing_tenant_ids = {tenant_id for tenant_id, _ in missing_pairs}
                missing_operator_ids = {operator_id for _, operator_id in missing_pairs}
                user_stmt = select(
                    TenantUser.tenant_id,
                    TenantUser.id,
                    TenantUser.username,
                    TenantUser.nickname,
                    TenantUser.avatar,
                ).where(
                    TenantUser.tenant_id.in_(missing_tenant_ids),
                    TenantUser.id.in_(missing_operator_ids),
                    TenantUser.is_deleted.is_(False),
                )
                user_result = await self.db.execute(user_stmt)
                for row in user_result.all():
                    operator_meta_map[(row.tenant_id, row.id)] = {
                        "operator_avatar": row.avatar,
                        "operator_name": row.username,
                        "operator_nickname": row.nickname,
                        "operator_type": "tenant_user",
                    }

        return operator_meta_map

    async def serialize_log(self, log: AIActionLog) -> dict[str, Any]:
        item = log.to_dict()
        tenant_id = item.get("tenant_id", PLATFORM_TENANT_ID) or PLATFORM_TENANT_ID
        tenant_meta_map = await self._load_tenant_meta_map({tenant_id})
        agent_meta_map = await self._load_agent_meta_map(
            {item["agent_id"]} if item.get("agent_id") else set(),
        )
        operator_meta_map = await self._load_operator_meta_map([log])
        item.update(_default_agent_meta())
        item.update(_default_operator_meta())
        item.update(tenant_meta_map.get(tenant_id, {}))
        item.update(
            _resolve_agent_meta(
                item,
                agent_meta_map.get(item.get("agent_id"), {}),
            ),
        )
        item.update(
            _resolve_operator_meta(
                item,
                operator_meta_map.get(
                    (tenant_id, item.get("operator_id")),
                    {},
                ),
            ),
        )
        return item

    async def serialize_logs(self, logs: list[AIActionLog]) -> list[dict[str, Any]]:
        tenant_meta_map = await self._load_tenant_meta_map(
            {log.tenant_id or PLATFORM_TENANT_ID for log in logs},
        )
        agent_meta_map = await self._load_agent_meta_map(
            {log.agent_id for log in logs if log.agent_id},
        )
        operator_meta_map = await self._load_operator_meta_map(logs)
        items: list[dict[str, Any]] = []
        for log in logs:
            item = log.to_dict()
            tenant_id = log.tenant_id or PLATFORM_TENANT_ID
            item.update(_default_agent_meta())
            item.update(_default_operator_meta())
            item.update(
                tenant_meta_map.get(tenant_id, {}),
            )
            item.update(
                _resolve_agent_meta(item, agent_meta_map.get(log.agent_id, {})),
            )
            item.update(
                _resolve_operator_meta(
                    item,
                    operator_meta_map.get((tenant_id, log.operator_id), {}),
                ),
            )
            items.append(item)
        return items

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
