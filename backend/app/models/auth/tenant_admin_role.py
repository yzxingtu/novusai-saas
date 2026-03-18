"""
企业管理员角色模型 / Tenant Admin Role Model

企业级别的角色，用于企业管理员权限控制，支持多级角色层级结构
Tenant-level roles for tenant admin permission control, supports multi-level role hierarchy.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.enums.role import DataScope, RoleType

# 角色-权限关联表（多对多）
tenant_admin_role_permissions = Table(
    "tenant_admin_role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("tenant_admin_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class TenantAdminRole(TenantModel):
    """
    企业管理员角色模型 / Tenant admin role model.

    - 属于特定企业
    - 用于企业管理员的权限控制
    - 与 Permission 多对多关联
    - 支持多级角色层级结构（父子关系）
    - 子角色自动继承父角色的权限
    - 不同企业可以有同名角色
    """

    __tablename__ = "tenant_admin_roles"

    __ai_policy__ = {
        "label": "企业管理角色",
        "keywords": ["角色", "role"],
        "allow_read": True,
    }

    __delete_deps__ = [
        DeletionDep("TenantAdmin", "role_id", DeletionStrategy.BLOCK,
                    label_field="username", i18n_key="tenant_admin"),
        DeletionDep("TenantAdminRole", "parent_id", DeletionStrategy.BLOCK,
                    label_field="name", i18n_key="tenant_admin_role"),
    ]

    # 可过滤字段声明
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "name": "name",
        "code": "code",
        "is_system": "is_system",
        "is_active": "is_active",
        "sort_order": "sort_order",
        "parent_id": "parent_id",
        "level": "level",
        "type": "type",
        "leader_id": "leader_id",
        "data_scope": "data_scope",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选项配置
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "code"],
        "extra": ["code", "type", "level"],
        # 树型配置
        "tree": {
            "parent_field": "parent_id",
            "children_field": "children",
            "order_by": "sort_order",
        },
    }

    # 排序配置
    __sortable__ = {
        "field": "sort_order",      # 排序字段名
        "step": 1000,               # 排序步长
        "scope_fields": ["tenant_id", "parent_id"],  # 企业内同级排序
    }

    # 角色名称
    name: Mapped[str] = mapped_column(
        String(50), comment="角色名称"
    )

    # 角色代码（企业内唯一）
    code: Mapped[str] = mapped_column(
        String(50), index=True, comment="角色代码"
    )

    # 角色描述
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="角色描述"
    )

    # 是否系统内置（内置角色不可删除）
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否系统内置"
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )

    # 排序
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序"
    )

    # ========== 层级结构字段 ==========
    # 父角色 ID
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_admin_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父角色 ID"
    )

    # 层级路径（物化路径，如 /1/3/7/）
    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="层级路径"
    )

    # 层级深度（根节点为 1）
    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="层级深度"
    )

    # ========== 组织架构字段 ==========
    # 节点类型（部门/岗位/角色）
    type: Mapped[str] = mapped_column(
        String(20),
        default=RoleType.ROLE.value,
        index=True,
        comment="节点类型: department/position/role"
    )

    # 是否允许添加成员
    allow_members: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否允许添加成员"
    )

    # 负责人 ID（仅部门类型可设置）
    leader_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="负责人 ID"
    )

    # ========== 数据权限字段 ==========
    # 数据范围（用于行级数据过滤） / Data scope for row-level filtering
    data_scope: Mapped[str] = mapped_column(
        String(20),
        default=DataScope.SELF_ONLY.value,
        index=True,
        comment="数据范围: all/dept_children/dept_only/self/custom"
    )

    # 自定义部门 ID 列表（当 data_scope=custom 时生效） / Custom department IDs (when data_scope=custom)
    custom_dept_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="自定义部门 ID 列表 [1,2,3]"
    )

    # ========== 关联关系 ==========
    # 父角色关系（自引用）
    parent: Mapped["TenantAdminRole | None"] = relationship(
        "TenantAdminRole",
        remote_side="TenantAdminRole.id",
        back_populates="children",
        lazy="selectin",
    )

    # 子角色关系（自引用）
    children: Mapped[list["TenantAdminRole"]] = relationship(
        "TenantAdminRole",
        back_populates="parent",
        lazy="selectin",
    )

    # 关联权限（多对多）
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=tenant_admin_role_permissions,
        lazy="selectin",
    )

    # 关联企业管理员（一对多）- 节点成员
    admins: Mapped[list["TenantAdmin"]] = relationship(
        "TenantAdmin",
        back_populates="role",
        lazy="selectin",
        foreign_keys="TenantAdmin.role_id",
    )

    # 负责人关系
    leader: Mapped["TenantAdmin | None"] = relationship(
        "TenantAdmin",
        foreign_keys=[leader_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TenantAdminRole(id={self.id}, tenant_id={self.tenant_id}, code={self.code}, level={self.level})>"

    @property
    def children_count(self) -> int:
        """获取子角色数量 / Get children role count."""
        return len([c for c in self.children if not c.is_deleted])

    @property
    def permissions_count(self) -> int:
        """获取权限数量 / Get permissions count."""
        return len(self.permissions)

    @property
    def has_children(self) -> bool:
        """是否有子角色 / Whether has child roles."""
        return self.children_count > 0

    @property
    def has_admins(self) -> bool:
        """是否有关联的管理员 / Whether has linked admins."""
        return len([a for a in self.admins if not a.is_deleted]) > 0

    @property
    def member_count(self) -> int:
        """获取节点成员数量 / Get node member count."""
        return len([a for a in self.admins if not a.is_deleted])

    @property
    def leader_name(self) -> str | None:
        """获取负责人名称 / Get leader display name."""
        if self.leader and not self.leader.is_deleted:
            return self.leader.nickname or self.leader.username
        return None

    @property
    def type_enum(self) -> RoleType | None:
        """获取节点类型枚举 / Get node type enum."""
        return RoleType.from_value(self.type)

    def has_permission(self, permission_code: str) -> bool:
        """
        检查角色是否拥有指定权限（仅检查自身权限，不含继承）/ Check if role has permission (self only, no inheritance).

        Args:
            permission_code: 权限代码

        Returns:
            是否拥有该权限
        """
        return any(p.code == permission_code for p in self.permissions)

    def get_ancestor_ids(self) -> list[int]:
        """
        从 path 中解析所有祖先角色 ID / Parse ancestor role IDs from path.

        Returns:
            祖先角色 ID 列表（不含自身）
        """
        if not self.path:
            return []
        # path 格式为 /1/3/7/，解析出 [1, 3, 7]
        parts = [p for p in self.path.strip('/').split('/') if p]
        # 排除自身 ID
        return [int(p) for p in parts if int(p) != self.id]

if TYPE_CHECKING:
    from app.models.auth.permission import Permission
    from app.models.tenant.tenant_admin import TenantAdmin


__all__ = ["TenantAdminRole", "tenant_admin_role_permissions"]
