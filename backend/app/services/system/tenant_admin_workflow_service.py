"""
Tenant admin workflow service. / 平台企业管理员管理工作流服务。

将控制器内的租户校验、业务编排与序列化下沉到服务层，保持 API 合约稳定。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.core.i18n import _
from app.core.identity import (
    resolve_identity_display_name,
    resolve_identity_display_role_name,
)
from app.core.response import serialize_datetime_for_api
from app.exceptions import BusinessException, NotFoundException
from app.services.common import AuthService
from app.services.system import TenantService
from app.services.tenant import TenantAdminService


def _serialize_tenant_admin(tenant_admin: Any) -> dict[str, Any]:
    permission_role = getattr(tenant_admin, "role", None)
    org_node = getattr(tenant_admin, "org_node", None)
    is_leader = bool(org_node and org_node.leader_id == tenant_admin.id)
    return {
        "id": tenant_admin.id,
        "tenant_id": tenant_admin.tenant_id,
        "username": tenant_admin.username,
        "email": tenant_admin.email,
        "nickname": tenant_admin.nickname,
        "avatar": tenant_admin.avatar,
        "is_owner": tenant_admin.is_owner,
        "is_leader": is_leader,
        "is_active": tenant_admin.is_active,
        "user_type": "tenant_admin",
        "role_name": permission_role.name if permission_role else None,
        "role_id": tenant_admin.role_id,
        "permission_role_name": permission_role.name if permission_role else None,
        "permission_role_id": tenant_admin.role_id,
        "org_node_name": org_node.name if org_node else None,
        "org_node_id": tenant_admin.org_node_id,
        "last_login_at": serialize_datetime_for_api(tenant_admin.last_login_at),
        "last_login_ip": tenant_admin.last_login_ip,
        "created_at": serialize_datetime_for_api(tenant_admin.created_at),
        "updated_at": serialize_datetime_for_api(tenant_admin.updated_at),
    }


def _serialize_tenant_admin_detail(tenant_admin: Any) -> dict[str, Any]:
    org_node = getattr(tenant_admin, "org_node", None)
    role = getattr(tenant_admin, "role", None)
    is_leader = bool(org_node and getattr(org_node, "leader_id", None) == tenant_admin.id)
    role_id = getattr(role, "id", None)
    role_name = getattr(role, "name", None)
    org_node_id = getattr(org_node, "id", None)
    org_node_name = getattr(org_node, "name", None)
    display_name = resolve_identity_display_name(
        tenant_admin.id,
        tenant_admin.nickname,
        tenant_admin.username,
    )
    return {
        "id": tenant_admin.id,
        "display_name": display_name,
        "username": tenant_admin.username,
        "email": tenant_admin.email,
        "phone": tenant_admin.phone,
        "nickname": tenant_admin.nickname,
        "avatar": tenant_admin.avatar,
        "is_active": tenant_admin.is_active,
        "is_owner": bool(tenant_admin.is_owner),
        "is_leader": is_leader,
        "user_type": "tenant_admin",
        "role_id": role_id,
        "role_name": role_name,
        "display_role_name": resolve_identity_display_role_name(
            role_name,
            org_node_name,
        ),
        "org_node_id": org_node_id,
        "org_node_name": org_node_name,
        "tenant_id": getattr(tenant_admin, "tenant_id", None),
        "created_at": serialize_datetime_for_api(tenant_admin.created_at),
        "updated_at": serialize_datetime_for_api(tenant_admin.updated_at),
        "last_login_at": serialize_datetime_for_api(tenant_admin.last_login_at),
        "last_login_ip": tenant_admin.last_login_ip,
        "permission_role_id": role_id,
        "permission_role_name": role_name,
    }


class TenantAdminWorkflowService:
    """Owns admin-side tenant-admin workflows outside the controller."""

    def __init__(self, db) -> None:
        self._db = db
        self._tenant_service = TenantService(db)
        self._auth_service = AuthService(db)

    def _get_tenant_admin_service(self, tenant_id: int) -> TenantAdminService:
        return TenantAdminService(self._db, tenant_id)

    async def _verify_tenant(self, tenant_id: int) -> None:
        tenant = await self._tenant_service.get_by_id(tenant_id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_("tenant.not_found"),
            )

    @staticmethod
    def _raise_http(exc: Exception) -> None:
        if isinstance(exc, NotFoundException):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc.message),
            )
        if isinstance(exc, BusinessException):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc.message),
            )
        raise exc

    async def list_tenant_admins(self, *, tenant_id: int) -> list[dict[str, Any]]:
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        admins = await service.list_identity_details()
        return [_serialize_tenant_admin(ta) for ta in admins]

    async def select_tenant_admins(
        self,
        *,
        tenant_id: int,
        search: str,
        page: int,
        page_size: int,
    ):
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        return await service.get_identity_select_options(
            search=search,
            page=page,
            page_size=page_size,
        )

    async def get_tenant_admin_detail(
        self,
        *,
        tenant_id: int,
        admin_id: int,
    ):
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        try:
            tenant_admin = await service.get_identity_detail(admin_id)
            return _serialize_tenant_admin_detail(tenant_admin)
        except Exception as exc:
            self._raise_http(exc)

    async def create_tenant_admin(
        self,
        *,
        tenant_id: int,
        data: Any,
    ) -> dict[str, Any]:
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        try:
            new_admin = await service.create_admin(
                username=data.username,
                email=data.email,
                password=data.password,
                nickname=data.nickname,
                is_active=True,
                is_owner=False,
                role_id=data.role_id,
                org_node_id=data.org_node_id,
            )
            await self._db.flush()
            return _serialize_tenant_admin(new_admin)
        except Exception as exc:
            self._raise_http(exc)

    async def update_tenant_admin(
        self,
        *,
        tenant_id: int,
        admin_id: int,
        data: Any,
    ) -> dict[str, Any]:
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        tenant_admin = await service.get_identity_detail(admin_id)

        if (
            data.is_active is not None
            and tenant_admin.is_owner
            and not data.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_("tenant_admin.cannot_disable_owner"),
            )

        update_data = data.model_dump(
            exclude_unset=True,
            exclude={"password"},
        )

        try:
            if data.password is not None:
                await service.reset_password(admin_id, data.password)
            if update_data:
                await service.update_admin(admin_id, update_data)

            updated_admin = await service.get_identity_detail(admin_id)
            await self._db.flush()
            return _serialize_tenant_admin(updated_admin)
        except Exception as exc:
            self._raise_http(exc)

    async def toggle_admin_status(
        self,
        *,
        tenant_id: int,
        admin_id: int,
        is_active: bool,
    ) -> dict[str, Any]:
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        tenant_admin = await service.get_identity_detail(admin_id)

        if tenant_admin.is_owner and not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_("tenant_admin.cannot_disable_owner"),
            )

        tenant_admin = await service.toggle_status(admin_id, is_active)
        await self._db.flush()
        return {
            "id": tenant_admin.id,
            "is_active": tenant_admin.is_active,
        }

    async def force_logout_tenant_admin(
        self,
        *,
        tenant_id: int,
        admin_id: int,
    ) -> str:
        await self._verify_tenant(tenant_id)
        service = self._get_tenant_admin_service(tenant_id)
        tenant_admin = await service.get_identity_detail(admin_id)

        await self._auth_service.token_sessions.force_logout(
            user_type="tenant_admin",
            user_id=admin_id,
            tenant_id=tenant_id,
        )
        return _("auth.force_logout_success", name=tenant_admin.username)


__all__ = ["TenantAdminWorkflowService"]
