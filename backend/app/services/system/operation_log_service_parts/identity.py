"""Identity enrichment helpers for operation logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import build_identity_select_extra


class _OperationLogIdentityFacade:
    """Identity enrichment and serialization helpers for operation logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def identity_ref(
        user_type: str | None,
        user_id: int | None,
    ) -> tuple[str, int] | None:
        if not user_type or not user_id:
            return None
        return str(user_type), int(user_id)

    @staticmethod
    def build_identity_meta(
        *,
        identity_id: int | None,
        user_type: str,
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
        return build_identity_select_extra(
            display_name=nickname
            or username
            or (f"#{identity_id}" if identity_id else "-"),
            username=username,
            nickname=nickname,
            avatar=avatar,
            org_node_id=org_node_id,
            org_node_name=org_node_name,
            role_name=role_name,
            user_type=user_type,
            is_active=is_active,
            is_leader=bool(is_leader),
            is_owner=bool(is_owner),
        )

    async def load_identity_meta_map(
        self,
        refs: set[tuple[str, int]],
    ) -> dict[tuple[str, int], dict[str, Any]]:
        if not refs:
            return {}

        from app.models.auth.admin_role import AdminRole
        from app.models.auth.tenant_admin_role import TenantAdminRole
        from app.models.auth.tenant_user_role import TenantUserRole
        from app.models.org.admin_org_node import AdminOrgNode
        from app.models.org.tenant_org_node import TenantOrgNode
        from app.models.system.admin import Admin as AdminModel
        from app.models.tenant.tenant_admin import TenantAdmin as TenantAdminModel
        from app.models.tenant.tenant_user import TenantUser as TenantUserModel

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
                    AdminModel.id,
                    AdminModel.username,
                    AdminModel.nickname,
                    AdminModel.avatar,
                    AdminModel.org_node_id,
                    AdminModel.is_active,
                    AdminModel.is_super,
                    AdminRole.name.label("role_name"),
                    AdminOrgNode.name.label("org_node_name"),
                    AdminOrgNode.leader_id.label("org_leader_id"),
                )
                .select_from(AdminModel)
                .join(AdminRole, AdminRole.id == AdminModel.role_id, isouter=True)
                .join(
                    AdminOrgNode,
                    AdminOrgNode.id == AdminModel.org_node_id,
                    isouter=True,
                )
                .where(
                    AdminModel.id.in_(admin_ids),
                    AdminModel.is_deleted.is_(False),
                )
            )
            rows = (await self.db.execute(stmt)).all()
            for row in rows:
                result[("admin", row.id)] = self.build_identity_meta(
                    identity_id=row.id,
                    user_type="admin",
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

        if tenant_admin_ids:
            stmt = (
                select(
                    TenantAdminModel.id,
                    TenantAdminModel.username,
                    TenantAdminModel.nickname,
                    TenantAdminModel.avatar,
                    TenantAdminModel.org_node_id,
                    TenantAdminModel.is_active,
                    TenantAdminModel.is_owner,
                    TenantAdminRole.name.label("role_name"),
                    TenantOrgNode.name.label("org_node_name"),
                    TenantOrgNode.leader_id.label("org_leader_id"),
                )
                .select_from(TenantAdminModel)
                .join(
                    TenantAdminRole,
                    TenantAdminRole.id == TenantAdminModel.role_id,
                    isouter=True,
                )
                .join(
                    TenantOrgNode,
                    TenantOrgNode.id == TenantAdminModel.org_node_id,
                    isouter=True,
                )
                .where(
                    TenantAdminModel.id.in_(tenant_admin_ids),
                    TenantAdminModel.is_deleted.is_(False),
                )
            )
            rows = (await self.db.execute(stmt)).all()
            for row in rows:
                result[("tenant_admin", row.id)] = self.build_identity_meta(
                    identity_id=row.id,
                    user_type="tenant_admin",
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

        if tenant_user_ids:
            stmt = (
                select(
                    TenantUserModel.id,
                    TenantUserModel.username,
                    TenantUserModel.nickname,
                    TenantUserModel.avatar,
                    TenantUserModel.org_node_id,
                    TenantUserModel.is_active,
                    TenantUserRole.name.label("role_name"),
                    TenantOrgNode.name.label("org_node_name"),
                )
                .select_from(TenantUserModel)
                .join(
                    TenantUserRole,
                    TenantUserRole.id == TenantUserModel.role_id,
                    isouter=True,
                )
                .join(
                    TenantOrgNode,
                    TenantOrgNode.id == TenantUserModel.org_node_id,
                    isouter=True,
                )
                .where(
                    TenantUserModel.id.in_(tenant_user_ids),
                    TenantUserModel.is_deleted.is_(False),
                )
            )
            rows = (await self.db.execute(stmt)).all()
            for row in rows:
                result[("tenant_user", row.id)] = self.build_identity_meta(
                    identity_id=row.id,
                    user_type="tenant_user",
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

        return result

    @staticmethod
    def serialize_operator_row(
        row: Any,
        identity_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        identity_meta = identity_meta or {}
        username = row.username or identity_meta.get("username") or ""
        nickname = row.nickname or identity_meta.get("nickname")
        display_name = identity_meta.get("display_name") or nickname or username or None
        return {
            "user_id": row.user_id,
            "user_type": row.user_type,
            "display_name": display_name,
            "username": username,
            "nickname": nickname,
            "avatar": identity_meta.get("avatar"),
            "org_node_id": identity_meta.get("org_node_id"),
            "org_node_name": identity_meta.get("org_node_name"),
            "role_name": identity_meta.get("role_name"),
            "is_active": identity_meta.get("is_active"),
            "is_owner": identity_meta.get("is_owner"),
            "is_leader": identity_meta.get("is_leader"),
        }


__all__ = ["_OperationLogIdentityFacade"]
