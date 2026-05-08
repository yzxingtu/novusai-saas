"""
企业管理员模型 / Tenant Admin Model

企业后台管理人员，区别于企业业务用户
Tenant backend administrators, distinct from tenant business users.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy


class TenantAdmin(TenantModel):
    """
    企业管理员模型 / Tenant admin model.

    - 属于特定企业
    - 管理企业后台
    - 可管理企业内的用户、配置等
    - 独立于业务用户（TenantUser）
    """

    __tablename__ = "tenant_admins"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "username", name="uq_tenant_admin_tenant_username"
        ),
        UniqueConstraint("tenant_id", "email", name="uq_tenant_admin_tenant_email"),
    )

    __delete_deps__ = [
        DeletionDep(
            "TenantAdminRole",
            "leader_id",
            DeletionStrategy.NULLIFY,
            label_field="name",
            i18n_key="tenant_admin_role_leader",
        ),
        DeletionDep(
            "TenantOrgNode",
            "leader_id",
            DeletionStrategy.NULLIFY,
            label_field="name",
            i18n_key="tenant_org_node_leader",
        ),
    ]

    # 可过滤字段声明（注意：不包含 password_hash 等敏感字段） /
    # Filterable fields (excludes password_hash etc.)
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "username": "username",
        "email": "email",
        "phone": "phone",
        "is_active": "is_active",
        "ai_enabled": "ai_enabled",
        "is_owner": "is_owner",
        "nickname": "nickname",
        "role_id": "role_id",
        "org_node_id": "org_node_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = [
        "id",
        "username",
        "email",
        "nickname",
        "is_active",
        "ai_enabled",
        "is_owner",
        "role_id",
        "created_at",
        "updated_at",
        "last_login_at",
    ]

    # 下拉选项配置 / Select dropdown config
    __selectable__ = {
        "label": "username",
        "value": "id",
        "search": ["username", "nickname", "email"],
        "extra": ["nickname", "avatar"],
    }

    # 基本信息 / Basic info
    username: Mapped[str] = mapped_column(
        String(50),
        index=True,
        comment="用户名 / Username",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        index=True,
        comment="邮箱 / Email",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
        nullable=True,
        comment="手机号 / Phone",
    )

    # 认证信息 / Credentials
    password_hash: Mapped[str] = mapped_column(
        String(255),
        comment="密码哈希 / Password hash",
    )

    # 管理员状态 / Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否激活 / Active",
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="是否允许使用 AI 对话 / AI chat enabled",
    )
    is_owner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否企业所有者（最高权限） / Tenant owner",
    )

    # 个人资料 / Profile
    nickname: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="昵称 / Nickname",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="头像附件 ID / Avatar attachment id",
    )

    # 登录信息 / Login audit
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间 / Last login at",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="最后登录 IP / Last login IP",
    )

    # 登录安全信息 / Login security
    login_fail_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="登录失败次数 / Failed login count",
    )
    last_fail_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录失败时间 / Last failed login",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="账户锁定到期时间 / Locked until",
    )

    # 角色关联（企业内角色） / Role within tenant
    role_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_admin_roles.id"),
        nullable=True,
        comment="角色 ID / Role id",
    )
    org_node_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_org_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="组织节点 ID / Org node id",
    )

    # 角色关系 / Role relationships
    role: Mapped["TenantAdminRole | None"] = relationship(
        "TenantAdminRole",
        back_populates="admins",
        lazy="selectin",
        foreign_keys=[role_id],
    )
    org_node: Mapped["TenantOrgNode | None"] = relationship(
        "TenantOrgNode",
        back_populates="admins",
        lazy="selectin",
        foreign_keys=[org_node_id],
    )

    def __repr__(self) -> str:
        return f"<TenantAdmin(id={self.id}, tenant_id={self.tenant_id}, username={self.username})>"

    def has_permission(self, permission_code: str) -> bool:
        """
        检查企业管理员是否拥有指定权限 / Check if tenant admin has permission.

        Args:
            permission_code: 权限代码

        Returns:
            是否拥有该权限
        """
        # 企业所有者拥有所有权限 / Owner has all permissions
        if self.is_owner:
            return True
        # 检查角色权限 / Check role permissions
        if self.role:
            return self.role.has_permission(permission_code)
        return False


if TYPE_CHECKING:
    from app.models.auth.tenant_admin_role import TenantAdminRole
    from app.models.org.tenant_org_node import TenantOrgNode


__all__ = ["TenantAdmin"]
