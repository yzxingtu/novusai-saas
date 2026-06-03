"""
Tenant admin permission role service / 企业管理员权限角色服务
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.base_service import TenantService
from app.core.i18n import _
from app.enums import ErrorCode
from app.enums.role import DataScope, RoleType
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.repositories.tenant.tenant_permission_role_repository import (
    TenantPermissionRoleRepository,
)
from app.services.tenant.plan_permission_guard import (
    normalize_tenant_plan_permission_ids,
)


class TenantPermissionRoleService(
    TenantService[TenantAdminRole, TenantPermissionRoleRepository]
):
    """Tenant admin permission role service / 企业管理员权限角色服务"""

    model = TenantAdminRole
    repository_class = TenantPermissionRoleRepository

    async def get_by_code(self, code: str) -> TenantAdminRole | None:
        return await self.repo.get_by_code(code)

    def _generate_role_code(self) -> str:
        return f"perm_{uuid.uuid4().hex[:12]}"

    async def get_permission_roles(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TenantAdminRole], int]:
        return await self.repo.get_page(search=search, page=page, page_size=page_size)

    async def create_permission_role(
        self,
        name: str,
        code: str | None = None,
        description: str | None = None,
        is_active: bool = True,
        sort_order: int = 0,
        permission_ids: list[int] | None = None,
    ) -> TenantAdminRole:
        role_code = code or self._generate_role_code()
        if await self.repo.code_exists(role_code):
            raise BusinessException(
                message=_("tenant_user_role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )
        if await self.repo.name_exists(name):
            raise BusinessException(
                message=_("tenant_user_role.name_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        data: dict[str, Any] = {
            "name": name,
            "code": role_code,
            "description": description,
            "is_active": is_active,
            "is_system": False,
            "sort_order": sort_order,
            "type": RoleType.ROLE.value,
            "parent_id": None,
            "path": None,
            "level": 1,
            "allow_members": True,
            "leader_id": None,
            "data_scope": DataScope.SELF_ONLY.value,
            "custom_dept_ids": None,
        }

        role = await self.repo.create(data)
        if permission_ids is not None:
            await self._assign_permissions(role, permission_ids)
        return role

    async def update_permission_role(
        self,
        role_id: int,
        data: dict[str, Any],
    ) -> TenantAdminRole:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        if role.is_system:
            raise BusinessException(
                message=_("tenant_user_role.system_cannot_modify"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        permission_ids = data.pop("permission_ids", None)
        for field in (
            "tenant_id",
            "type",
            "parent_id",
            "path",
            "level",
            "allow_members",
            "leader_id",
            "data_scope",
            "custom_dept_ids",
        ):
            data.pop(field, None)

        if (
            "code" in data
            and data["code"]
            and await self.repo.code_exists(data["code"], exclude_id=role_id)
        ):
            raise BusinessException(
                message=_("tenant_user_role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )
        if (
            "name" in data
            and data["name"]
            and await self.repo.name_exists(data["name"], exclude_id=role_id)
        ):
            raise BusinessException(
                message=_("tenant_user_role.name_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        result = await self.repo.update(role_id, data)
        if not result:
            raise NotFoundException(message=_("role.not_found"))

        if permission_ids is not None:
            await self._assign_permissions(result, permission_ids)

        return result

    async def delete_permission_role(self, role_id: int) -> bool:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        if role.is_system:
            raise BusinessException(
                message=_("role.system_role_cannot_delete"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_DELETE,
            )

        return await self.delete(role_id)

    async def assign_permissions(
        self,
        role_id: int,
        permission_ids: list[int],
    ) -> TenantAdminRole:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        await self._assign_permissions(role, permission_ids)
        return role

    async def _assign_permissions(
        self,
        role: TenantAdminRole,
        permission_ids: list[int],
    ) -> None:
        if not permission_ids:
            role.permissions = []
            await self.db.flush()
            await self.db.refresh(role)
            return

        normalized_permission_ids = await normalize_tenant_plan_permission_ids(
            self.db,
            tenant_id=self.tenant_id,
            permission_ids=permission_ids,
        )
        query = select(Permission).where(
            Permission.id.in_(normalized_permission_ids),
            Permission.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        permissions = list(result.scalars().all())
        permission_map = {permission.id: permission for permission in permissions}
        role.permissions = [
            permission_map[permission_id]
            for permission_id in normalized_permission_ids
            if permission_id in permission_map
        ]
        await self.db.flush()
        await self.db.refresh(role)


__all__ = ["TenantPermissionRoleService"]
