"""
平台管理员角色仓储

提供平台角色的数据访问操作，支持层级查询
"""

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.models.auth.admin_role import AdminRole


class AdminRoleRepository(BaseRepository[AdminRole]):
    """
    平台管理员角色仓储
    
    提供平台角色特有的数据访问方法，包含层级结构查询
    """
    
    model = AdminRole
    
    # 按 scope 限制可过滤字段
    _scope_fields = {
        "admin": {
            "id", "name", "code", "is_system", "is_active",
            "parent_id", "level", "type", "leader_id",
            "created_at", "updated_at",
        },
    }
    
    async def get_by_code(self, code: str) -> AdminRole | None:
        """
        根据代码获取角色
        
        Args:
            code: 角色代码
        
        Returns:
            角色实例或 None
        """
        return await self.get_one_by(code=code)
    
    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查角色代码是否已存在
        
        Args:
            code: 角色代码
            exclude_id: 排除的 ID（用于更新时排除自身）
        
        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.code == code,
            self.model.is_deleted == False,
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    # ========== 层级查询方法 ==========
    
    async def get_children(
        self,
        parent_id: int | None,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取直接子角色列表
        
        Args:
            parent_id: 父角色 ID，None 表示获取顶级角色
            include_deleted: 是否包含已删除记录
        
        Returns:
            子角色列表
        """
        query = select(self.model).where(
            self.model.parent_id == parent_id if parent_id else self.model.parent_id.is_(None)
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_ancestors(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取所有祖先角色（从根到父，不含自身）
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            祖先角色列表（按层级从上到下排序）
        """
        # 先获取当前角色的 path
        role = await self.get_by_id(role_id, include_deleted=include_deleted)
        if not role or not role.path:
            return []
        
        # 解析 path 获取祖先 ID 列表
        ancestor_ids = role.get_ancestor_ids()
        if not ancestor_ids:
            return []
        
        # 查询祖先角色
        query = select(self.model).where(
            self.model.id.in_(ancestor_ids)
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        query = query.order_by(self.model.level.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_descendants(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取所有后代角色（不含自身）
        
        使用 path 字段的 LIKE 查询实现
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            后代角色列表（按层级从上到下排序）
        """
        # 先获取当前角色
        role = await self.get_by_id(role_id, include_deleted=include_deleted)
        if not role:
            return []
        
        # 构建 path 前缀模式，如 /1/3/% 匹配所有以 /1/3/ 开头的角色
        # 当前角色的 path 已经包含自身，如 /1/3/，所以后代的 path 会是 /1/3/7/、/1/3/7/9/ 等
        path_prefix = role.path or f"/{role_id}/"
        
        query = select(self.model).where(
            self.model.path.like(f"{path_prefix}%"),
            self.model.id != role_id,  # 排除自身
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        query = query.order_by(self.model.level.asc(), self.model.sort_order.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_descendant_ids(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> list[int]:
        """
        获取所有后代角色 ID（不含自身）
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            后代角色 ID 列表
        """
        descendants = await self.get_descendants(role_id, include_deleted)
        return [d.id for d in descendants]
    
    async def get_tree(
        self,
        parent_id: int | None = None,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取角色树（指定节点下的所有角色）
        
        Args:
            parent_id: 父角色 ID，None 表示从根节点开始
            include_deleted: 是否包含已删除记录
        
        Returns:
            角色列表（平铺，按层级和排序字段排序）
        """
        if parent_id is None:
            # 获取所有角色
            query = select(self.model)
        else:
            # 获取指定节点及其后代
            role = await self.get_by_id(parent_id, include_deleted=include_deleted)
            if not role:
                return []
            
            path_prefix = role.path or f"/{parent_id}/"
            query = select(self.model).where(
                self.model.path.like(f"{path_prefix}%")
            )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 加载子角色和管理员关联，支持 children_count/has_children/has_admins 属性
        query = query.options(
            selectinload(self.model.children),
            selectinload(self.model.admins),
        )
        query = query.order_by(self.model.level.asc(), self.model.sort_order.asc(), self.model.id.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def has_children(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> bool:
        """
        检查角色是否有子角色
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            是否有子角色
        """
        query = select(func.count(self.model.id)).where(
            self.model.parent_id == role_id
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0
    
    async def count_children(
        self,
        parent_id: int | None,
        include_deleted: bool = False,
    ) -> int:
        """
        统计直接子角色数量
        
        Args:
            parent_id: 父角色 ID，None 表示统计顶级角色
            include_deleted: 是否包含已删除记录
        
        Returns:
            子角色数量
        """
        query = select(func.count(self.model.id)).where(
            self.model.parent_id == parent_id if parent_id else self.model.parent_id.is_(None)
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def get_root_roles(
        self,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取所有顶级角色（无父角色）
        
        Args:
            include_deleted: 是否包含已删除记录
        
        Returns:
            顶级角色列表
        """
        return await self.get_children(parent_id=None, include_deleted=include_deleted)
    
    async def has_admins(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> bool:
        """
        检查角色是否有关联的管理员
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            是否有关联管理员
        """
        from app.models.system.admin import Admin
        
        query = select(func.count(Admin.id)).where(
            Admin.role_id == role_id
        )
        
        if not include_deleted:
            query = query.where(Admin.is_deleted == False)
        
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0
    
    # ========== 组织架构查询方法 ==========
    
    async def get_by_type(
        self,
        role_type: str,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        根据节点类型获取角色列表
        
        Args:
            role_type: 节点类型 (department/position/role)
            include_deleted: 是否包含已删除记录
        
        Returns:
            角色列表
        """
        query = select(self.model).where(
            self.model.type == role_type
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        query = query.order_by(self.model.sort_order.asc(), self.model.id.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_departments(
        self,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取所有部门节点
        
        Args:
            include_deleted: 是否包含已删除记录
        
        Returns:
            部门列表
        """
        return await self.get_by_type("department", include_deleted)
    
    async def get_members(
        self,
        role_id: int,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        include_descendants: bool = True,
        include_deleted: bool = False,
    ) -> tuple[list, int]:
        """
        获取节点成员列表（分页 + 搜索 + 递归子节点）
        
        Args:
            role_id: 角色/节点 ID
            search: 搜索关键词（匹配用户名/昵称/邮箱）
            page: 页码
            page_size: 每页数量
            include_descendants: 是否包含子节点成员（默认 True）
            include_deleted: 是否包含已删除记录
        
        Returns:
            (成员列表, 总数)
        """
        from app.models.system.admin import Admin
        from sqlalchemy import or_
        from sqlalchemy.orm import selectinload
        
        # 确定查询的角色 ID 范围
        if include_descendants:
            # 获取当前节点的 path
            role = await self.get_by_id(role_id, include_deleted=include_deleted)
            if not role:
                return [], 0
            
            # 查询所有子节点 ID（包含自身）
            # 子节点的 path 以当前节点的 path 为前缀，如当前节点 path=/155/，子节点 path=/155/xxx/
            path_prefix = role.path or f"/{role_id}/"
            role_ids_query = select(self.model.id).where(
                or_(
                    self.model.id == role_id,  # 包含当前节点自身
                    self.model.path.like(f"{path_prefix}%"),  # 所有以当前 path 为前缀的子节点
                )
            )
            if not include_deleted:
                role_ids_query = role_ids_query.where(self.model.is_deleted == False)
            
            role_ids_result = await self.db.execute(role_ids_query)
            role_ids = [r for r in role_ids_result.scalars().all()]
            
            if not role_ids:
                return [], 0
            
            # 基础查询条件：所有子节点的成员
            base_conditions = [Admin.role_id.in_(role_ids)]
        else:
            # 仅查询当前节点的成员
            base_conditions = [Admin.role_id == role_id]
        
        if not include_deleted:
            base_conditions.append(Admin.is_deleted == False)
        
        # 搜索条件
        if search:
            search_pattern = f"%{search}%"
            base_conditions.append(
                or_(
                    Admin.username.ilike(search_pattern),
                    Admin.nickname.ilike(search_pattern),
                    Admin.email.ilike(search_pattern),
                )
            )
        
        # 统计总数
        count_query = select(func.count(Admin.id)).where(*base_conditions)
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # 分页查询，并加载角色关联
        offset = (page - 1) * page_size
        query = select(Admin).where(*base_conditions)
        query = query.options(selectinload(Admin.role))  # 加载角色关联
        query = query.order_by(Admin.id.asc())
        query = query.offset(offset).limit(page_size)
        
        result = await self.db.execute(query)
        members = list(result.scalars().all())
        
        return members, total
    
    async def count_members(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> int:
        """
        统计节点成员数量
        
        Args:
            role_id: 角色/节点 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            成员数量
        """
        from app.models.system.admin import Admin
        
        query = select(func.count(Admin.id)).where(
            Admin.role_id == role_id
        )
        
        if not include_deleted:
            query = query.where(Admin.is_deleted == False)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def get_with_members(
        self,
        role_id: int,
        include_deleted: bool = False,
    ) -> AdminRole | None:
        """
        获取角色并加载成员关系
        
        Args:
            role_id: 角色 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            角色实例（含成员列表）
        """
        query = select(self.model).where(
            self.model.id == role_id
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        query = query.options(
            selectinload(self.model.admins),
            selectinload(self.model.leader),
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_organization_root_nodes(
        self,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取组织架构根节点列表（用于按需加载树）
        
        Args:
            include_deleted: 是否包含已删除记录
        
        Returns:
            根节点列表（level=1 且 parent_id=None），含关联数据
        """
        query = select(self.model).where(
            self.model.parent_id.is_(None)
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 加载关联数据
        query = query.options(
            selectinload(self.model.children),
            selectinload(self.model.admins),
            selectinload(self.model.leader),
        )
        query = query.order_by(
            self.model.sort_order.asc(),
            self.model.id.asc(),
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_children_with_details(
        self,
        parent_id: int,
        include_deleted: bool = False,
    ) -> list[AdminRole]:
        """
        获取指定节点的直接子节点（含关联数据）
        
        Args:
            parent_id: 父节点 ID
            include_deleted: 是否包含已删除记录
        
        Returns:
            子节点列表，含成员等关联数据
        """
        query = select(self.model).where(
            self.model.parent_id == parent_id
        )
        
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        
        # 加载关联数据
        query = query.options(
            selectinload(self.model.children),
            selectinload(self.model.admins),
            selectinload(self.model.leader),
        )
        query = query.order_by(
            self.model.sort_order.asc(),
            self.model.id.asc(),
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


__all__ = ["AdminRoleRepository"]
