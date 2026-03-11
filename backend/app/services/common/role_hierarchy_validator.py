"""
角色层级校验服务 / Role Hierarchy Validator Service

提供基于角色层级的访问控制校验方法
Provides role hierarchy-based access control validation methods.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, TenantAdmin
from app.rbac.services.permission_service import PermissionService


class AdminRoleHierarchyValidator:
    """
    平台管理员角色层级校验器

    提供基于角色层级的访问控制校验：
    - 角色可见性校验
    - 角色管理权限校验
    - 权限分配校验
    """

    def __init__(self, db: AsyncSession, admin: Admin):
        """
        初始化校验器

        Args:
            db: 数据库会话
            admin: 当前平台管理员
        """
        self.db = db
        self.admin = admin
        self._perm_service = PermissionService(db)
        # 缓存
        self._visible_role_ids: set[int] | None = None
        self._manageable_role_ids: set[int] | None = None
        self._effective_permission_ids: set[int] | None = None

    async def get_visible_role_ids(self) -> set[int]:
        """
        获取可见的角色 ID 集合（带缓存）

        Returns:
            可见角色 ID 集合
        """
        if self._visible_role_ids is None:
            self._visible_role_ids = await self._perm_service.get_admin_visible_role_ids(self.admin)
        return self._visible_role_ids

    async def get_manageable_role_ids(self) -> set[int]:
        """
        获取可管理的角色 ID 集合（带缓存）

        Returns:
            可管理角色 ID 集合
        """
        if self._manageable_role_ids is None:
            self._manageable_role_ids = await self._perm_service.get_admin_manageable_role_ids(self.admin)
        return self._manageable_role_ids

    async def get_effective_permission_ids(self) -> set[int]:
        """
        获取有效权限 ID 集合（带缓存）

        Returns:
            有效权限 ID 集合
        """
        if self._effective_permission_ids is None:
            self._effective_permission_ids = await self._perm_service.get_admin_effective_permission_ids(self.admin)
        return self._effective_permission_ids

    async def can_view_role(self, role_id: int) -> bool:
        """
        检查是否可以查看某角色

        Args:
            role_id: 角色 ID

        Returns:
            是否可以查看
        """
        visible_ids = await self.get_visible_role_ids()
        return role_id in visible_ids

    async def can_manage_role(self, role_id: int) -> bool:
        """
        检查是否可以管理某角色（创建/编辑/删除）

        Args:
            role_id: 角色 ID

        Returns:
            是否可以管理
        """
        manageable_ids = await self.get_manageable_role_ids()
        return role_id in manageable_ids

    async def can_create_under_parent(self, parent_id: int | None) -> bool:
        """
        检查是否可以在指定父角色下创建子角色

        - 如果 parent_id 是 None，只有超级管理员可以创建根角色
        - 否则 parent_id 必须是当前管理员的角色或其后代

        Args:
            parent_id: 父角色 ID

        Returns:
            是否可以创建
        """
        # 超级管理员可以在任何位置创建
        if self.admin.is_super:
            return True

        # 无角色的管理员不能创建角色
        if self.admin.role_id is None:
            return False

        # 不能创建根角色（只有超级管理员可以）
        if parent_id is None:
            return False

        # parent_id 必须是自己的角色或后代角色
        visible_ids = await self.get_visible_role_ids()
        return parent_id in visible_ids

    async def can_assign_permission(self, permission_id: int) -> bool:
        """
        检查是否可以分配某权限

        只能分配自己已有的权限

        Args:
            permission_id: 权限 ID

        Returns:
            是否可以分配
        """
        effective_ids = await self.get_effective_permission_ids()
        return permission_id in effective_ids

    async def filter_assignable_permissions(self, permission_ids: list[int]) -> list[int]:
        """
        过滤出可分配的权限 ID

        Args:
            permission_ids: 权限 ID 列表

        Returns:
            可分配的权限 ID 列表
        """
        effective_ids = await self.get_effective_permission_ids()
        return [pid for pid in permission_ids if pid in effective_ids]

    async def get_unassignable_permissions(self, permission_ids: list[int]) -> list[int]:
        """
        获取不可分配的权限 ID

        Args:
            permission_ids: 权限 ID 列表

        Returns:
            不可分配的权限 ID 列表
        """
        effective_ids = await self.get_effective_permission_ids()
        return [pid for pid in permission_ids if pid not in effective_ids]


class TenantAdminRoleHierarchyValidator:
    """
    租户管理员角色层级校验器

    提供基于角色层级的访问控制校验（租户隔离）
    """

    def __init__(self, db: AsyncSession, tenant_admin: TenantAdmin):
        """
        初始化校验器

        Args:
            db: 数据库会话
            tenant_admin: 当前租户管理员
        """
        self.db = db
        self.tenant_admin = tenant_admin
        self._perm_service = PermissionService(db)
        # 缓存
        self._visible_role_ids: set[int] | None = None
        self._manageable_role_ids: set[int] | None = None
        self._effective_permission_ids: set[int] | None = None

    async def get_visible_role_ids(self) -> set[int]:
        """获取可见的角色 ID 集合（带缓存）"""
        if self._visible_role_ids is None:
            self._visible_role_ids = await self._perm_service.get_tenant_admin_visible_role_ids(self.tenant_admin)
        return self._visible_role_ids

    async def get_manageable_role_ids(self) -> set[int]:
        """获取可管理的角色 ID 集合（带缓存）"""
        if self._manageable_role_ids is None:
            self._manageable_role_ids = await self._perm_service.get_tenant_admin_manageable_role_ids(self.tenant_admin)
        return self._manageable_role_ids

    async def get_effective_permission_ids(self) -> set[int]:
        """获取有效权限 ID 集合（带缓存）"""
        if self._effective_permission_ids is None:
            self._effective_permission_ids = await self._perm_service.get_tenant_admin_effective_permission_ids(self.tenant_admin)
        return self._effective_permission_ids

    async def can_view_role(self, role_id: int) -> bool:
        """检查是否可以查看某角色"""
        visible_ids = await self.get_visible_role_ids()
        return role_id in visible_ids

    async def can_manage_role(self, role_id: int) -> bool:
        """检查是否可以管理某角色"""
        manageable_ids = await self.get_manageable_role_ids()
        return role_id in manageable_ids

    async def can_create_under_parent(self, parent_id: int | None) -> bool:
        """检查是否可以在指定父角色下创建子角色"""
        # 租户所有者可以在任何位置创建
        if self.tenant_admin.is_owner:
            return True

        # 无角色的管理员不能创建角色
        if self.tenant_admin.role_id is None:
            return False

        # 不能创建根角色（只有租户所有者可以）
        if parent_id is None:
            return False

        # parent_id 必须是自己的角色或后代角色
        visible_ids = await self.get_visible_role_ids()
        return parent_id in visible_ids

    async def can_assign_permission(self, permission_id: int) -> bool:
        """检查是否可以分配某权限"""
        effective_ids = await self.get_effective_permission_ids()
        return permission_id in effective_ids

    async def filter_assignable_permissions(self, permission_ids: list[int]) -> list[int]:
        """过滤出可分配的权限 ID"""
        effective_ids = await self.get_effective_permission_ids()
        return [pid for pid in permission_ids if pid in effective_ids]

    async def get_unassignable_permissions(self, permission_ids: list[int]) -> list[int]:
        """获取不可分配的权限 ID"""
        effective_ids = await self.get_effective_permission_ids()
        return [pid for pid in permission_ids if pid not in effective_ids]


__all__ = ["AdminRoleHierarchyValidator", "TenantAdminRoleHierarchyValidator"]
