"""
平台管理员模型 / Platform Admin Model

平台级别的超级管理员，独立于企业体系
Platform-level super administrators, independent of the tenant system.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy


class Admin(BaseModel):
    """
    平台管理员模型 / Platform admin model.

    - 独立于企业体系
    - 用于平台后台管理
    - 可管理所有企业和系统配置
    """

    __tablename__ = "admins"

    __delete_deps__ = [
        DeletionDep("AdminRole", "leader_id", DeletionStrategy.NULLIFY,
                    label_field="name", i18n_key="admin_role_leader"),
        DeletionDep("AdminOrgNode", "leader_id", DeletionStrategy.NULLIFY,
                    label_field="name", i18n_key="admin_org_node_leader"),
    ]

    # 可过滤字段声明（注意：不包含 password_hash 等敏感字段）
    __filterable__ = {
        "id": "id",
        "username": "username",
        "email": "email",
        "phone": "phone",
        "is_active": "is_active",
        "is_super": "is_super",
        "nickname": "nickname",
        "role_id": "role_id",
        "org_node_id": "org_node_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = ["id", "username", "email", "nickname", "is_active", "created_at", "updated_at", "last_login_at"]

    # 下拉选项配置
    __selectable__ = {
        "label": "username",
        "value": "id",
        "search": ["username", "nickname", "email"],
        "extra": ["nickname", "avatar"],
    }

    # 基本信息
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, comment="邮箱"
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True, comment="手机号"
    )

    # 认证信息
    password_hash: Mapped[str] = mapped_column(
        String(255), comment="密码哈希"
    )

    # 管理员状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否激活"
    )
    is_super: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否超级管理员（最高权限）"
    )

    # 个人资料
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="昵称"
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像附件 ID（兼容旧 URL 值）"
    )

    # 登录信息
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录时间"
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="最后登录 IP"
    )

    # 登录安全信息
    login_fail_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="登录失败次数"
    )
    last_fail_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录失败时间"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="账户锁定到期时间"
    )

    # 角色关联（平台角色）
    role_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admin_roles.id"), nullable=True, comment="角色 ID"
    )
    org_node_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("admin_org_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="组织节点 ID",
    )

    # 角色关系
    role: Mapped["AdminRole | None"] = relationship(
        "AdminRole",
        back_populates="admins",
        lazy="selectin",
        foreign_keys=[role_id],
    )
    org_node: Mapped["AdminOrgNode | None"] = relationship(
        "AdminOrgNode",
        back_populates="admins",
        lazy="selectin",
        foreign_keys=[org_node_id],
    )

    def __repr__(self) -> str:
        return f"<Admin(id={self.id}, username={self.username})>"

    def has_permission(self, permission_code: str) -> bool:
        """
        检查管理员是否拥有指定权限 / Check if admin has the given permission.

        Args:
            permission_code: 权限代码

        Returns:
            是否拥有该权限
        """
        # 超级管理员拥有所有权限
        if self.is_super:
            return True
        # 检查角色权限
        if self.role:
            return self.role.has_permission(permission_code)
        return False

if TYPE_CHECKING:
    from app.models.auth.admin_role import AdminRole
    from app.models.org.admin_org_node import AdminOrgNode


__all__ = ["Admin"]
