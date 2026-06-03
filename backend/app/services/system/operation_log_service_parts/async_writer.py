"""Async writer helpers for operation logs."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.identity_snapshot import load_identity_snapshot
from app.core.logging import LoggerMixin
from app.enums.log import UserTypeEnum

from .payloads import build_operation_log_payload, clone_operation_log_payload


class _ModuleLogger(LoggerMixin):
    """operation_log_service module logger."""


_module_logger = _ModuleLogger()


async def _fetch_user_info(
    db: AsyncSession,
    user_type: str | None,
    user_id: int | None,
) -> dict[str, str | None] | None:
    if not user_type or not user_id:
        return None

    try:
        if user_type == UserTypeEnum.ADMIN.value:
            from app.models import Admin

            row = (
                await db.execute(
                    select(Admin.username, Admin.nickname).where(Admin.id == user_id)
                )
            ).first()
            if row:
                return {"username": row[0], "nickname": row[1]}

        if user_type == UserTypeEnum.TENANT_ADMIN.value:
            from app.models import TenantAdmin

            row = (
                await db.execute(
                    select(TenantAdmin.username, TenantAdmin.nickname).where(
                        TenantAdmin.id == user_id
                    )
                )
            ).first()
            if row:
                return {"username": row[0], "nickname": row[1]}

        if user_type == UserTypeEnum.TENANT_USER.value:
            from app.models import TenantUser

            row = (
                await db.execute(
                    select(TenantUser.username, TenantUser.nickname).where(
                        TenantUser.id == user_id
                    )
                )
            ).first()
            if row:
                return {"username": row[0], "nickname": row[1]}
    except Exception:
        _module_logger.logger.debug(
            "Failed to resolve user info for {}:{}",
            user_type,
            user_id,
        )

    return None


async def _write_log_async(log_data: dict[str, Any]) -> None:
    try:
        payload = clone_operation_log_payload(log_data)
        async with async_session_factory() as db:
            if not payload.get("identity_snapshot"):
                snapshot = await load_identity_snapshot(
                    db,
                    user_type=payload.get("user_type"),
                    user_id=payload.get("user_id"),
                    tenant_id=payload.get("tenant_id"),
                    fallback_username=payload.get("username"),
                    fallback_nickname=payload.get("nickname"),
                )
                if snapshot:
                    payload["identity_snapshot"] = snapshot
                    payload["username"] = payload.get("username") or snapshot.get(
                        "username"
                    )
                    payload["nickname"] = payload.get("nickname") or snapshot.get(
                        "nickname"
                    )

            if (
                not payload.get("username") or not payload.get("nickname")
            ) and payload.get("user_id"):
                user_info = await _fetch_user_info(
                    db,
                    user_type=payload.get("user_type"),
                    user_id=payload.get("user_id"),
                )
                if user_info:
                    if not payload.get("username") and user_info.get("username"):
                        payload["username"] = user_info["username"]
                    if not payload.get("nickname") and user_info.get("nickname"):
                        payload["nickname"] = user_info["nickname"]

            from app.services.system.operation_log_service import OperationLogService

            service = OperationLogService(db)
            await service.create_log(**payload)
            await db.commit()
    except Exception as exc:
        _module_logger.logger.error("Failed to write operation log: {}", exc)


def create_log_async(
    tenant_id: int | None,
    user_type: str,
    user_id: int | None,
    username: str | None,
    module: str | None,
    action: str | None,
    resource: str | None,
    method: str,
    path: str,
    query_params: dict | None = None,
    request_body: dict | None = None,
    status_code: int | None = None,
    response_code: int | None = None,
    response_message: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    duration_ms: int | None = None,
    nickname: str | None = None,
    trace_id: str | None = None,
    identity_snapshot: dict[str, Any] | None = None,
) -> None:
    payload = build_operation_log_payload(
        tenant_id=tenant_id,
        user_type=user_type,
        user_id=user_id,
        username=username,
        module=module,
        action=action,
        resource=resource,
        method=method,
        path=path,
        query_params=query_params,
        request_body=request_body,
        status_code=status_code,
        response_code=response_code,
        response_message=response_message,
        ip=ip,
        user_agent=user_agent,
        duration_ms=duration_ms,
        nickname=nickname,
        trace_id=trace_id,
        identity_snapshot=identity_snapshot,
    )
    try:
        asyncio.get_running_loop().create_task(_write_log_async(payload))
    except RuntimeError:
        asyncio.run(_write_log_async(payload))


__all__ = [
    "_fetch_user_info",
    "_write_log_async",
    "create_log_async",
]
