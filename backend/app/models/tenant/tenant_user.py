"""
租户业务用户模型

租户的终端用户（C端用户/业务用户）
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class TenantUser(TenantModel):
    """
    租户业务用户模型

    - 属于特定租户
    - 租户的终端用户（客户、会员等）
    - 与租户管理员（TenantAdmin）独立
    """

    __tablename__ = "tenant_users"

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_tenant_user_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_tenant_user_tenant_email"),
        UniqueConstraint("tenant_id", "phone", name="uq_tenant_user_tenant_phone"),
    )

    # 基本信息
    username: Mapped[str | None] = mapped_column(
        String(50), index=True, nullable=True, comment="用户名"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True, comment="邮箱"
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), index=True, nullable=True, comment="手机号"
    )

    # 认证信息
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="密码哈希"
    )

    # 第三方登录
    openid: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="微信 OpenID"
    )
    unionid: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="微信 UnionID"
    )

    # 用户状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否激活"
    )

    # 个人资料
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="昵称"
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像 URL"
    )
    gender: Mapped[int] = mapped_column(
        Integer, default=0, comment="性别: 0未知 1男 2女"
    )

    # 扩展信息
    extra: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="扩展信息"
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

    def __repr__(self) -> str:
        return f"<TenantUser(id={self.id}, tenant_id={self.tenant_id})>"


__all__ = ["TenantUser"]
