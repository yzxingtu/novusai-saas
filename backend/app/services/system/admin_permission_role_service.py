"""
Admin permission role service / 管理后台权限角色服务
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums import ErrorCode, RoleType
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.admin_role import AdminRole
from app.models.auth.permission import Permission
from app.repositories.system.admin_permission_role_repository import (
    AdminPermissionRoleRepository,
)


class AdminPermissionRoleService(GlobalService[AdminRole, AdminPermissionRoleRepository]):
    """Service for admin permission roles / 管理后台权限角色服务"""

    model = AdminRole
    repository_class = AdminPermissionRoleRepository

    def _generate_role_code(self) -> str:
        return f"perm_{uuid.uuid4().hex[:12]}"

    async def get_by_code(self, code: str) -> AdminRole | None:
        return await self.repo.get_by_code(code)

    async def get_permission_roles(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AdminRole], int]:
        return await self.repo.get_page(search=search, page=page, page_size=page_size)

    async def create_permission_role(
        self,
        name: str,
        code: str | None = None,
        description: str | None = None,
        is_system: bool = False,
        is_active: bool = True,
        sort_order: int = 0,
    ) -> AdminRole:
        role_code = code or self._generate_role_code()
        if await self.repo.code_exists(role_code):
            raise BusinessException(
                message=_("role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        data: dict[str, Any] = {
            "name": name,
            "code": role_code,
            "description": description,
            "is_system": is_system,
            "is_active": is_active,
            "sort_order": sort_order,
        }
        if hasattr(self.model, "type"):
            data["type"] = RoleType.ROLE.value
        return await self.repo.create(data)

    async def update_permission_role(self, role_id: int, data: dict[str, Any]) -> AdminRole:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        if (
            "code" in data
            and data["code"]
            and await self.repo.code_exists(data["code"], exclude_id=role_id)
        ):
            raise BusinessException(
                message=_("role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        updated = await self.repo.update(role_id, data)
        if not updated:
            raise NotFoundException(message=_("role.not_found"))
        return updated

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

    async def assign_permissions(self, role_id: int, permission_ids: list[int]) -> AdminRole:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        query = select(Permission).where(
            Permission.id.in_(permission_ids),
            Permission.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        role.permissions = list(result.scalars().all())
        await self.db.flush()
        await self.db.refresh(role)
        return role

    async def get_effective_permissions(self, role_id: int) -> list[Permission]:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        return list(role.permissions)


__all__ = ["AdminPermissionRoleService"]
