"""
平台管理员角色服务

提供平台角色的业务逻辑，支持层级结构和权限继承
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.enums import ErrorCode, RoleType
from app.services.common import MAX_ROLE_DEPTH
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.admin_role import AdminRole
from app.models.auth.permission import Permission
from app.models.system.admin import Admin
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.services.common.role_tree_mixin import RoleTreeMixin


class AdminRoleService(GlobalService[AdminRole, AdminRoleRepository], RoleTreeMixin[AdminRole]):
    """
    平台管理员角色服务
    
    提供角色的 CRUD 操作和层级结构管理
    """
    
    model = AdminRole
    repository_class = AdminRoleRepository
    
    async def get_by_code(self, code: str) -> AdminRole | None:
        """
        根据代码获取角色
        
        Args:
            code: 角色代码
        
        Returns:
            角色实例或 None
        """
        return await self.repo.get_by_code(code)
    
    def _generate_role_code(self) -> str:
        """生成唯一角色代码"""
        return f"role_{uuid.uuid4().hex[:12]}"
    
    async def create_role(
        self,
        name: str,
        description: str | None = None,
        is_system: bool = False,
        is_active: bool = True,
        sort_order: int = 0,
        parent_id: int | None = None,
        type: str = RoleType.ROLE.value,
        allow_members: bool = True,
    ) -> AdminRole:
        """
        创建角色
        
        Args:
            name: 角色名称
            description: 角色描述
            is_system: 是否系统内置
            is_active: 是否启用
            sort_order: 排序
            parent_id: 父角色 ID
        
        Returns:
            创建的角色
        
        Raises:
            BusinessException: 父角色无效或子节点类型不允许
        """
        # 自动生成唯一代码
        code = self._generate_role_code()
        
        # 验证父角色并获取 path 和 level
        parent_path, parent_level = await self.validate_parent(parent_id)
        
        # 验证子节点类型是否允许
        if parent_id:
            parent_role = await self.repo.get_by_id(parent_id)
            if parent_role and not self.validate_child_type(parent_role.type, type):
                raise BusinessException(
                    message=_("role.invalid_child_type"),
                    code=ErrorCode.ROLE_INVALID_CHILD_TYPE,
                )
        
        # 检查深度限制
        new_level = self._calculate_level(parent_level)
        if new_level > MAX_ROLE_DEPTH:
            raise BusinessException(
                message=_("role.max_depth_exceeded"),
                code=ErrorCode.ROLE_MAX_DEPTH_EXCEEDED,
            )
        
        # 创建角色（先不设置 path，需要先获取 ID）
        data = {
            "name": name,
            "code": code,
            "description": description,
            "is_system": is_system,
            "is_active": is_active,
            "sort_order": sort_order,
            "parent_id": parent_id,
            "level": new_level,
            "type": type,
            "allow_members": allow_members,
        }
        
        role = await self.repo.create(data)
        
        # 更新 path（需要角色 ID）
        path = self._build_path(parent_path, role.id)
        await self.repo.update(role.id, {"path": path})
        
        # 刷新角色
        return await self.repo.get_by_id(role.id)
    
    async def update_role(
        self,
        role_id: int,
        data: dict[str, Any],
    ) -> AdminRole:
        """
        更新角色
        
        Args:
            role_id: 角色 ID
            data: 更新数据
        
        Returns:
            更新后的角色
        
        Raises:
            NotFoundException: 角色不存在
            BusinessException: 代码已存在或父角色无效
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        # 系统角色不可修改父级关系
        if role.is_system and "parent_id" in data:
            raise BusinessException(
                message=_("role.system_role_cannot_change_parent"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_CHANGE_PARENT,
            )
        
        # 检查代码是否已被其他角色使用
        if "code" in data and data["code"]:
            if await self.repo.code_exists(data["code"], exclude_id=role_id):
                raise BusinessException(
                    message=_("role.code_exists"),
                    code=ErrorCode.DUPLICATE_ENTRY,
                )
        
        # 如果更新了父角色，需要验证并更新 path/level
        if "parent_id" in data and data["parent_id"] != role.parent_id:
            new_parent_id = data["parent_id"]
            parent_path, parent_level = await self.validate_parent(new_parent_id, exclude_id=role_id)
            
            new_level = self._calculate_level(parent_level)
            
            # 检查深度限制（含子树）
            max_descendant_depth = await self._get_max_descendant_depth(role_id)
            if new_level + max_descendant_depth > MAX_ROLE_DEPTH:
                raise BusinessException(
                    message=_("role.max_depth_exceeded"),
                    code=ErrorCode.ROLE_MAX_DEPTH_EXCEEDED,
                )
            
            # 计算新 path
            new_path = self._build_path(parent_path, role_id)
            old_path = role.path or f"/{role_id}/"
            
            data["path"] = new_path
            data["level"] = new_level
            
            # 更新角色
            result = await self.repo.update(role_id, data)
            
            # 更新所有后代的 path 和 level
            await self._update_descendants_path(role_id, old_path, new_path, new_level)
            
            return await self.repo.get_by_id(role_id)
        
        # 普通更新（不涉及父级变更）
        result = await self.repo.update(role_id, data)
        if not result:
            raise NotFoundException(message=_("role.not_found"))
        
        return result
    
    async def delete_role(self, role_id: int) -> bool:
        """
        删除角色
        
        Args:
            role_id: 角色 ID
        
        Returns:
            是否删除成功
        
        Raises:
            NotFoundException: 角色不存在
            BusinessException: 有子角色或关联用户
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        # 系统角色不可删除
        if role.is_system:
            raise BusinessException(
                message=_("role.system_role_cannot_delete"),
                code=ErrorCode.ROLE_SYSTEM_CANNOT_DELETE,
            )
        
        # 检查是否有子角色（使用 repository 方法避免 lazy-load 问题）
        if await self.repo.has_children(role_id):
            raise BusinessException(
                message=_("role.has_children"),
                code=ErrorCode.ROLE_HAS_CHILDREN,
            )
        
        # 检查是否有关联的管理员（使用 repository 方法避免 lazy-load 问题）
        if await self.repo.has_admins(role_id):
            raise BusinessException(
                message=_("role.has_users"),
                code=ErrorCode.ROLE_HAS_USERS,
            )
        
        return await self.repo.delete(role_id)
    
    async def assign_permissions(
        self,
        role_id: int,
        permission_ids: list[int],
    ) -> AdminRole:
        """
        分配权限给角色
        
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
            raise NotFoundException(message=_("role.not_found"))
        
        # 查询权限
        query = select(Permission).where(
            Permission.id.in_(permission_ids),
            Permission.is_deleted == False,
        )
        result = await self.db.execute(query)
        permissions = list(result.scalars().all())
        
        # 更新角色权限
        role.permissions = permissions
        await self.db.flush()
        await self.db.refresh(role)
        
        return role
    
    async def get_root_roles(self) -> list[AdminRole]:
        """
        获取所有顶级角色
        
        Returns:
            顶级角色列表
        """
        return await self.repo.get_root_roles()
    
    # ========== 组织架构管理方法 ==========
    
    def validate_child_type(self, parent_type: str, child_type: str) -> bool:
        """
        验证子节点类型是否允许
        
        规则:
        - department: 可添加 department, position
        - position: 不可添加子节点
        - role: 可添加 role
        
        Args:
            parent_type: 父节点类型
            child_type: 子节点类型
        
        Returns:
            是否允许
        """
        allowed = {
            RoleType.DEPARTMENT.value: {RoleType.DEPARTMENT.value, RoleType.POSITION.value},
            RoleType.POSITION.value: set(),  # 岗位不可添加子节点
            RoleType.ROLE.value: {RoleType.ROLE.value},
        }
        return child_type in allowed.get(parent_type, set())
    
    async def set_leader(
        self,
        role_id: int,
        leader_id: int | None,
    ) -> AdminRole:
        """
        设置节点负责人
        
        Args:
            role_id: 角色/节点 ID
            leader_id: 负责人 ID，None 表示取消
        
        Returns:
            更新后的角色
        
        Raises:
            NotFoundException: 角色或负责人不存在
            BusinessException: 节点类型不支持设置负责人
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        # 只有部门类型可以设置负责人
        if role.type != RoleType.DEPARTMENT.value:
            raise BusinessException(
                message=_("role.only_department_can_set_leader"),
                code=ErrorCode.ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER,
            )
        
        # 验证负责人是否存在
        if leader_id:
            query = select(Admin).where(
                Admin.id == leader_id,
                Admin.is_deleted == False,
            )
            result = await self.db.execute(query)
            leader = result.scalar_one_or_none()
            if not leader:
                raise NotFoundException(message=_("admin.not_found"))
        
        await self.repo.update(role_id, {"leader_id": leader_id})
        return await self.repo.get_by_id(role_id)
    
    async def get_organization_root_nodes(self) -> list[AdminRole]:
        """
        获取组织架构根节点列表（用于按需加载树）
        
        Returns:
            根节点列表（level=1），每个节点包含 has_children 标记
        """
        return await self.repo.get_organization_root_nodes()
    
    async def get_organization_children(self, parent_id: int) -> list[AdminRole]:
        """
        获取指定节点的直接子节点（用于按需加载）
        
        Args:
            parent_id: 父节点 ID
        
        Returns:
            子节点列表
        """
        return await self.repo.get_children_with_details(parent_id)
    
    async def add_member(
        self,
        role_id: int,
        admin_id: int,
    ) -> AdminRole:
        """
        添加成员到节点
        
        Args:
            role_id: 角色/节点 ID
            admin_id: 管理员 ID
        
        Returns:
            更新后的角色
        
        Raises:
            NotFoundException: 角色或管理员不存在
            BusinessException: 节点不允许添加成员或成员已存在
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        # 检查是否允许添加成员
        if not role.allow_members:
            raise BusinessException(
                message=_("role.cannot_add_member"),
                code=ErrorCode.ROLE_CANNOT_ADD_MEMBER,
            )
        
        # 获取管理员
        query = select(Admin).where(
            Admin.id == admin_id,
            Admin.is_deleted == False,
        )
        result = await self.db.execute(query)
        admin = result.scalar_one_or_none()
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
        
        # 检查是否已是该节点成员
        if admin.role_id == role_id:
            raise BusinessException(
                message=_("role.member_exists"),
                code=ErrorCode.ROLE_MEMBER_EXISTS,
            )
        
        # 更新管理员的角色
        admin.role_id = role_id
        await self.db.flush()
        
        # 重新加载角色信息
        return await self.repo.get_by_id(role_id)
    
    async def remove_member(
        self,
        role_id: int,
        admin_id: int,
    ) -> AdminRole:
        """
        从节点移除成员
        
        Args:
            role_id: 角色/节点 ID
            admin_id: 管理员 ID
        
        Returns:
            更新后的角色
        
        Raises:
            NotFoundException: 角色或管理员不存在
            BusinessException: 管理员不是该节点成员
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        # 获取管理员
        query = select(Admin).where(
            Admin.id == admin_id,
            Admin.is_deleted == False,
        )
        result = await self.db.execute(query)
        admin = result.scalar_one_or_none()
        if not admin:
            raise NotFoundException(message=_("admin.not_found"))
        
        # 检查是否是该节点成员
        if admin.role_id != role_id:
            raise BusinessException(
                message=_("role.member_not_in_node"),
                code=ErrorCode.ROLE_MEMBER_NOT_IN_NODE,
            )
        
        # 如果是负责人，先取消负责人
        if role.leader_id == admin_id:
            await self.repo.update(role_id, {"leader_id": None})
        
        # 移除成员（将 role_id 设为 None）
        admin.role_id = None
        await self.db.flush()
        
        return await self.repo.get_by_id(role_id)
    
    async def get_members(
        self,
        role_id: int,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_descendants: bool = True,
    ) -> tuple[list[Admin], int]:
        """
        获取节点成员列表（分页 + 搜索 + 递归子节点）
        
        Args:
            role_id: 角色/节点 ID
            search: 搜索关键词
            page: 页码
            page_size: 每页数量
            include_descendants: 是否包含子节点成员（默认 True）
        
        Returns:
            (成员列表, 总数)
        
        Raises:
            NotFoundException: 角色不存在
        """
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundException(message=_("role.not_found"))
        
        return await self.repo.get_members(
            role_id,
            search=search,
            page=page,
            page_size=page_size,
            include_descendants=include_descendants,
        )


__all__ = ["AdminRoleService"]
