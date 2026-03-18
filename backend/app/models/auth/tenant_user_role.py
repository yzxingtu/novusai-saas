"""
企业用户角色模型 / Tenant User Role Model

企业级别的用户角色，用于企业业务用户的权限控制（扁平结构，无层级）
Tenant-level user roles for tenant business user permission control (flat structure, no hierarchy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy


# 用户角色-权限关联表（多对多）
tenant_user_role_permissions = Table(
    "tenant_user_role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("tenant_user_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class TenantUserRole(TenantModel):
    """
    企业用户角色模型 / Tenant user role model.

    - 属于特定企业
    - 用于企业业务用户的权限控制
    - 与 Permission 多对多关联
    - 扁平结构，不支持层级
    - 不同企业可以有同名角色
    """

    __tablename__ = "tenant_user_roles"

    __ai_policy__ = {
        "label": "企业用户角色",
        "keywords": ["角色", "role"],
        "allow_read": True,
    }

    __delete_deps__ = [
        DeletionDep("TenantUser", "role_id", DeletionStrategy.BLOCK,
                    label_field="username", i18n_key="tenant_user"),
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
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # 下拉选项配置
    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "code"],
        "extra": ["code"],
    }

    # 排序配置
    __sortable__ = {
        "field": "sort_order",
        "step": 1000,
        "scope_fields": ["tenant_id"],
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

    # ========== 关联关系 ==========
    # 关联权限（多对多）
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=tenant_user_role_permissions,
        lazy="selectin",
    )

    # 关联企业用户（一对多）
    users: Mapped[list["TenantUser"]] = relationship(
        "TenantUser",
        back_populates="role",
        lazy="selectin",
        foreign_keys="TenantUser.role_id",
    )

    def __repr__(self) -> str:
        return f"<TenantUserRole(id={self.id}, tenant_id={self.tenant_id}, code={self.code})>"

    @property
    def permissions_count(self) -> int:
        """获取权限数量 / Get permissions count."""
        return len(self.permissions)

    @property
    def member_count(self) -> int:
        """获取用户数量 / Get user count."""
        return len([u for u in self.users if not u.is_deleted])

    def has_permission(self, permission_code: str) -> bool:
        """
        检查角色是否拥有指定权限 / Check if role has the given permission.

        Args:
            permission_code: 权限代码 / Permission code.

        Returns:
            是否拥有该权限 / Whether the role has the permission.
        """
        return any(p.code == permission_code for p in self.permissions)


if TYPE_CHECKING:
    from app.models.auth.permission import Permission
    from app.models.tenant.tenant_user import TenantUser


__all__ = ["TenantUserRole", "tenant_user_role_permissions"]
