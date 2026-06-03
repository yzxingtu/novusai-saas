"""
角色树操作公共 Mixin / Role Tree Mixin

提供角色层级结构的通用操作方法，供平台角色和企业角色服务复用
Provides common role hierarchy operations, shared by platform and tenant role services.
"""

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException, NotFoundException

if TYPE_CHECKING:
    from app.models.auth.admin_role import AdminRole
    from app.models.auth.permission import Permission
    from app.models.auth.tenant_admin_role import TenantAdminRole

# 角色类型变量 / Role type variable
RoleType = TypeVar("RoleType", bound="AdminRole | TenantAdminRole")

# 最大层级深度限制 / Max hierarchy depth
MAX_ROLE_DEPTH = 10


class RoleTreeMixin(Generic[RoleType]):
    """
    角色树操作 Mixin / Role tree mixin.

    提供层级结构的通用方法：
    - 树形结构查询
    - 节点移动（含循环检测）
    - 权限继承计算
    - path 和 level 维护

    使用方式：
        class AdminRoleService(GlobalService, RoleTreeMixin[AdminRole]):
            ...
    """

    # 子类需实现的属性（通过 Service 基类提供）
    repo: Any  # RoleRepository 实例
    db: Any  # AsyncSession 实例

    # ========== 树形结构查询 / Tree queries ==========

    async def get_tree(
        self,
        parent_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取角色树结构 / Get role tree structure.

        Args:
            parent_id: 父角色 ID，None 表示获取整棵树

        Returns:
            树形结构列表，每个节点包含 children 字段
        """
        # 获取所有角色（平铺） / Load flat role list
        if parent_id is None:
            roles = await self.repo.get_tree()
        else:
            roles = await self.repo.get_tree(parent_id=parent_id)

        # 构建树形结构 / Build nested children
        return self._build_tree_structure(roles)

    def _build_tree_structure(
        self,
        roles: list[RoleType],
    ) -> list[dict[str, Any]]:
        """
        将平铺的角色列表构建为树形结构 / Build tree from flat role list.

        Args:
            roles: 角色列表

        Returns:
            树形结构列表
        """
        if not roles:
            return []

        # 建立 id -> role 的映射 / Index by id
        role_map: dict[int, dict[str, Any]] = {}
        for role in roles:
            role_dict = self._role_to_dict(role)
            role_dict["children"] = []
            role_map[role.id] = role_dict

        # 构建父子关系 / Link parent → children
        tree: list[dict[str, Any]] = []
        for role in roles:
            role_dict = role_map[role.id]
            if role.parent_id is None or role.parent_id not in role_map:
                # 顶级节点 / Root node
                tree.append(role_dict)
            else:
                # 子节点 / Child node
                parent_dict = role_map[role.parent_id]
                parent_dict["children"].append(role_dict)

        return tree

    def _role_to_dict(self, role: RoleType) -> dict[str, Any]:
        """
        将角色模型转换为字典 / Convert role model to dict.

        Args:
            role: 角色模型

        Returns:
            角色字典
        """
        return {
            "id": role.id,
            "name": role.name,
            "code": role.code,
            "description": role.description,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "sort_order": role.sort_order,
            "parent_id": role.parent_id,
            "path": role.path,
            "level": role.level,
            "children_count": role.children_count,
            "has_children": role.has_children,
            "has_admins": role.has_admins,
            "created_at": role.created_at,
            "updated_at": role.updated_at,
        }

    async def get_children(self, role_id: int) -> list[RoleType]:
        """
        获取直接子角色列表 / Get direct children.

        Args:
            role_id: 角色 ID

        Returns:
            子角色列表
        """
        return await self.repo.get_children(parent_id=role_id)

    async def get_ancestors(self, role_id: int) -> list[RoleType]:
        """
        获取所有祖先角色 / Get all ancestors.

        Args:
            role_id: 角色 ID

        Returns:
            祖先角色列表（按层级从上到下排序）
        """
        return await self.repo.get_ancestors(role_id)

    async def get_descendants(self, role_id: int) -> list[RoleType]:
        """
        获取所有后代角色 / Get all descendants.

        Args:
            role_id: 角色 ID

        Returns:
            后代角色列表
        """
        return await self.repo.get_descendants(role_id)

    # ========== 节点移动 / Move node ==========

    async def move_node(
        self,
        role_id: int,
        new_parent_id: int | None,
    ) -> RoleType:
        """
        移动角色节点到新的父节点下 / Move role node to new parent.

        Args:
            role_id: 要移动的角色 ID
            new_parent_id: 新父角色 ID，None 表示移动到根级

        Returns:
            移动后的角色

        Raises:
            NotFoundException: 角色不存在
            BusinessException: 循环引用或深度超限
        """
        # 获取要移动的角色 / Load role to move
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        # 不能将自己设为父角色 / Cannot parent self
        if new_parent_id == role_id:
            raise BusinessException(
                message=_("role.cannot_set_self_as_parent"),
                code=ErrorCode.ROLE_CANNOT_SET_SELF_AS_PARENT,
            )

        # 如果新父级与当前父级相同，无需操作 / No-op if parent unchanged
        if role.parent_id == new_parent_id:
            return role

        # 获取新父角色信息 / Resolve new parent
        new_parent = None
        new_parent_path = ""
        new_parent_level = 0

        if new_parent_id is not None:
            new_parent = await self.repo.get_by_id(new_parent_id)
            if not new_parent:
                raise NotFoundException(message=_("role.parent_not_found"))

            new_parent_path = new_parent.path or f"/{new_parent_id}/"
            new_parent_level = new_parent.level or 1

            # 检测循环引用：新父角色不能是当前角色的后代 / Prevent cycle: parent not under self
            descendant_ids = await self.repo.get_descendant_ids(role_id)
            if new_parent_id in descendant_ids:
                raise BusinessException(
                    message=_("role.circular_reference"),
                    code=ErrorCode.ROLE_CIRCULAR_REFERENCE,
                )

        # 计算新的层级深度 / New depth from parent
        new_level = self._calculate_level(new_parent_level)

        # 检查深度限制 / Enforce max depth (include subtree)
        # 需要考虑该角色下的子树深度 / Account for descendants under this role
        max_descendant_depth = await self._get_max_descendant_depth(role_id)
        total_depth = new_level + max_descendant_depth
        if total_depth > MAX_ROLE_DEPTH:
            raise BusinessException(
                message=_("role.max_depth_exceeded"),
                code=ErrorCode.ROLE_MAX_DEPTH_EXCEEDED,
            )

        # 计算新 path / New materialized path
        new_path = self._build_path(new_parent_path if new_parent_id else None, role_id)

        # 更新当前角色 / Persist moved node
        old_path = role.path or f"/{role_id}/"

        await self.repo.update(
            role_id,
            {
                "parent_id": new_parent_id,
                "path": new_path,
                "level": new_level,
            },
        )

        # 更新所有后代的 path 和 level / Fix descendants after move
        await self._update_descendants_path(role_id, old_path, new_path, new_level)

        # 刷新并返回更新后的角色 / Reload role
        return await self.repo.get_by_id(role_id)

    async def _get_max_descendant_depth(self, role_id: int) -> int:
        """
        获取某角色下子树的最大相对深度 / Get max relative depth of subtree under role.

        Args:
            role_id: 角色 ID

        Returns:
            最大相对深度（相对于当前角色）
        """
        descendants = await self.repo.get_descendants(role_id)
        if not descendants:
            return 0

        role = await self.repo.get_by_id(role_id)
        role_level = role.level if role else 1

        max_depth = 0
        for desc in descendants:
            relative_depth = (desc.level or 1) - role_level
            if relative_depth > max_depth:
                max_depth = relative_depth

        return max_depth

    async def _update_descendants_path(
        self,
        role_id: int,
        old_path: str,
        new_path: str,
        new_level: int,
    ) -> None:
        """
        更新所有后代的 path 和 level / Update path and level for all descendants.

        Args:
            role_id: 角色 ID
            old_path: 旧 path
            new_path: 新 path
            new_level: 新 level
        """
        descendants = await self.repo.get_descendants(role_id)

        for desc in descendants:
            # 计算新 path: 替换前缀 / Rewrite path prefix
            desc_new_path = (
                desc.path.replace(old_path, new_path, 1) if desc.path else None
            )

            # 计算新 level: 基于深度差 / Shift level by delta
            level_diff = new_level - (await self.repo.get_by_id(role_id)).level
            desc_new_level = (desc.level or 1) + level_diff

            await self.repo.update(
                desc.id,
                {
                    "path": desc_new_path,
                    "level": desc_new_level,
                },
            )

    # ========== 权限继承 / Permission inheritance ==========

    async def get_effective_permissions(self, role_id: int) -> list["Permission"]:
        """
        获取角色的有效权限（包含继承的权限）/ Get effective permissions for role (including inherited).

        有效权限 = 自身权限 ∪ 所有祖先角色的权限

        Args:
            role_id: 角色 ID

        Returns:
            有效权限列表（去重）
        """
        # 获取当前角色 / Load role
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))

        # 收集所有权限（使用 set 去重）
        permission_ids: set[int] = set()
        permissions_map: dict[int, Permission] = {}

        # 自身权限 / Direct grants
        for perm in role.permissions:
            permission_ids.add(perm.id)
            permissions_map[perm.id] = perm

        # 祖先权限 / Inherited from ancestors
        ancestors = await self.repo.get_ancestors(role_id)
        for ancestor in ancestors:
            for perm in ancestor.permissions:
                if perm.id not in permission_ids:
                    permission_ids.add(perm.id)
                    permissions_map[perm.id] = perm

        return list(permissions_map.values())

    async def get_inherited_permissions(self, role_id: int) -> list["Permission"]:
        """
        获取角色继承的权限（仅祖先角色的权限，不含自身）/ Get inherited permissions (ancestors only).

        Args:
            role_id: 角色 ID

        Returns:
            继承的权限列表（去重）
        """
        permission_ids: set[int] = set()
        permissions_map: dict[int, Permission] = {}

        ancestors = await self.repo.get_ancestors(role_id)
        for ancestor in ancestors:
            for perm in ancestor.permissions:
                if perm.id not in permission_ids:
                    permission_ids.add(perm.id)
                    permissions_map[perm.id] = perm

        return list(permissions_map.values())

    async def has_permission(self, role_id: int, permission_code: str) -> bool:
        """
        检查角色是否拥有指定权限（包含继承）/ Check if role has permission (including inherited).

        Args:
            role_id: 角色 ID
            permission_code: 权限代码

        Returns:
            是否拥有该权限
        """
        effective_permissions = await self.get_effective_permissions(role_id)
        return any(p.code == permission_code for p in effective_permissions)

    # ========== 辅助方法 / Helpers ==========

    def _build_path(self, parent_path: str | None, role_id: int) -> str:
        """
        构建角色的物化路径 / Build materialized path for role.

        Args:
            parent_path: 父角色的 path，None 表示顶级角色
            role_id: 当前角色 ID

        Returns:
            物化路径，如 /1/3/7/
        """
        if parent_path:
            return f"{parent_path.rstrip('/')}/{role_id}/"
        return f"/{role_id}/"

    def _calculate_level(self, parent_level: int | None) -> int:
        """
        计算角色的层级深度 / Calculate role level depth.

        Args:
            parent_level: 父角色的层级，None 表示顶级角色

        Returns:
            层级深度，根节点为 1
        """
        if parent_level is None or parent_level == 0:
            return 1
        return parent_level + 1

    async def validate_parent(
        self, parent_id: int | None, exclude_id: int | None = None
    ) -> tuple[str | None, int]:
        """
        验证父角色并返回其 path 和 level / Validate parent role and return its path and level.

        Args:
            parent_id: 父角色 ID
            exclude_id: 排除的角色 ID（用于更新时排除自身）

        Returns:
            (parent_path, parent_level) 元组

        Raises:
            NotFoundException: 父角色不存在
            BusinessException: 循环引用
        """
        if parent_id is None:
            return None, 0

        # 不能将自己设为父角色 / Cannot parent self (create/update guard)
        if exclude_id and parent_id == exclude_id:
            raise BusinessException(
                message=_("role.cannot_set_self_as_parent"),
                code=ErrorCode.ROLE_CANNOT_SET_SELF_AS_PARENT,
            )

        parent = await self.repo.get_by_id(parent_id)
        if not parent:
            raise NotFoundException(message=_("role.parent_not_found"))

        # 如果是更新操作，检查循环引用 / On update, block cycles via parent
        if exclude_id:
            descendant_ids = await self.repo.get_descendant_ids(exclude_id)
            if parent_id in descendant_ids:
                raise BusinessException(
                    message=_("role.circular_reference"),
                    code=ErrorCode.ROLE_CIRCULAR_REFERENCE,
                )

        return parent.path or f"/{parent_id}/", parent.level or 1


__all__ = ["RoleTreeMixin", "MAX_ROLE_DEPTH"]
