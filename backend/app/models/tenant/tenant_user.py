"""
企业业务用户模型 / Tenant User Model

企业的终端用户（C端用户/业务用户）
Tenant end-users (C-side users / business users).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.enums.common import ApprovalStatusEnum


class TenantUser(TenantModel):
    """
    企业业务用户模型 / Tenant user model.

    - 属于特定企业
    - 企业的终端用户（客户、会员等）
    - 与企业管理员（TenantAdmin）独立
    """

    __tablename__ = "tenant_users"

    __ai_policy__ = {
        "label": "终端用户",
        "keywords": ["用户", "user", "终端用户"],
        "allow_read": True,
    }

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_tenant_user_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_tenant_user_tenant_email"),
        UniqueConstraint("tenant_id", "phone", name="uq_tenant_user_tenant_phone"),
    )

    # 可过滤字段声明 / Declares filterable fields
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "username": "username",
        "email": "email",
        "phone": "phone",
        "nickname": "nickname",
        "is_active": "is_active",
        "role_id": "role_id",
        "org_node_id": "org_node_id",
        "gender": "gender",
        "approval_status": "approval_status",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "last_login_at": "last_login_at",
    }

    # 可排序字段声明 / Declares sortable fields
    __sortable__ = [
        "id", "username", "email", "nickname",
        "is_active", "approval_status", "gender",
        "created_at", "updated_at", "last_login_at",
    ]

    # 下拉选项配置 / Select dropdown config
    __selectable__ = {
        "label": "nickname",
        "value": "id",
        "search": ["username", "nickname", "email"],
        "extra": ["username", "email", "avatar"],
    }

    # 基本信息 / Basic info
    username: Mapped[str | None] = mapped_column(
        String(50), index=True, nullable=True, comment="用户名 / Username",
    )
    email: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True, comment="邮箱 / Email",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), index=True, nullable=True, comment="手机号 / Phone",
    )

    # 认证信息 / Credentials
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="密码哈希 / Password hash",
    )

    # 第三方登录 / Third-party login
    openid: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="微信 OpenID / WeChat OpenID",
    )
    unionid: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="微信 UnionID / WeChat UnionID",
    )

    # 角色 / Role assignment
    role_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_user_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="用户角色 ID / User role id",
    )
    org_node_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenant_org_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="组织节点 ID / Org node id",
    )

    # 用户状态 / Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否激活 / Active",
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStatusEnum.APPROVED.value,
        server_default=ApprovalStatusEnum.APPROVED.value,
        comment="审批状态: pending/approved/rejected / Approval status",
    )

    # 个人资料 / Profile
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="昵称 / Nickname",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像附件 ID（兼容旧 URL 值） / Avatar attachment id",
    )
    gender: Mapped[int] = mapped_column(
        Integer, default=0, comment="性别: 0未知 1男 2女 / Gender code",
    )

    # 扩展信息 / Extra JSON
    extra: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="扩展信息 / Extra payload",
    )

    # 登录信息 / Login audit
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录时间 / Last login at",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="最后登录 IP / Last login IP",
    )

    # 登录安全信息 / Login security
    login_fail_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="登录失败次数 / Failed login count",
    )
    last_fail_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录失败时间 / Last failed login",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="账户锁定到期时间 / Locked until",
    )

    # ========== 关联关系 ========== / Relationships
    role: Mapped["TenantUserRole | None"] = relationship(
        "TenantUserRole",
        back_populates="users",
        lazy="selectin",
        foreign_keys=[role_id],
    )
    org_node: Mapped["TenantOrgNode | None"] = relationship(
        "TenantOrgNode",
        back_populates="users",
        lazy="selectin",
        foreign_keys=[org_node_id],
    )

    def __repr__(self) -> str:
        return f"<TenantUser(id={self.id}, tenant_id={self.tenant_id})>"


if TYPE_CHECKING:
    from app.models.auth.tenant_user_role import TenantUserRole
    from app.models.org.tenant_org_node import TenantOrgNode


__all__ = ["TenantUser"]
