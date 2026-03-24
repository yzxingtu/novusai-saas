"""
权限模型 / Permission Model

定义系统中的所有权限点，支持装饰器自动同步
Defines all permission points in the system, supports decorator-based auto synchronization.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy


class Permission(BaseModel):
    """
    权限模型 / Permission model.

    - 定义系统中的权限点
    - 支持菜单权限和操作权限
    - 权限代码在同一 scope 内唯一（code + scope 联合唯一）
    - 通过装饰器自动注册并同步到数据库
    """

    __tablename__ = "permissions"

    __delete_deps__ = [
        DeletionDep("Permission", "parent_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="code", i18n_key="permission_child"),
    ]

    # 联合唯一约束：code + scope / Unique (code, scope)
    __table_args__ = (
        UniqueConstraint("code", "scope", name="uq_permissions_code_scope"),
    )

    # 排序配置 / Sort order config
    __sortable__ = {
        "field": "sort_order",      # 排序字段名 / Sort field name
        "step": 1000,               # 排序步长 / Sort step
        "scope_fields": ["parent_id"],  # 同级权限内排序 / Sibling sort scope
    }

    # 权限代码（同一 scope 内唯一） / Permission code (unique per scope)
    code: Mapped[str] = mapped_column(
        String(100), index=True,
        comment="权限代码（如：user:create, menu:tenant.user） / Permission code",
    )

    # 权限名称 / Display name
    name: Mapped[str] = mapped_column(
        String(100), comment="权限名称 / Display name",
    )

    # 权限描述 / Description
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="权限描述 / Description",
    )

    # 权限类型: menu(菜单) / operation(操作) / Kind: menu or operation
    type: Mapped[str] = mapped_column(
        String(20), index=True, comment="权限类型: menu/operation / Permission kind",
    )

    # 作用域: admin(平台) / tenant(企业) / both(两端) / Scope
    scope: Mapped[str] = mapped_column(
        String(20), index=True, comment="作用域: admin/tenant/both / Scope",
    )

    # 资源标识（如: user, order, menu） / Resource key
    resource: Mapped[str] = mapped_column(
        String(50), index=True, comment="资源标识 / Resource",
    )

    # 操作标识（如: create, read, update, delete, admin.user） / Action key
    action: Mapped[str] = mapped_column(
        String(50), comment="操作标识 / Action",
    )

    # 父级权限（用于菜单层级） / Parent permission (menu tree)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("permissions.id"), nullable=True, comment="父级权限 ID / Parent id",
    )

    # 排序 / Sort order
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序 / Sort order",
    )

    # 菜单专用字段 / Menu-only fields
    icon: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="图标（菜单专用） / Icon (menu)",
    )
    path: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="前端路由（菜单专用） / Frontend route (menu)",
    )
    component: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="前端组件（菜单专用） / Frontend component (menu)",
    )
    hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否隐藏菜单（仅做权限控制） / Hide in menu (ACL only)",
    )

    # 状态 / Status
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, comment="是否启用 / Enabled",
    )

    # 关系: 子权限 / Child permissions
    children: Mapped[list["Permission"]] = relationship(
        "Permission",
        back_populates="parent",
        lazy="selectin",
    )
    parent: Mapped["Permission | None"] = relationship(
        "Permission",
        back_populates="children",
        remote_side="Permission.id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code={self.code}, type={self.type})>"


__all__ = ["Permission"]
