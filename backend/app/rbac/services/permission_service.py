"""
权限检查服务

提供权限获取和检查功能
"""

from typing import Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import _
from app.models import Admin, TenantAdmin, Permission
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.repositories.tenant.tenant_role_repository import TenantRoleRepository
from app.schemas.common import MenuResponse, PermissionTreeResponse, PermissionResponse


class PermissionService:
    """
    权限检查服务
    
    提供：
    - 获取用户权限列表
    - 检查用户是否拥有指定权限
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_admin_permissions(
        self, 
        admin: Admin,
    ) -> set[str]:
        """
        获取平台管理员的直接权限集合（不含继承）
        
        Args:
            admin: 平台管理员
        
        Returns:
            权限代码集合
        """
        # 超级管理员拥有所有权限
        if admin.is_super:
            return {"*"}
        
        # 无角色则无权限
        if admin.role_id is None:
            return set()
        
        # 查询角色及其权限
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
        获取平台管理员的直接权限 ID 集合（不含继承）
        
        Args:
            admin: 平台管理员
        
        Returns:
            权限 ID 集合
        """
        # 超级管理员拥有所有平台端权限（admin/both 作用域）
        if admin.is_super:
            result = await self.db.execute(
                select(Permission.id).where(
                    Permission.is_enabled.is_(True),
                    Permission.is_deleted.is_(False),
                    Permission.scope.in_(["admin_only", "admin_and_all"]),
                )
            )
            return set(result.scalars().all())
        
        # 无角色则无权限
        if admin.role_id is None:
            return set()
        
        permission_ids: set[int] = set()
        
        # 获取当前角色的权限
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
        获取平台管理员可管理的角色 ID 集合

        可管理的角色 = 自身角色的所有后代角色（不含自身） + 自己作为负责人的角色

        Args:
            admin: 平台管理员

        Returns:
            角色 ID 集合
        """
        # 超级管理员可以管理所有角色
        if admin.is_super:
            result = await self.db.execute(
                select(AdminRole.id).where(AdminRole.is_deleted.is_(False))
            )
            return set(result.scalars().all())

        # 无角色则无法管理任何角色
        if admin.role_id is None:
            return set()

        manageable_ids = set()

        # 获取后代角色（不含自身）
        repo = AdminRoleRepository(self.db)
        descendant_ids = await repo.get_descendant_ids(admin.role_id)
        manageable_ids.update(descendant_ids)

        # 获取自己作为负责人的角色（部门负责人可以管理本部门）
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
        获取平台管理员可见的角色 ID 集合
        
        可见的角色 = 自身角色 + 所有后代角色
        
        Args:
            admin: 平台管理员
        
        Returns:
            角色 ID 集合
        """
        # 超级管理员可以看到所有角色
        if admin.is_super:
            result = await self.db.execute(
                select(AdminRole.id).where(AdminRole.is_deleted.is_(False))
            )
            return set(result.scalars().all())
        
        # 无角色则无法看到任何角色
        if admin.role_id is None:
            return set()
        
        # 自身角色 + 后代角色
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
        获取租户套餐的权限集合
        
        注意：套餐只分配菜单级权限，但会自动包含这些菜单下的所有子操作权限，
        以便租户能够自行分配操作权限粒度。
        
        Args:
            tenant_id: 租户 ID
        
        Returns:
            (权限码集合, 权限ID集合) 或 None（如果租户无套餐）
        """
        # 查询租户及其套餐（并加载套餐的权限列表）
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
        
        # 收集套餐权限（只包含启用且未删除的）
        plan_codes = set()
        plan_ids = set()
        menu_ids = set()  # 套餐中的菜单权限 ID
        
        for p in plan.permissions:
            if p.is_enabled and not p.is_deleted:
                plan_codes.add(p.code)
                plan_ids.add(p.id)
                if p.type == "menu":
                    menu_ids.add(p.id)
        
        # 查询套餐菜单权限下的所有子操作权限
        # 这样租户可以自行分配操作权限粒度
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
        获取租户管理员的权限集合
        
        权限逻辑（严格模式）：
        - 无套餐：无权限（返回空集）
        - 租户所有者：套餐全部权限
        - 普通管理员：角色权限 ∩ 套餐权限
        
        Args:
            tenant_admin: 租户管理员
        
        Returns:
            权限代码集合
        """
        # 获取套餐权限（如果有）
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)
        
        # 严格模式：无套餐 → 无权限
        if plan_perms is None:
            return set()

        # 租户所有者：返回套餐全部权限
        if tenant_admin.is_owner:
            return plan_perms[0]
        
        # 无角色则无权限
        if tenant_admin.role_id is None:
            return set()
        
        # 查询角色及其权限
        result = await self.db.execute(
            select(TenantAdminRole)
            .where(TenantAdminRole.id == tenant_admin.role_id)
            .options(selectinload(TenantAdminRole.permissions))
        )
        role = result.scalar_one_or_none()
        
        if role is None or not role.is_active:
            return set()
        
        # 角色权限 ∩ 套餐权限
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
        获取租户管理员的有效权限 ID 集合
        
        权限逻辑（严格模式）：
        - 无套餐：无权限（返回空集）
        - 租户所有者：套餐全部权限 ID
        - 普通管理员：角色权限 ∩ 套餐权限
        
        Args:
            tenant_admin: 租户管理员
        
        Returns:
            权限 ID 集合
        """
        # 获取套餐权限（如果有）
        plan_perms = await self._get_tenant_plan_permissions(tenant_admin.tenant_id)
        
        # 严格模式：无套餐 → 无权限
        if plan_perms is None:
            return set()

        # 租户所有者：返回套餐全部权限 ID
        if tenant_admin.is_owner:
            return plan_perms[1]
        
        # 无角色则无权限
        if tenant_admin.role_id is None:
            return set()
        
        permission_ids: set[int] = set()
        
        # 获取当前角色的权限
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
        
        # 角色权限 ∩ 套餐权限
        return permission_ids & plan_perms[1]
    
    async def get_tenant_admin_manageable_role_ids(
        self,
        tenant_admin: TenantAdmin,
    ) -> set[int]:
        """
        获取租户管理员可管理的角色 ID 集合

        Args:
            tenant_admin: 租户管理员

        Returns:
            角色 ID 集合
        """
        # 租户所有者可以管理所有角色
        if tenant_admin.is_owner:
            result = await self.db.execute(
                select(TenantAdminRole.id).where(
                    TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                    TenantAdminRole.is_deleted.is_(False),
                )
            )
            return set(result.scalars().all())

        # 无角色则无法管理
        if tenant_admin.role_id is None:
            return set()

        manageable_ids = set()

        # 获取后代角色
        repo = TenantRoleRepository(self.db, tenant_admin.tenant_id)
        descendant_ids = await repo.get_descendant_ids(tenant_admin.role_id)
        manageable_ids.update(descendant_ids)

        # 获取自己作为负责人的角色（部门负责人可以管理本部门）
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
        获取租户管理员可见的角色 ID 集合
        
        Args:
            tenant_admin: 租户管理员
        
        Returns:
            角色 ID 集合
        """
        # 租户所有者可以看到所有角色
        if tenant_admin.is_owner:
            result = await self.db.execute(
                select(TenantAdminRole.id).where(
                    TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                    TenantAdminRole.is_deleted.is_(False),
                )
            )
            return set(result.scalars().all())
        
        # 无角色则无法看到
        if tenant_admin.role_id is None:
            return set()
        
        # 自身角色 + 后代角色
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
        检查用户是否拥有指定权限
        
        支持：
        - 精确匹配: user:create
        - 通配符: * (所有权限)
        - 资源通配符: user:* (某资源的所有操作)
        
        Args:
            user_permissions: 用户权限集合
            required: 需要的权限代码
        
        Returns:
            是否拥有权限
        """
        # 超级权限
        if "*" in user_permissions:
            return True
        
        # 精确匹配
        if required in user_permissions:
            return True
        
        # 资源通配符匹配
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
        检查用户是否拥有任意一个指定权限
        
        Args:
            user_permissions: 用户权限集合
            required_permissions: 需要的权限代码列表
        
        Returns:
            是否拥有任意一个权限
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
        检查用户是否拥有所有指定权限
        
        Args:
            user_permissions: 用户权限集合
            required_permissions: 需要的权限代码列表
        
        Returns:
            是否拥有所有权限
        """
        return all(
            self.check_permission(user_permissions, perm) 
            for perm in required_permissions
        )
    
    async def get_enabled_permissions_by_scope(self, scope: str) -> list[Permission]:
        """
        获取指定作用域的所有启用权限
        
        Args:
            scope: 权限作用域 (admin/tenant/both)
        
        Returns:
            权限列表
        """
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
                Permission.scope.in_([scope, "admin_and_all"]),
            )
            .order_by(Permission.sort_order)
        )
        return list(result.scalars().all())
    
    # ==================== 权限树/列表方法 ====================
    
    @staticmethod
    def _translate_name(name: str) -> str:
        """
        翻译权限/菜单名称
        
        Args:
            name: 权限名称（可能是 i18n key）
        
        Returns:
            翻译后的名称
        """
        if name and "." in name:
            translated = _(name)
            if translated == name:
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
        构建权限树（内部递归方法）
        
        Args:
            permissions: 权限列表
            parent_id: 父级 ID
        
        Returns:
            权限树
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
        获取平台管理员的权限树
        
        Args:
            admin: 平台管理员
        
        Returns:
            权限树列表
        """
        # 超级管理员返回所有权限
        if admin.is_super:
            all_permissions = await self.get_enabled_permissions_by_scope("admin_only")
            return self._build_permission_tree(all_permissions)
        
        # 获取用户的有效权限 ID 集合
        effective_ids = await self.get_admin_effective_permission_ids(admin)
        
        if not effective_ids:
            return []
        
        # 查询用户拥有的权限
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
        
        # 补充父级权限（确保树形结构完整）
        permissions = await self._fill_parent_permissions(permissions)
        
        return self._build_permission_tree(permissions)
    
    async def get_tenant_permission_tree(self, tenant_admin: TenantAdmin) -> list[PermissionTreeResponse]:
        """
        获取租户管理员的权限树
        
        Args:
            tenant_admin: 租户管理员
        
        Returns:
            权限树列表
        """
        # 获取用户的有效权限 ID 集合（已包含套餐过滤逻辑）
        effective_ids = await self.get_tenant_admin_effective_permission_ids(tenant_admin)
        
        if not effective_ids:
            return []
        
        # 查询用户拥有的权限
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
        
        # 补充父级权限
        permissions = await self._fill_parent_permissions(permissions)
        
        return self._build_permission_tree(permissions)
    
    async def get_admin_permission_list(
        self,
        admin: Admin,
        perm_type: str | None = None,
    ) -> list[PermissionResponse]:
        """
        获取平台管理员的权限列表（平铺）
        
        Args:
            admin: 平台管理员
            perm_type: 权限类型过滤 (menu/operation)
        
        Returns:
            权限列表
        """
        # 超级管理员返回所有权限
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
            # 普通管理员只返回自己拥有的权限
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
        获取租户管理员的权限列表（平铺）
        
        Args:
            tenant_admin: 租户管理员
            perm_type: 权限类型过滤 (menu/operation)
        
        Returns:
            权限列表
        """
        # 获取用户有效权限 ID（已包含套餐过滤逻辑）
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
        补充父级权限（确保树形结构完整）
        
        Args:
            permissions: 当前权限列表
        
        Returns:
            补充后的权限列表
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
    
    # ==================== 菜单构建方法 ====================
    
    @classmethod
    def _build_menu_tree(
        cls,
        permissions: list[Permission],
        user_permission_codes: set[str] | None = None,
        parent_id: int | None = None,
    ) -> list[MenuResponse]:
        """
        构建菜单树（内部递归方法）
        
        Args:
            permissions: 所有权限列表（包含菜单和操作权限）
            user_permission_codes: 用户拥有的权限码集合（用于过滤 permissions 字段）
                                   None 表示返回所有操作权限（超管/所有者场景）
            parent_id: 父级 ID
        
        Returns:
            菜单树，每个菜单节点包含该菜单下用户拥有的操作权限码
        """
        tree = []
        for perm in permissions:
            if perm.parent_id == parent_id and perm.type == "menu":
                # 递归构建子菜单
                children = cls._build_menu_tree(permissions, user_permission_codes, perm.id)
                
                # 收集该菜单下的操作权限码
                menu_permissions = []
                for p in permissions:
                    if p.type == "operation" and p.parent_id == perm.id:
                        # 如果提供了用户权限码集合，只返回用户拥有的
                        if user_permission_codes is None or p.code in user_permission_codes:
                            menu_permissions.append(p.code)
                
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
        获取平台管理员的菜单树
        
        Args:
            admin: 平台管理员
        
        Returns:
            菜单树列表，每个菜单包含该菜单下用户拥有的操作权限码
        """
        # 获取所有平台端权限（菜单 + 操作权限）
        all_permissions = await self.get_enabled_permissions_by_scope("admin_only")
        
        # 超级管理员获取所有菜单和所有权限
        if admin.is_super:
            return self._build_menu_tree(all_permissions, user_permission_codes=None)
        
        # 获取用户的有效权限 ID 集合
        effective_ids = await self.get_admin_effective_permission_ids(admin)
        
        if not effective_ids:
            return []
        
        # 查询用户拥有的所有权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())
        
        # 收集用户拥有的权限码集合
        user_permission_codes = {p.code for p in user_permissions}
        
        # 收集用户拥有的菜单 ID 和操作权限的 parent_id
        menu_ids = set()
        for perm in user_permissions:
            if perm.type == "menu":
                menu_ids.add(perm.id)
            elif perm.type == "operation" and perm.parent_id:
                menu_ids.add(perm.parent_id)
        
        # 构建菜单 ID 到菜单的映射
        menu_by_id = {p.id: p for p in all_permissions if p.type == "menu"}
        
        # 补充所有祖先菜单
        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)
        
        # 构建用于菜单树的权限列表
        permissions_for_tree = []
        for p in all_permissions:
            if p.type == "menu" and p.id in menu_ids:
                permissions_for_tree.append(p)
            elif p.type == "operation":
                permissions_for_tree.append(p)
        
        return self._build_menu_tree(permissions_for_tree, user_permission_codes)
    
    async def get_tenant_admin_menus(self, tenant_admin: TenantAdmin) -> list[MenuResponse]:
        """
        获取租户管理员的菜单树
        
        Args:
            tenant_admin: 租户管理员
        
        Returns:
            菜单树列表，每个菜单包含该菜单下用户拥有的操作权限码
        """
        # 获取所有租户端权限（菜单 + 操作权限）
        all_permissions = await self.get_enabled_permissions_by_scope("all_tenants")
        
        # 获取用户的有效权限 ID 集合（已包含套餐过滤逻辑）
        effective_ids = await self.get_tenant_admin_effective_permission_ids(tenant_admin)
        
        if not effective_ids:
            return []
        
        # 查询用户拥有的所有权限
        result = await self.db.execute(
            select(Permission)
            .where(
                Permission.id.in_(effective_ids),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )
        user_permissions = list(result.scalars().all())
        
        # 收集用户拥有的权限码集合
        user_permission_codes = {p.code for p in user_permissions}
        
        # 收集用户拥有的菜单 ID 和操作权限的 parent_id
        menu_ids = set()
        for perm in user_permissions:
            if perm.type == "menu":
                menu_ids.add(perm.id)
            elif perm.type == "operation" and perm.parent_id:
                menu_ids.add(perm.parent_id)
        
        # 构建菜单 ID 到菜单的映射
        menu_by_id = {p.id: p for p in all_permissions if p.type == "menu"}
        
        # 补充所有祖先菜单
        ids_to_process = list(menu_ids)
        while ids_to_process:
            menu_id = ids_to_process.pop()
            menu = menu_by_id.get(menu_id)
            if menu and menu.parent_id and menu.parent_id not in menu_ids:
                menu_ids.add(menu.parent_id)
                ids_to_process.append(menu.parent_id)
        
        # 构建用于菜单树的权限列表
        permissions_for_tree = []
        for p in all_permissions:
            if p.type == "menu" and p.id in menu_ids:
                permissions_for_tree.append(p)
            elif p.type == "operation":
                permissions_for_tree.append(p)
        
        return self._build_menu_tree(permissions_for_tree, user_permission_codes)


__all__ = ["PermissionService"]
