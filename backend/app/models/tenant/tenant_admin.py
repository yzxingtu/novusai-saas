"""
租户管理员模型

租户后台管理人员，区别于租户业务用户
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel


class TenantAdmin(TenantModel):
    """
    租户管理员模型
    
    - 属于特定租户
    - 管理租户后台
    - 可管理租户内的用户、配置等
    - 独立于业务用户（TenantUser）
    """
    
    __tablename__ = "tenant_admins"
    
    # 可过滤字段声明（注意：不包含 password_hash 等敏感字段）
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "username": "username",
        "email": "email",
        "phone": "phone",
        "is_active": "is_active",
        "is_owner": "is_owner",
        "nickname": "nickname",
        "role_id": "role_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    
    # 下拉选项配置
    __selectable__ = {
        "label": "username",
        "value": "id",
        "search": ["username", "nickname", "email"],
        "extra": ["nickname", "avatar"],
    }
    
    # 基本信息
    username: Mapped[str] = mapped_column(
        String(50), index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255), index=True, comment="邮箱"
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), index=True, nullable=True, comment="手机号"
    )
    
    # 认证信息
    password_hash: Mapped[str] = mapped_column(
        String(255), comment="密码哈希"
    )
    
    # 管理员状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否激活"
    )
    is_owner: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否租户所有者（最高权限）"
    )
    
    # 个人资料
    nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="昵称"
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像 URL"
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
    
    # 角色关联（租户内角色）
    role_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenant_admin_roles.id"), nullable=True, comment="角色 ID"
    )
    
    # 角色关系
    role: Mapped["TenantAdminRole | None"] = relationship(
        "TenantAdminRole",
        back_populates="admins",
        lazy="selectin",
        foreign_keys=[role_id],
    )
    
    def __repr__(self) -> str:
        return f"<TenantAdmin(id={self.id}, tenant_id={self.tenant_id}, username={self.username})>"
    
    def has_permission(self, permission_code: str) -> bool:
        """
        检查租户管理员是否拥有指定权限
        
        Args:
            permission_code: 权限代码
        
        Returns:
            是否拥有该权限
        """
        # 租户所有者拥有所有权限
        if self.is_owner:
            return True
        # 检查角色权限
        if self.role:
            return self.role.has_permission(permission_code)
        return False


# 类型注解导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.auth.tenant_admin_role import TenantAdminRole


__all__ = ["TenantAdmin"]
