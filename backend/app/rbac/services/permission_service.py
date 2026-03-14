"""
Permission Check Service
权限检查服务

Provides permission retrieval and check functionality.
提供权限获取和检查功能。
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import _
from app.models import Admin, Permission, TenantAdmin, TenantUser
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.repositories.tenant.tenant_role_repository import TenantRoleRepository
from app.schemas.common import MenuResponse, PermissionResponse, PermissionTreeResponse


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

    async def get_admin_permissions(
        self,
        admin: Admin,
    ) -> set[str]:
        """
        Get platform admin's direct permission set (no inheritance).
        获取平台管理员的直接权限集合（不含继承）。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Permission code set / 权限代码集合
        """
        # Super admin has all permissions / 超级管理员拥有所有权限
        if admin.is_super:
            return {"*"}

        # No role means no permissions / 无角色则无权限
        if admin.role_id is None:
            return set()

        # Query role and its permissions / 查询角色及其权限
        result = await self.db.execute(
            select(AdminRole)
            .where(AdminRole.id == admin.role_id)
            .options(selectinload(AdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            p.code for p in role.permissions
            if p.is_enabled and not p.is_deleted
        }

    async def get_admin_effective_permission_ids(self, admin: Admin) -> set[int]:
        """
        Get platform admin's direct permission ID set (no inheritance).
        获取平台管理员的直接权限 ID 集合（不含继承）。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Permission ID set / 权限 ID 集合
        """
        # Super admin has all platform permissions (admin/both scope) / 超级管理员拥有所有平台端权限
        if admin.is_super:
            result = await self.db.execute(
                select(Permission.id).where(
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                    Permission.scope.in_(["admin_only", "admin_and_all"]),
                )
            )
            return set(result.scalars().all())

        # No role means no permissions / 无角色则无权限
        if admin.role_id is None:
            return set()

        permission_ids: set[int] = set()

        # Get current role's permissions / 获取当前角色的权限
        result = await self.db.execute(
            select(AdminRole)
            .where(AdminRole.id == admin.role_id)
            .options(selectinload(AdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role and role.is_active:
            for p in role.permissions:
                if p.is_enabled and not p.is_deleted:
                    permission_ids.add(p.id)

        return permission_ids

    async def get_admin_manageable_role_ids(self, admin: Admin) -> set[int]:
        """
        Get platform admin's manageable role ID set.
        获取平台管理员可管理的角色 ID 集合。

        Manageable roles = all descendant roles (excluding self) + roles where admin is leader.
        可管理的角色 = 自身角色的所有后代角色（不含自身） + 自己作为负责人的角色。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Role ID set / 角色 ID 集合
        """
        # Super admin can manage all roles / 超级管理员可以管理所有角色
        if admin.is_super:
            result = await self.db.execute(
                select(AdminRole.id).where(AdminRole.is_deleted.is_(False))
            )
            return set(result.scalars().all())

        # No role means cannot manage any role / 无角色则无法管理任何角色
        if admin.role_id is None:
            return set()

        manageable_ids = set()

        # Get descendant roles (excluding self) / 获取后代角色（不含自身）
        repo = AdminRoleRepository(self.db)
        descendant_ids = await repo.get_descendant_ids(admin.role_id)
        manageable_ids.update(descendant_ids)

        # Get roles where admin is leader (dept leader can manage their dept) / 获取自己作为负责人的角色
        leader_roles_result = await self.db.execute(
            select(AdminRole.id).where(
                AdminRole.leader_id == admin.id,
                AdminRole.is_deleted.is_(False),
            )
        )
        leader_role_ids = set(leader_roles_result.scalars().all())
        manageable_ids.update(leader_role_ids)

        return manageable_ids

    async def get_admin_visible_role_ids(self, admin: Admin) -> set[int]:
        """
        Get platform admin's visible role ID set.
        获取平台管理员可见的角色 ID 集合。

        Visible roles = own role + all descendant roles.
        可见的角色 = 自身角色 + 所有后代角色。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Role ID set / 角色 ID 集合
        """
        # Super admin can see all roles / 超级管理员可以看到所有角色
        if admin.is_super:
            result = await self.db.execute(
                select(AdminRole.id).where(AdminRole.is_deleted.is_(False))
            )
            return set(result.scalars().all())

        # No role means cannot see any role / 无角色则无法看到任何角色
        if admin.role_id is None:
            return set()

        # Own role + descendant roles / 自身角色 + 后代角色
        visible_ids = {admin.role_id}
        repo = AdminRoleRepository(self.db)
        descendant_ids = await repo.get_descendant_ids(admin.role_id)
        visible_ids.update(descendant_ids)

        return visible_ids

    async def _get_tenant_plan_permissions(
        self,
        tenant_id: int,
    ) -> tuple[set[str], set[int]] | None:
        """
        Get tenant plan's permission set.
        获取企业套餐的权限集合。

        Note: Plans only assign menu-level permissions, but automatically include all child
        operation permissions under those menus, so tenants can assign operation permission granularity.
        注意：套餐只分配菜单级权限，但会自动包含这些菜单下的所有子操作权限。

        Args:
            tenant_id: Tenant ID / 企业 ID

        Returns:
            (permission code set, permission ID set) or None (if tenant has no plan) /
            (权限码集合, 权限ID集合) 或 None（如果企业无套餐）
        """
        # Query tenant and its plan (with plan's permission list loaded) / 查询企业及其套餐
        result = await self.db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_id)
            .options(
                selectinload(Tenant.tenant_plan)
                .selectinload(TenantPlan.permissions)
            )
        )
        tenant = result.scalar_one_or_none()

        if tenant is None or tenant.plan_id is None:
            return None

        plan = tenant.tenant_plan
        if plan is None or not plan.is_active:
            return None

        # Collect plan permissions (only enabled and not deleted) / 收集套餐权限
        plan_codes = set()
        plan_ids = set()
        menu_ids = set()  # Menu permission IDs in plan / 套餐中的菜单权限 ID

        for p in plan.permissions:
            if p.is_enabled and not p.is_deleted:
                plan_codes.add(p.code)
                plan_ids.add(p.id)
                if p.type == "menu":
                    menu_ids.add(p.id)

        # Query all child operation permissions under plan menu permissions / 查询套餐菜单权限下的所有子操作权限
        # So tenants can assign operation permission granularity / 这样企业可以自行分配操作权限粒度
        if menu_ids:
            child_result = await self.db.execute(
                select(Permission)
                .where(
                    Permission.parent_id.in_(menu_ids),
                    Permission.type == "operation",
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                )
            )
            for child in child_result.scalars().all():
                plan_codes.add(child.code)
                plan_ids.add(child.id)

        return plan_codes, plan_ids

    async def get_tenant_admin_permissions(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[str]:
        """
        Get tenant admin's permission set.
        获取企业管理员的权限集合。

        Permission logic (strict mode) / 权限逻辑（严格模式）：
        - No plan: no permissions (returns empty set) / 无套餐：无权限
        - Tenant owner: all plan permissions / 企业所有者：套餐全部权限
        - Regular admin: role permissions ∩ plan permissions / 普通管理员：角色权限 ∩ 套餐权限

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Permission code set / 权限代码集合
        """
        # Get plan permissions (if any) / 获取套餐权限
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)

        # Strict mode: no plan -> no permissions / 严格模式：无套餐 → 无权限
        if plan_perms is None:
            return set()

        # Tenant owner: return all plan permissions / 企业所有者：返回套餐全部权限
        if tenant_admin.is_owner:
            return plan_perms[0]

        # No role means no permissions / 无角色则无权限
        if tenant_admin.role_id is None:
            return set()

        # Query role and its permissions / 查询角色及其权限
        result = await self.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        # Role permissions ∩ plan permissions / 角色权限 ∩ 套餐权限
        role_perms = {
            p.code for p in role.permissions
            if p.is_enabled and not p.is_deleted
        }
        return role_perms & plan_perms[0]

    async def get_tenant_admin_effective_permission_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        """
        Get tenant admin's effective permission ID set.
        获取企业管理员的有效权限 ID 集合。

        Permission logic (strict mode) / 权限逻辑（严格模式）：
        - No plan: no permissions / 无套餐：无权限
        - Tenant owner: all plan permission IDs / 企业所有者：套餐全部权限 ID
        - Regular admin: role permissions ∩ plan permissions / 普通管理员：角色权限 ∩ 套餐权限

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Permission ID set / 权限 ID 集合
        """
        # Get plan permissions (if any) / 获取套餐权限
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)

        # Strict mode: no plan -> no permissions / 严格模式：无套餐 → 无权限
        if plan_perms is None:
            return set()

        # Tenant owner: return all plan permission IDs / 企业所有者：返回套餐全部权限 ID
        if tenant_admin.is_owner:
            return plan_perms[1]

        # No role means no permissions / 无角色则无权限
        if tenant_admin.role_id is None:
            return set()

        permission_ids: set[int] = set()

        # Get current role's permissions / 获取当前角色的权限
        result = await self.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role and role.is_active:
            for p in role.permissions:
                if p.is_enabled and not p.is_deleted:
                    permission_ids.add(p.id)

        # Role permissions ∩ plan permissions / 角色权限 ∩ 套餐权限
        return permission_ids & plan_perms[1]

    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        """
        Get tenant admin's manageable role ID set.
        获取企业管理员可管理的角色 ID 集合。

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Role ID set / 角色 ID 集合
        """
        # Tenant owner can manage all roles / 企业所有者可以管理所有角色
        if tenant_admin.is_owner:
            result = await self.db.execute(
                select(TenantAdminRole.id).where(
                    TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                    TenantAdminRole.is_deleted.is_(False),
                )
            )
            return set(result.scalars().all())

        # No role means cannot manage / 无角色则无法管理
        if tenant_admin.role_id is None:
            return set()

        manageable_ids = set()

        # Get descendant roles / 获取后代角色
        repo = TenantRoleRepository(self.db, tenant_admin.tenant_id)
        descendant_ids = await repo.get_descendant_ids(tenant_admin.role_id)
        manageable_ids.update(descendant_ids)

        # Get roles where admin is leader (dept leader can manage their dept) / 获取自己作为负责人的角色
        leader_roles_result = await self.db.execute(
            select(TenantAdminRole.id).where(
                TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                TenantAdminRole.leader_id == tenant_admin.id,
                TenantAdminRole.is_deleted.is_(False),
            )
        )
        leader_role_ids = set(leader_roles_result.scalars().all())
        manageable_ids.update(leader_role_ids)

        return manageable_ids

    async def get_tenant_admin_visible_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        """
        Get tenant admin's visible role ID set.
        获取企业管理员可见的角色 ID 集合。

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Role ID set / 角色 ID 集合
        """
        # Tenant owner can see all roles / 企业所有者可以看到所有角色
        if tenant_admin.is_owner:
            result = await self.db.execute(
                select(TenantAdminRole.id).where(
                    TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                    TenantAdminRole.is_deleted.is_(False),
                )
            )
            return set(result.scalars().all())

        # No role means cannot see any / 无角色则无法看到
        if tenant_admin.role_id is None:
            return set()

        # Own role + descendant roles / 自身角色 + 后代角色
        visible_ids = {tenant_admin.role_id}
        repo = TenantRoleRepository(self.db, tenant_admin.tenant_id)
        descendant_ids = await repo.get_descendant_ids(tenant_admin.role_id)
        visible_ids.update(descendant_ids)

        return visible_ids

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
        """
        Get all enabled permissions for a given scope.
        获取指定作用域的所有启用权限。

        Args:
            scope: Permission scope / 权限作用域 (admin_only/all_tenants/tenant_user)

        Returns:
            Permission list / 权限列表
        """
        # tenant_user is independent scope, excludes admin_and_all / tenant_user 独立作用域，不含 admin_and_all
        if scope == "tenant_user":
            scopes = [scope]
        else:
            scopes = [scope, "admin_and_all"]

        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
                Permission.scope.in_(scopes),
            )
            .order_by(Permission.sort_order)
        )
        return list(result.scalars().all())

    # ==================== Permission Tree/List Methods / 权限树/列表方法 ====================

    @staticmethod
    def _translate_name(name: str) -> str:
        """
        Translate permission/menu name.
        翻译权限/菜单名称。

        Args:
            name: Permission name (may be i18n key) / 权限名称（可能是 i18n key）

        Returns:
            Translated name / 翻译后的名称
        """
        if name and "." in name:
            translated = _(name)
            if translated == name:
                # Plugin menu key missing from locale file, fallback to runtime title (manifest.title) / 插件菜单 key 缺失于 locale 文件时，回退到 runtime title
                from app.plugins.registry import ExtensionRegistry

                runtime_title = ExtensionRegistry.get_instance().resolve_plugin_menu_title(name)
                if runtime_title:
                    return runtime_title
                return name.split(".")[-1]
            return translated
        return name or ""

    @classmethod
    def _build_permission_tree(
        cls,
        permissions: list[Permission],
        parent_id: int | None = None,
    ) -> list[PermissionTreeResponse]:
        """
        Build permission tree (internal recursive method).
        构建权限树（内部递归方法）。

        Args:
            permissions: Permission list / 权限列表
            parent_id: Parent ID / 父级 ID

        Returns:
            Permission tree / 权限树
        """
        tree = []
        for perm in permissions:
            if perm.parent_id == parent_id:
                children = cls._build_permission_tree(permissions, perm.id)
                tree.append(PermissionTreeResponse(
                    id=perm.id,
                    code=perm.code,
                    name=cls._translate_name(perm.name),
                    description=perm.description,
                    type=perm.type,
                    scope=perm.scope,
                    resource=perm.resource,
                    action=perm.action,
                    parent_id=perm.parent_id,
                    sort_order=perm.sort_order,
                    icon=perm.icon,
                    path=perm.path,
                    component=perm.component,
                    hidden=perm.hidden,
                    children=children,
                ))
        return sorted(tree, key=lambda x: x.sort_order)

    async def get_admin_permission_tree(self, admin: Admin) -> list[PermissionTreeResponse]:
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
            all_permissions = await self.get_enabled_permissions_by_scope("admin_only")
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

    async def get_tenant_permission_tree(self, tenant_admin: TenantAdmin) -> list[PermissionTreeResponse]:
        """
        Get tenant admin's permission tree.
        获取企业管理员的权限树。

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Permission tree list / 权限树列表
        """
        # Get user's effective permission ID set (includes plan filtering) / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_tenant_admin_effective_permission_ids(tenant_admin)

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
                Permission.scope.in_(["admin_only", "admin_and_all"]),
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
        effective_ids = await self.get_tenant_admin_effective_permission_ids(tenant_admin)

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

    async def _fill_parent_permissions(self, permissions: list[Permission]) -> list[Permission]:
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
                select(Permission)
                .where(
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

    # ==================== Menu Building Methods / 菜单构建方法 ====================

    @classmethod
    def _build_menu_tree(
        cls,
        permissions: list[Permission],
        user_permission_codes: set[str] | None = None,
        parent_id: int | None = None,
    ) -> list[MenuResponse]:
        """
        Build menu tree (internal recursive method).
        构建菜单树（内部递归方法）。

        Args:
            permissions: All permission list (including menus and operations) /
                所有权限列表（包含菜单和操作权限）
            user_permission_codes: User's permission code set (for filtering permissions field);
                None means return all operation permissions (super admin/owner scenario) /
                用户拥有的权限码集合（用于过滤）；None 表示返回所有操作权限
            parent_id: Parent ID / 父级 ID

        Returns:
            Menu tree, each node includes user's operation permission codes under that menu /
            菜单树，每个菜单节点包含该菜单下用户拥有的操作权限码
        """
        tree = []
        for perm in permissions:
            if perm.parent_id == parent_id and perm.type == "menu":
                # Recursively build child menus / 递归构建子菜单
                children = cls._build_menu_tree(permissions, user_permission_codes, perm.id)

                # Collect operation permission codes under this menu / 收集该菜单下的操作权限码
                menu_permissions = []
                for p in permissions:
                    if (
                        p.type == "operation"
                        and p.parent_id == perm.id
                        and (user_permission_codes is None or p.code in user_permission_codes)
                    ):
                        # If user permission codes provided, only return user's / 如果提供了用户权限码集合，只返回用户拥有的
                        menu_permissions.append(p.code)

                # Skip empty directory menus: no component (pure directory) + no children + no operation permissions / 跳过空目录菜单
                # Typical scenario: parent directory becomes empty shell after plugin disabled / 典型场景：插件禁用后其父目录变为空壳
                # Exception: plugin menus use dynamic standalone pages, not static view components / 插件菜单使用动态独立页面，不走静态视图组件
                is_plugin_menu = perm.code and ".plugin_" in perm.code
                if not perm.component and not children and not menu_permissions and not is_plugin_menu:
                    continue

                tree.append(MenuResponse(
                    id=perm.id,
                    code=perm.code,
                    name=cls._translate_name(perm.name),
                    icon=perm.icon,
                    path=perm.path,
                    component=perm.component,
                    hidden=perm.hidden,
                    sort_order=perm.sort_order,
                    permissions=sorted(menu_permissions),
                    children=children,
                ))
        return sorted(tree, key=lambda x: x.sort_order)

    async def get_admin_menus(self, admin: Admin) -> list[MenuResponse]:
        """
        Get platform admin's menu tree.
        获取平台管理员的菜单树。

        Args:
            admin: Platform admin / 平台管理员

        Returns:
            Menu tree list, each menu includes user's operation permission codes /
            菜单树列表，每个菜单包含该菜单下用户拥有的操作权限码
        """
        # Get all platform permissions (menu + operation) / 获取所有平台端权限
        all_permissions = await self.get_enabled_permissions_by_scope("admin_only")

        # Super admin gets all menus and all permissions / 超级管理员获取所有菜单和所有权限
        if admin.is_super:
            return self._build_menu_tree(all_permissions, user_permission_codes=None)

        # Get user's effective permission ID set / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_admin_effective_permission_ids(admin)

        if not effective_ids:
            return []

        # Query user's all permissions / 查询用户拥有的所有权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())

        # Collect user's permission code set / 收集用户拥有的权限码集合
        user_permission_codes = {p.code for p in user_permissions}

        # Collect user's menu IDs and operation permission parent_ids / 收集用户拥有的菜单 ID 和操作权限的 parent_id
        menu_ids = set()
        for perm in user_permissions:
            if perm.type == "menu":
                menu_ids.add(perm.id)
            elif perm.type == "operation" and perm.parent_id:
                menu_ids.add(perm.parent_id)

        # Build menu ID to menu mapping / 构建菜单 ID 到菜单的映射
        menu_by_id = {p.id: p for p in all_permissions if p.type == "menu"}

        # Fill all ancestor menus / 补充所有祖先菜单
        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)

        # Build permission list for menu tree / 构建用于菜单树的权限列表
        permissions_for_tree = []
        for p in all_permissions:
            if p.type == "menu" and p.id in menu_ids or p.type == "operation":
                permissions_for_tree.append(p)

        return self._build_menu_tree(permissions_for_tree, user_permission_codes)

    async def get_tenant_admin_menus(self, tenant_admin: TenantAdmin) -> list[MenuResponse]:
        """
        Get tenant admin's menu tree.
        获取企业管理员的菜单树。

        Args:
            tenant_admin: Tenant admin / 企业管理员

        Returns:
            Menu tree list, each menu includes user's operation permission codes /
            菜单树列表，每个菜单包含该菜单下用户拥有的操作权限码
        """
        # Get all tenant permissions (menu + operation) / 获取所有企业端权限
        all_permissions = await self.get_enabled_permissions_by_scope("all_tenants")

        # Get user's effective permission ID set (includes plan filtering) / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_tenant_admin_effective_permission_ids(tenant_admin)

        if not effective_ids:
            return []

        # Query user's all permissions / 查询用户拥有的所有权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())

        # Collect user's permission code set / 收集用户拥有的权限码集合
        user_permission_codes = {p.code for p in user_permissions}

        # Collect user's menu IDs and operation permission parent_ids / 收集用户拥有的菜单 ID 和操作权限的 parent_id
        menu_ids = set()
        for perm in user_permissions:
            if perm.type == "menu":
                menu_ids.add(perm.id)
            elif perm.type == "operation" and perm.parent_id:
                menu_ids.add(perm.parent_id)

        # Build menu ID to menu mapping / 构建菜单 ID 到菜单的映射
        menu_by_id = {p.id: p for p in all_permissions if p.type == "menu"}

        # Fill all ancestor menus / 补充所有祖先菜单
        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)

        # Build permission list for menu tree / 构建用于菜单树的权限列表
        permissions_for_tree = []
        for p in all_permissions:
            if p.type == "menu" and p.id in menu_ids or p.type == "operation":
                permissions_for_tree.append(p)

        return self._build_menu_tree(permissions_for_tree, user_permission_codes)

    # ==================== User Permission Methods / 用户端权限方法 ====================

    async def get_tenant_user_permissions(
        self,
        tenant_user: TenantUser,
    ) -> set[str]:
        """
        Get tenant business user's permission code set.
        获取企业业务用户的权限码集合。

        Args:
            tenant_user: Tenant business user / 企业业务用户

        Returns:
            Permission code set / 权限代码集合
        """
        if tenant_user.role_id is None:
            return set()

        result = await self.db.execute(
            select(TenantUserRole)
            .where(TenantUserRole.id == tenant_user.role_id)
            .options(selectinload(TenantUserRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            p.code for p in role.permissions
            if p.is_enabled and not p.is_deleted
        }

    async def get_tenant_user_effective_permission_ids(
        self,
        tenant_user: TenantUser,
    ) -> set[int]:
        """
        Get tenant business user's effective permission ID set.
        获取企业业务用户的有效权限 ID 集合。

        Args:
            tenant_user: Tenant business user / 企业业务用户

        Returns:
            Permission ID set / 权限 ID 集合
        """
        if tenant_user.role_id is None:
            return set()

        result = await self.db.execute(
            select(TenantUserRole)
            .where(TenantUserRole.id == tenant_user.role_id)
            .options(selectinload(TenantUserRole.permissions))
        )
        role = result.scalar_one_or_none()

        if role is None or not role.is_active:
            return set()

        return {
            p.id for p in role.permissions
            if p.is_enabled and not p.is_deleted
        }

    async def get_tenant_user_menus(self, tenant_user: TenantUser) -> list[MenuResponse]:
        """
        Get tenant business user's menu tree.
        获取企业业务用户的菜单树。

        Args:
            tenant_user: Tenant business user / 企业业务用户

        Returns:
            Menu tree list, each menu includes user's operation permission codes /
            菜单树列表，每个菜单包含该菜单下用户拥有的操作权限码
        """
        # Get all user permissions (menu + operation) / 获取所有用户端权限
        all_permissions = await self.get_enabled_permissions_by_scope("tenant_user")

        # Get user's effective permission ID set / 获取用户的有效权限 ID 集合
        effective_ids = await self.get_tenant_user_effective_permission_ids(tenant_user)

        if not effective_ids:
            return []

        # Query user's all permissions / 查询用户拥有的所有权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())

        # Collect user's permission code set / 收集用户拥有的权限码集合
        user_permission_codes = {p.code for p in user_permissions}

        # Collect user's menu IDs and operation permission parent_ids / 收集用户拥有的菜单 ID 和操作权限的 parent_id
        menu_ids = set()
        for perm in user_permissions:
            if perm.type == "menu":
                menu_ids.add(perm.id)
            elif perm.type == "operation" and perm.parent_id:
                menu_ids.add(perm.parent_id)

        # Build menu ID to menu mapping / 构建菜单 ID 到菜单的映射
        menu_by_id = {p.id: p for p in all_permissions if p.type == "menu"}

        # Fill all ancestor menus / 补充所有祖先菜单
        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)

        # Build permission list for menu tree / 构建用于菜单树的权限列表
        permissions_for_tree = []
        for p in all_permissions:
            if p.type == "menu" and p.id in menu_ids or p.type == "operation":
                permissions_for_tree.append(p)

        return self._build_menu_tree(permissions_for_tree, user_permission_codes)


__all__ = ["PermissionService"]
