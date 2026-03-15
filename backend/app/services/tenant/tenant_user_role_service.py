"""
企业用户角色服务 / Tenant User Role Service

提供企业用户角色的业务逻辑（企业隔离），扁平结构无层级
Provides tenant user role business logic (tenant-isolated), flat structure without hierarchy.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.base_service import TenantService
from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.auth.tenant_user_role import TenantUserRole
from app.repositories.tenant.tenant_user_role_repository import TenantUserRoleRepository


class TenantUserRoleService(TenantService[TenantUserRole, TenantUserRoleRepository]):
    """
    企业用户角色服务 / Tenant user role service.

    提供企业用户角色特有的业务方法，自动注入企业隔离
    """

    model = TenantUserRole
    repository_class = TenantUserRoleRepository

    async def get_by_code(self, code: str) -> TenantUserRole | None:
        """
        根据代码获取角色（企业内）/ Get role by code (within tenant).

        Args:
            code: 角色代码

        Returns:
            角色实例或 None
        """
        return await self.repo.get_by_code(code)

    def _generate_role_code(self) -> str:
        """生成唯一角色代码 / Generate unique role code."""
        return f"role_{uuid.uuid4().hex[:12]}"

    async def create_role(
        self,
        name: str,
        code: str | None = None,
        description: str | None = None,
        is_active: bool = True,
        sort_order: int = 0,
        permission_ids: list[int] | None = None,
    ) -> TenantUserRole:
        """
        创建用户角色（企业内）/ Create user role (within tenant).

        Args:
            name: 角色名称
            code: 角色代码
            description: 角色描述
            is_active: 是否启用
            sort_order: 排序
            permission_ids: 权限 ID 列表

        Returns:
            创建的角色

        Raises:
            BusinessException: 名称或代码已存在
        """
        # 自动生成代码（如未提供）
        if not code:
            code = self._generate_role_code()

        # 检查代码是否已存在
        if await self.repo.code_exists(code):
            raise BusinessException(
                message=_("tenant_user_role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        # 检查名称是否已存在
        if await self.repo.name_exists(name):
            raise BusinessException(
                message=_("tenant_user_role.name_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        data = {
            "name": name,
            "code": code,
            "description": description,
            "is_active": is_active,
            "sort_order": sort_order,
        }

        role = await self.repo.create(data)

        # 分配权限
        if permission_ids:
            await self._assign_permissions(role, permission_ids)

        return role

    async def update_role(
        self,
        role_id: int,
        data: dict[str, Any],
    ) -> TenantUserRole:
        """
        更新用户角色（企业内）/ Update user role (within tenant).

        Args:
            role_id: 角色 ID
            data: 更新数据

        Returns:
            更新后的角色

        Raises:
            NotFoundException: 角色不存在
            BusinessException: 系统角色不可修改/代码已存在
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        # 系统角色不可修改
        if role.is_system:
            raise BusinessException(
                message=_("tenant_user_role.system_cannot_modify"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        # 移除不允许直接更新的字段
        data.pop("tenant_id", None)
        permission_ids = data.pop("permission_ids", None)

        # 检查代码唯一性
        if (
            "code" in data
            and data["code"]
            and await self.repo.code_exists(data["code"], exclude_id=role_id)
        ):
            raise BusinessException(
                message=_("tenant_user_role.code_exists"),
                code=ErrorCode.DUPLICATE_ENTRY,
            )

        # 检查名称唯一性
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
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        # 更新权限
        if permission_ids is not None:
            await self._assign_permissions(result, permission_ids)

        return result

    async def delete_role(self, role_id: int) -> bool:
        """
        删除用户角色（企业内） / Delete user role (tenant-scoped)

        通过 BaseService.delete() 统一处理 __delete_deps__ 依赖检查。
        Uses BaseService.delete() for unified __delete_deps__ checking.

        Args:
            role_id: 角色 ID / Role ID

        Returns:
            是否删除成功 / Whether deletion was successful

        Raises:
            NotFoundException: 角色不存在 / Role not found
            BusinessException: 系统角色不可删除 / System role cannot be deleted
            DependencyBlockedException: 有关联用户 / Has associated users
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        if role.is_system:
            raise BusinessException(
                message=_("tenant_user_role.system_cannot_delete"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        return await self.delete(role_id)

    async def assign_permissions(
        self,
        role_id: int,
        permission_ids: list[int],
    ) -> TenantUserRole:
        """
        分配权限给角色（企业内）/ Assign permissions to role (within tenant).

        Args:
            role_id: 角色 ID
            permission_ids: 权限 ID 列表

        Returns:
            更新后的角色

        Raises:
            NotFoundException: 角色不存在
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        await self._assign_permissions(role, permission_ids)
        return role

    async def toggle_status(
        self,
        role_id: int,
        is_active: bool,
    ) -> TenantUserRole:
        """
        切换角色状态 / Toggle role active status.

        Args:
            role_id: 角色 ID
            is_active: 是否启用

        Returns:
            更新后的角色

        Raises:
            NotFoundException: 角色不存在
            BusinessException: 系统角色不可修改
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        if role.is_system:
            raise BusinessException(
                message=_("tenant_user_role.system_cannot_modify"),
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = await self.repo.update(role_id, {"is_active": is_active})
        if not result:
            raise NotFoundException(message=_("tenant_user_role.not_found"))

        return result

    async def _assign_permissions(
        self,
        role: TenantUserRole,
        permission_ids: list[int],
    ) -> None:
        """
        内部方法：分配权限给角色 / Internal: assign permissions to role.

        Args:
            role: 角色实例
            permission_ids: 权限 ID 列表
        """
        if not permission_ids:
            role.permissions = []
            await self.db.flush()
            await self.db.refresh(role)
            return

        query = select(Permission).where(
            Permission.id.in_(permission_ids),
            Permission.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        permissions = list(result.scalars().all())

        role.permissions = permissions
        await self.db.flush()
        await self.db.refresh(role)


__all__ = ["TenantUserRoleService"]
