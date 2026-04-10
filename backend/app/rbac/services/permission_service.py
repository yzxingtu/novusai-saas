"""
Permission Check Service. / 权限检查服务。

Provides permission retrieval and check functionality.
提供权限获取和检查功能。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums.rbac import PermissionScope
from app.models import Admin, Permission, TenantAdmin, TenantUser
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.rbac.registry import permission_registry
from app.rbac.services.permission_domains import (
    PermissionAggregationDomain,
    PermissionMenuDomain,
    PermissionPresentationDomain,
)
from app.schemas.common import (
    MenuMetaResponse,
    MenuResponse,
    PermissionResponse,
    PermissionTreeResponse,
)


class _PermissionAggregationFacade:
    """Permission aggregation by identity domain."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_permissions(self, admin: Admin) -> set[str]:
        return await self._service.get_admin_permissions(admin)

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_effective_permission_ids(admin)

    async def get_tenant_admin_permissions(self, tenant_admin: TenantAdmin) -> set[str]:
        return await self._service.get_tenant_admin_permissions(tenant_admin)

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )

    async def get_tenant_user_permissions(self, tenant_user: TenantUser) -> set[str]:
        return await self._service.get_tenant_user_permissions(tenant_user)

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        return await self._service.get_tenant_user_effective_permission_ids(tenant_user)

    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        return await self._service.get_enabled_permissions_by_scope(scope)


class _PermissionTreeFacade:
    """Permission list/tree composition facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_tree(self, admin: Admin) -> list[PermissionTreeResponse]:
        return await self._service.get_admin_permission_tree(admin)

    async def get_tenant_tree(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionTreeResponse]:
        return await self._service.get_tenant_permission_tree(tenant_admin)

    async def get_admin_list(self, admin: Admin) -> list[PermissionResponse]:
        return await self._service.get_admin_permission_list(admin)

    async def get_tenant_list(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[PermissionResponse]:
        return await self._service.get_tenant_permission_list(tenant_admin)

    async def fill_parent_permissions_for_tree(
        self,
        permission_ids: list[int],
    ) -> set[int]:
        return await self._service.fill_parent_permissions_for_tree(permission_ids)


class _MenuFacade:
    """Menu tree facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        return await self._service.get_admin_menus(admin)

    async def get_tenant_admin_menus(
        self,
        tenant_admin: TenantAdmin,
    ) -> list[MenuResponse]:
        return await self._service.get_tenant_admin_menus(tenant_admin)

    async def get_tenant_user_menus(
        self,
        tenant_user: TenantUser,
    ) -> list[MenuResponse]:
        return await self._service.get_tenant_user_menus(tenant_user)


class _OrgAuthorityFacade:
    """Role visibility/manageability facade."""

    def __init__(self, service: "PermissionService") -> None:
        self._service = service

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_manageable_role_ids(admin)

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        return await self._service.get_admin_visible_role_ids(admin)

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_manageable_role_ids(tenant_admin)

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._service.get_tenant_admin_visible_role_ids(tenant_admin)


class PermissionService:
    """
    Permission Check Service.
    权限检查服务。

    Provides / 提供：
    - Get user permission list / 获取用户权限列表
    - Check if user has specified permission / 检查用户是否拥有指定权限
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # Backward-compatible responsibility facades for gradual migration.
        self.permission_aggregation = _PermissionAggregationFacade(self)
        self.permission_tree = _PermissionTreeFacade(self)
        self.menu_tree = _MenuFacade(self)
        self.org_authority = _OrgAuthorityFacade(self)
        self._aggregation_domain = PermissionAggregationDomain(db)
        self._menu_domain = PermissionMenuDomain(self)

    async def _get_admin_org_node(self, admin: Admin):
        return await self._aggregation_domain.get_admin_org_node(admin)

    async def _get_tenant_org_node(self, tenant_admin: TenantAdmin):
        return await self._aggregation_domain.get_tenant_org_node(tenant_admin)

    async def get_admin_permissions(self, admin: Admin) -> set[str]:
        return await self._aggregation_domain.get_admin_permissions(admin)

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_effective_permission_ids(admin)

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_manageable_role_ids(admin)

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        return await self._aggregation_domain.get_admin_visible_role_ids(admin)

    async def _get_tenant_plan_permissions(
        self,
        tenant_id: int,
    ) -> tuple[set[str], set[int]] | None:
        return await self._aggregation_domain.get_tenant_plan_permissions(tenant_id)

    async def get_tenant_admin_permissions(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[str]:
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[0]

        org_node = await self._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            org_node_perms = {
                permission.code
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }
            return org_node_perms & plan_perms[0]

        if tenant_admin.role_id is None:
            return set()

        result = await self.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        role_perms = {
            permission.code
            for permission in role.permissions
            if permission.is_enabled and not permission.is_deleted
        }
        return role_perms & plan_perms[0]

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)
        if plan_perms is None:
            return set()

        if tenant_admin.is_owner:
            return plan_perms[1]

        org_node = await self._get_tenant_org_node(tenant_admin)
        if org_node is not None:
            org_node_permission_ids = {
                permission.id
                for permission in org_node.permissions
                if permission.is_enabled and not permission.is_deleted
            }
            return org_node_permission_ids & plan_perms[1]

        if tenant_admin.role_id is None:
            return set()

        permission_ids: set[int] = set()
        result = await self.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()
        if role and role.is_active:
            for permission in role.permissions:
                if permission.is_enabled and not permission.is_deleted:
                    permission_ids.add(permission.id)

        return permission_ids & plan_perms[1]

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_admin_manageable_role_ids(
            tenant_admin
        )

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_admin_visible_role_ids(
            tenant_admin
        )

    def check_permission(
        self,
        user_permissions: set[str],
        required: str,
    ) -> bool:
        """
        Check if user has specified permission.
        检查用户是否拥有指定权限。

        Supports / 支持：
        - Exact match / 精确匹配: user:create
        - Wildcard / 通配符: * (all permissions / 所有权限)
        - Resource wildcard / 资源通配符: user:* (all ops of a resource / 某资源的所有操作)

        Args:
            user_permissions: User permission set / 用户权限集合
            required: Required permission code / 需要的权限代码

        Returns:
            Whether user has permission / 是否拥有权限
        """
        # Super permission / 超级权限
        if "*" in user_permissions:
            return True

        # Exact match / 精确匹配
        if required in user_permissions:
            return True

        # Resource wildcard match / 资源通配符匹配
        if ":" in required:
            resource = required.split(":")[0]
            if f"{resource}:*" in user_permissions:
                return True

        return False

    def check_any_permission(
        self,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        """
        Check if user has any one of the specified permissions.
        检查用户是否拥有任意一个指定权限。

        Args:
            user_permissions: User permission set / 用户权限集合
            required_permissions: Required permission code list / 需要的权限代码列表

        Returns:
            Whether user has any one permission / 是否拥有任意一个权限
        """
        return any(
            self.check_permission(user_permissions, perm)
            for perm in required_permissions
        )

    def check_all_permissions(
        self,
        user_permissions: set[str],
        required_permissions: list[str],
    ) -> bool:
        """
        Check if user has all specified permissions.
        检查用户是否拥有所有指定权限。

        Args:
            user_permissions: User permission set / 用户权限集合
            required_permissions: Required permission code list / 需要的权限代码列表

        Returns:
            Whether user has all permissions / 是否拥有所有权限
        """
        return all(
            self.check_permission(user_permissions, perm)
            for perm in required_permissions
        )

    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        return await self._aggregation_domain.get_enabled_permissions_by_scope(scope)

    # ==================== Permission Tree/List Methods / 权限树/列表方法 ====================

    @staticmethod
    def _translate_name(name: str) -> str:
        return PermissionPresentationDomain._translate_name(name)

    @classmethod
    def translate_name(cls, name: str) -> str:
        return PermissionPresentationDomain.translate_name(name)

    @staticmethod
    def _resolve_plugin_menu_title(name: str) -> str | None:
        return PermissionPresentationDomain._resolve_plugin_menu_title(name)

    @staticmethod
    def _resolve_plugin_permission_title(name: str) -> str | None:
        return PermissionPresentationDomain._resolve_plugin_permission_title(name)

    @staticmethod
    def _fallback_permission_name(name: str) -> str:
        return PermissionPresentationDomain._fallback_permission_name(name)

    @staticmethod
    def _is_plugin_menu(code: str | None) -> bool:
        return PermissionPresentationDomain._is_plugin_menu(code)

    @classmethod
    def _build_permission_tree(
        cls,
        permissions: list[Permission],
        parent_id: int | None = None,
    ) -> list[PermissionTreeResponse]:
        return PermissionPresentationDomain._build_permission_tree(
            permissions,
            parent_id=parent_id,
        )

    async def get_admin_permission_tree(
        self, admin: Admin
    ) -> list[PermissionTreeResponse]:
        """
        Get platform admin's permission tree.
        获取平台管理员的权限树。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Permission tree list / 权限树列表
        """
        # Super admin returns all permissions / 超级管理员返回所有权限
        if admin.is_super:
            all_permissions = await self.get_enabled_permissions_by_scope(
                PermissionScope.ADMIN.value
            )
            return self._build_permission_tree(all_permissions)

        # Get user's effective permission ID set / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_admin_effective_permission_ids(admin)

        if not effective_ids:
            return []

        # Query user's permissions / 查询用户拥有的权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.sort_order)
        )
        permissions = list(result.scalars().all())

        # Fill parent permissions (ensure tree structure integrity) / 补充父级权限（确保树形结构完整）
        permissions = await self._fill_parent_permissions(permissions)

        return self._build_permission_tree(permissions)

    async def get_tenant_permission_tree(
        self, tenant_admin: TenantAdmin
    ) -> list[PermissionTreeResponse]:
        """
        Get tenant admin's permission tree.
        获取企业管理员的权限树。

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Permission tree list / 权限树列表
        """
        # Get user's effective permission ID set (includes plan filtering) / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )

        if not effective_ids:
            return []

        # Query user's permissions / 查询用户拥有的权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.sort_order)
        )
        permissions = list(result.scalars().all())

        # Fill parent permissions / 补充父级权限
        permissions = await self._fill_parent_permissions(permissions)

        return self._build_permission_tree(permissions)

    async def get_admin_permission_list(
        self,
        admin: Admin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        """
        Get platform admin's permission list (flat).
        获取平台管理员的权限列表（平铺）。

        Args:
            admin: Platform admin / 平台管理员
            perm_type: Permission type filter / 权限类型过滤 (menu/operation)

        Returns:
            Permission list / 权限列表
        """
        # Super admin returns all permissions / 超级管理员返回所有权限
        if admin.is_super:
            query = select(Permission).where(
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
                Permission.scope.in_(
                    [PermissionScope.ADMIN.value, PermissionScope.BOTH.value]
                ),
            )
            if perm_type:
                query = query.where(Permission.type == perm_type)
            query = query.order_by(Permission.sort_order)
            result = await self.db.execute(query)
            permissions = list(result.scalars().all())
        else:
            # Regular admin only returns own permissions / 普通管理员只返回自己拥有的权限
            effective_ids = await self.get_admin_effective_permission_ids(admin)

            if not effective_ids:
                return []

            query = select(Permission).where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
            if perm_type:
                query = query.where(Permission.type == perm_type)
            query = query.order_by(Permission.sort_order)
            result = await self.db.execute(query)
            permissions = list(result.scalars().all())

        return [
            PermissionResponse(
                id=p.id,
                code=p.code,
                name=self._translate_name(p.name),
                description=p.description,
                type=p.type,
                scope=p.scope,
                resource=p.resource,
                action=p.action,
                parent_id=p.parent_id,
                sort_order=p.sort_order,
                icon=p.icon,
                path=p.path,
                component=p.component,
                hidden=p.hidden,
            )
            for p in permissions
        ]

    async def get_tenant_permission_list(
        self,
        tenant_admin: TenantAdmin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        """
        Get tenant admin's permission list (flat).
        获取企业管理员的权限列表（平铺）。

        Args:
            tenant_admin: Tenant admin / 企业管理员
            perm_type: Permission type filter / 权限类型过滤 (menu/operation)

        Returns:
            Permission list / 权限列表
        """
        # Get user's effective permission IDs (includes plan filtering) / 获取用户有效权限 ID
        effective_ids = await self.get_tenant_admin_effective_permission_ids(
            tenant_admin
        )

        if not effective_ids:
            return []

        query = select(Permission).where(
            Permission.id.in_(effective_ids),
            Permission.is_enabled.is_(True),
            Permission.is_deleted.is_(False),
        )
        if perm_type:
            query = query.where(Permission.type == perm_type)
        query = query.order_by(Permission.sort_order)
        result = await self.db.execute(query)
        permissions = list(result.scalars().all())

        return [
            PermissionResponse(
                id=p.id,
                code=p.code,
                name=self._translate_name(p.name),
                description=p.description,
                type=p.type,
                scope=p.scope,
                resource=p.resource,
                action=p.action,
                parent_id=p.parent_id,
                sort_order=p.sort_order,
                icon=p.icon,
                path=p.path,
                component=p.component,
                hidden=p.hidden,
            )
            for p in permissions
        ]

    async def _fill_parent_permissions(
        self, permissions: list[Permission]
    ) -> list[Permission]:
        """
        Fill parent permissions (ensure tree structure integrity).
        补充父级权限（确保树形结构完整）。

        Args:
            permissions: Current permission list / 当前权限列表

        Returns:
            Permission list with parents filled / 补充后的权限列表
        """
        perm_ids = {p.id for p in permissions}
        parent_ids_to_fetch = set()

        for p in permissions:
            if p.parent_id and p.parent_id not in perm_ids:
                parent_ids_to_fetch.add(p.parent_id)

        while parent_ids_to_fetch:
            result = await self.db.execute(
                select(Permission).where(
                    Permission.id.in_(parent_ids_to_fetch),
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                )
            )
            parents = list(result.scalars().all())
            permissions.extend(parents)
            perm_ids.update(p.id for p in parents)

            parent_ids_to_fetch = set()
            for p in parents:
                if p.parent_id and p.parent_id not in perm_ids:
                    parent_ids_to_fetch.add(p.parent_id)

        return permissions

    async def fill_parent_permissions_for_tree(
        self, permissions: list[Permission]
    ) -> list[Permission]:
        """
        Return a copy of permissions with missing ancestors filled in.
        返回补齐缺失祖先节点后的权限列表副本。

        Useful for secondary tree builders (for example plan-available permissions)
        so they stay consistent with the main `/permissions` endpoint.
        供套餐可分配权限树等二次构树场景复用，确保与主 `/permissions` 接口保持一致。
        """
        return await self._fill_parent_permissions(list(permissions))

    # ==================== Menu Building Methods / 菜单构建方法 ====================

    @staticmethod
    def _normalize_menu_ai_strings(values: list[str] | None) -> list[str]:
        return PermissionPresentationDomain._normalize_menu_ai_strings(values)

    @staticmethod
    def _scope_enum_from_value(scope: str | None) -> PermissionScope | None:
        return PermissionPresentationDomain._scope_enum_from_value(scope)

    @classmethod
    def _infer_menu_ai_category(cls, permission: Permission) -> str | None:
        return PermissionPresentationDomain._infer_menu_ai_category(permission)

    @classmethod
    def _build_generic_menu_ai_keywords(
        cls,
        permission: Permission,
        *,
        translated_name: str,
    ) -> list[str]:
        return PermissionPresentationDomain._build_generic_menu_ai_keywords(
            permission,
            translated_name=translated_name,
        )

    @classmethod
    def _build_menu_ai_meta(cls, permission: Permission) -> MenuMetaResponse | None:
        return PermissionPresentationDomain._build_menu_ai_meta(permission)

    @classmethod
    def _build_menu_tree(
        cls,
        permissions: list[Permission],
        user_permission_codes: set[str] | None = None,
        parent_id: int | None = None,
    ) -> list[MenuResponse]:
        return PermissionPresentationDomain._build_menu_tree(
            permissions,
            user_permission_codes=user_permission_codes,
            parent_id=parent_id,
        )

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        return await self._menu_domain.get_admin_menus(admin)

    async def get_tenant_admin_menus(
        self, tenant_admin: TenantAdmin
    ) -> list[MenuResponse]:
        return await self._menu_domain.get_tenant_admin_menus(tenant_admin)

    # ==================== User Permission Methods / 用户端权限方法 ====================

    async def get_tenant_user_permissions(
        self,
        tenant_user: TenantUser,
    ) -> set[str]:
        return await self._aggregation_domain.get_tenant_user_permissions(tenant_user)

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        return await self._aggregation_domain.get_tenant_user_effective_permission_ids(
            tenant_user
        )

    async def get_tenant_user_menus(
        self, tenant_user: TenantUser
    ) -> list[MenuResponse]:
        return await self._menu_domain.get_tenant_user_menus(tenant_user)


__all__ = ["PermissionService", "permission_registry"]
