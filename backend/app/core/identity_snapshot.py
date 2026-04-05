"""
Identity snapshot helpers for immutable audit and AI log presentation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import (
    resolve_identity_display_name,
    resolve_identity_display_role_name,
)

IDENTITY_SNAPSHOT_VERSION = 1


def normalize_identity_snapshot_user_type(
    user_type: str | None,
) -> str | None:
    if not user_type:
        return None
    normalized = str(user_type).strip().lower()
    if normalized in {"admin", "platform_admin", "system_admin"}:
        return "platform_admin"
    if normalized in {"tenant_admin", "tenant_user"}:
        return normalized
    return normalized or None


def snapshot_has_key(snapshot: dict[str, Any] | None, key: str) -> bool:
    return isinstance(snapshot, dict) and key in snapshot


def snapshot_value(
    snapshot: dict[str, Any] | None,
    key: str,
    fallback: Any = None,
) -> Any:
    if snapshot_has_key(snapshot, key):
        return snapshot.get(key)
    return fallback


def build_identity_snapshot(
    *,
    identity_id: int | None,
    user_type: str | None,
    username: str | None,
    nickname: str | None,
    avatar: str | None,
    org_node_id: int | None = None,
    org_node_name: str | None = None,
    role_name: str | None = None,
    is_active: bool | None = None,
    is_owner: bool | None = None,
    is_leader: bool | None = None,
) -> dict[str, Any]:
    return {
        "v": IDENTITY_SNAPSHOT_VERSION,
        "user_id": identity_id,
        "display_name": resolve_identity_display_name(
            identity_id,
            nickname,
            username,
        ),
        "username": username,
        "nickname": nickname,
        "avatar": avatar,
        "org_node_id": org_node_id,
        "org_node_name": org_node_name,
        "role_name": role_name,
        "display_role_name": resolve_identity_display_role_name(
            role_name,
            org_node_name,
        ),
        "user_type": normalize_identity_snapshot_user_type(user_type),
        "is_active": is_active,
        "is_owner": is_owner,
        "is_leader": is_leader,
    }


async def load_identity_snapshot(
    db: AsyncSession,
    *,
    user_type: str | None,
    user_id: int | None,
    tenant_id: int | None = None,
    fallback_username: str | None = None,
    fallback_nickname: str | None = None,
) -> dict[str, Any] | None:
    normalized_type = normalize_identity_snapshot_user_type(user_type)
    if not normalized_type:
        if fallback_username or fallback_nickname:
            return build_identity_snapshot(
                identity_id=user_id,
                user_type=user_type,
                username=fallback_username,
                nickname=fallback_nickname,
                avatar=None,
            )
        return None

    if not user_id:
        return build_identity_snapshot(
            identity_id=user_id,
            user_type=normalized_type,
            username=fallback_username,
            nickname=fallback_nickname,
            avatar=None,
        )

    if normalized_type == "platform_admin":
        from app.models.auth.admin_role import AdminRole
        from app.models.org.admin_org_node import AdminOrgNode
        from app.models.system.admin import Admin

        row = (
            await db.execute(
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
                .join(AdminOrgNode, AdminOrgNode.id == Admin.org_node_id, isouter=True)
                .where(
                    Admin.id == user_id,
                    Admin.is_deleted.is_(False),
                )
            )
        ).first()
        if row:
            return build_identity_snapshot(
                identity_id=row.id,
                user_type=normalized_type,
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                is_active=row.is_active,
                is_owner=bool(row.is_super),
                is_leader=bool(
                    row.org_leader_id is not None and row.org_leader_id == row.id
                ),
            )

    if normalized_type == "tenant_admin":
        from app.models.auth.tenant_admin_role import TenantAdminRole
        from app.models.org.tenant_org_node import TenantOrgNode
        from app.models.tenant.tenant_admin import TenantAdmin

        filters = [
            TenantAdmin.id == user_id,
            TenantAdmin.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            filters.append(TenantAdmin.tenant_id == tenant_id)

        row = (
            await db.execute(
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
                .where(*filters)
            )
        ).first()
        if row:
            return build_identity_snapshot(
                identity_id=row.id,
                user_type=normalized_type,
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                is_active=row.is_active,
                is_owner=bool(row.is_owner),
                is_leader=bool(
                    row.org_leader_id is not None and row.org_leader_id == row.id
                ),
            )

    if normalized_type == "tenant_user":
        from app.models.auth.tenant_user_role import TenantUserRole
        from app.models.org.tenant_org_node import TenantOrgNode
        from app.models.tenant.tenant_user import TenantUser

        filters = [
            TenantUser.id == user_id,
            TenantUser.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            filters.append(TenantUser.tenant_id == tenant_id)

        row = (
            await db.execute(
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
                .where(*filters)
            )
        ).first()
        if row:
            return build_identity_snapshot(
                identity_id=row.id,
                user_type=normalized_type,
                username=row.username,
                nickname=row.nickname,
                avatar=row.avatar,
                org_node_id=row.org_node_id,
                org_node_name=row.org_node_name,
                role_name=row.role_name,
                is_active=row.is_active,
                is_owner=False,
                is_leader=False,
            )

    return build_identity_snapshot(
        identity_id=user_id,
        user_type=normalized_type,
        username=fallback_username,
        nickname=fallback_nickname,
        avatar=None,
    )


__all__ = [
    "IDENTITY_SNAPSHOT_VERSION",
    "build_identity_snapshot",
    "load_identity_snapshot",
    "normalize_identity_snapshot_user_type",
    "snapshot_has_key",
    "snapshot_value",
]
