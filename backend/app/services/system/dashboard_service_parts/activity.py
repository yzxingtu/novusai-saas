"""
Dashboard activity helpers / 仪表盘活动与身份补全辅助
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import (
    build_identity_select_extra,
    resolve_identity_display_name,
)
from app.models.system.operation_log import OperationLog

_LOW_SIGNAL_ACTIVITY_EXACT_PATHS = (
    "/admin/auth/me",
    "/admin/auth/refresh",
    "/admin/notifications/unread-count",
    "/admin/permissions/menus",
    "/admin/plugins/slots",
    "/admin/preferences/me",
    "/tenant/auth/me",
    "/tenant/auth/refresh",
    "/tenant/notifications/unread-count",
    "/tenant/permissions/menus",
    "/tenant/plugins/slots",
    "/tenant/preferences/me",
)
_LOW_SIGNAL_ACTIVITY_PREFIXES = (
    "/api/public/",
    "/admin/dashboard",
    "/admin/ws/",
    "/tenant/dashboard",
    "/tenant/ws/",
)


def _meaningful_activity_condition():
    exact_path_clauses = [
        OperationLog.path == path for path in _LOW_SIGNAL_ACTIVITY_EXACT_PATHS
    ]
    prefix_clauses = [
        OperationLog.path.like(f"{prefix}%") for prefix in _LOW_SIGNAL_ACTIVITY_PREFIXES
    ]
    return not_(or_(*(exact_path_clauses + prefix_clauses)))


def _normalize_identity_user_type(user_type: str | None) -> str | None:
    normalized = (user_type or "").strip().lower()
    if normalized in {"admin", "platform_admin", "system_admin"}:
        return "admin"
    if normalized in {"tenant_admin", "tenant_user"}:
        return normalized
    return None


def _operation_log_identity_ref(log: OperationLog) -> tuple[str, int] | None:
    normalized_user_type = _normalize_identity_user_type(log.user_type)
    if not normalized_user_type or log.user_id is None:
        return None
    return normalized_user_type, int(log.user_id)


async def _load_operation_log_identity_meta_map(
    db: AsyncSession,
    refs: set[tuple[str, int]],
    *,
    tenant_id: int | None = None,
) -> dict[tuple[str, int], dict[str, Any]]:
    if not refs:
        return {}

    from app.models.auth.admin_role import AdminRole
    from app.models.auth.tenant_admin_role import TenantAdminRole
    from app.models.auth.tenant_user_role import TenantUserRole
    from app.models.org.admin_org_node import AdminOrgNode
    from app.models.org.tenant_org_node import TenantOrgNode
    from app.models.system.admin import Admin
    from app.models.tenant.tenant_admin import TenantAdmin
    from app.models.tenant.tenant_user import TenantUser

    result: dict[tuple[str, int], dict[str, Any]] = {}
    admin_ids = {user_id for user_type, user_id in refs if user_type == "admin"}
    tenant_admin_ids = {
        user_id for user_type, user_id in refs if user_type == "tenant_admin"
    }
    tenant_user_ids = {
        user_id for user_type, user_id in refs if user_type == "tenant_user"
    }

    if admin_ids:
        stmt = (
            select(
                Admin.id,
                Admin.username,
                Admin.nickname,
                Admin.avatar,
                Admin.org_node_id,
                Admin.is_active,
                Admin.is_super,
                AdminRole.name.label("role_name"),
                AdminOrgNode.name.label("org_node_name"),
                AdminOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(Admin)
            .join(AdminRole, AdminRole.id == Admin.role_id, isouter=True)
            .join(
                AdminOrgNode,
                AdminOrgNode.id == Admin.org_node_id,
                isouter=True,
            )
            .where(
                Admin.id.in_(admin_ids),
                Admin.is_deleted.is_(False),
            )
        )
        rows = (await db.execute(stmt)).all()
        for row in rows:
            result[("admin", row.id)] = build_identity_select_extra(
                display_name=resolve_identity_display_name(
                    row.id,
                    row.nickname,
                    row.username,
                ),
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                user_type="admin",
                is_active=row.is_active,
                is_leader=bool(
                    row.org_leader_id is not None and row.org_leader_id == row.id
                ),
                is_owner=bool(row.is_super),
            )

    if tenant_admin_ids:
        stmt = (
            select(
                TenantAdmin.id,
                TenantAdmin.username,
                TenantAdmin.nickname,
                TenantAdmin.avatar,
                TenantAdmin.org_node_id,
                TenantAdmin.is_active,
                TenantAdmin.is_owner,
                TenantAdminRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
                TenantOrgNode.leader_id.label("org_leader_id"),
            )
            .select_from(TenantAdmin)
            .join(
                TenantAdminRole,
                TenantAdminRole.id == TenantAdmin.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantAdmin.org_node_id,
                isouter=True,
            )
            .where(
                TenantAdmin.id.in_(tenant_admin_ids),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(TenantAdmin.tenant_id == tenant_id)
        rows = (await db.execute(stmt)).all()
        for row in rows:
            result[("tenant_admin", row.id)] = build_identity_select_extra(
                display_name=resolve_identity_display_name(
                    row.id,
                    row.nickname,
                    row.username,
                ),
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                user_type="tenant_admin",
                is_active=row.is_active,
                is_leader=bool(
                    row.org_leader_id is not None and row.org_leader_id == row.id
                ),
                is_owner=bool(row.is_owner),
            )

    if tenant_user_ids:
        stmt = (
            select(
                TenantUser.id,
                TenantUser.username,
                TenantUser.nickname,
                TenantUser.avatar,
                TenantUser.org_node_id,
                TenantUser.is_active,
                TenantUserRole.name.label("role_name"),
                TenantOrgNode.name.label("org_node_name"),
            )
            .select_from(TenantUser)
            .join(
                TenantUserRole,
                TenantUserRole.id == TenantUser.role_id,
                isouter=True,
            )
            .join(
                TenantOrgNode,
                TenantOrgNode.id == TenantUser.org_node_id,
                isouter=True,
            )
            .where(
                TenantUser.id.in_(tenant_user_ids),
                TenantUser.is_deleted.is_(False),
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(TenantUser.tenant_id == tenant_id)
        rows = (await db.execute(stmt)).all()
        for row in rows:
            result[("tenant_user", row.id)] = build_identity_select_extra(
                display_name=resolve_identity_display_name(
                    row.id,
                    row.nickname,
                    row.username,
                ),
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                user_type="tenant_user",
                is_active=row.is_active,
                is_leader=False,
                is_owner=False,
            )

    return result


def _serialize_recent_activity(
    log: OperationLog,
    identity_meta: dict[str, Any] | None,
    *,
    format_dt: Callable[[datetime | None], str | None],
) -> dict[str, Any]:
    identity_meta = identity_meta or {}
    username = identity_meta.get("username") or log.username
    nickname = identity_meta.get("nickname") or log.nickname
    display_name = identity_meta.get("display_name")
    if not display_name:
        display_name = resolve_identity_display_name(log.user_id, nickname, username)
    if display_name == "-" and not nickname and not username:
        display_name = None

    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": username,
        "nickname": nickname,
        "display_name": display_name,
        "avatar": identity_meta.get("avatar"),
        "org_node_id": identity_meta.get("org_node_id"),
        "org_node_name": identity_meta.get("org_node_name"),
        "role_name": identity_meta.get("role_name"),
        "display_role_name": identity_meta.get("display_role_name"),
        "user_type": identity_meta.get("user_type") or log.user_type,
        "is_active": identity_meta.get("is_active"),
        "is_owner": identity_meta.get("is_owner"),
        "is_leader": identity_meta.get("is_leader"),
        "action": log.action,
        "module": log.module,
        "resource": log.resource,
        "path": log.path,
        "method": log.method,
        "status_code": log.status_code,
        "ip": log.ip,
        "duration_ms": log.duration_ms,
        "created_at": format_dt(log.created_at),
    }
