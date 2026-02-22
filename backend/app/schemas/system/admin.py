"""
平台管理员相关 Schema

定义平台管理员 API 的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class AdminLoginRequest(BaseSchema):
    """管理员登录请求"""
    
    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class AdminResponse(BaseSchema):
    """管理员信息响应"""
    
    id: int = Field(..., description="管理员 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool = Field(..., description="是否激活")
    is_super: bool = Field(..., description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")
    role_name: str | None = Field(None, description="角色名称")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    
    @classmethod
    def from_model(cls, admin) -> "AdminResponse":
        """从模型创建响应，包含角色名称"""
        return cls(
            id=admin.id,
            username=admin.username,
            email=admin.email,
            phone=admin.phone,
            nickname=admin.nickname,
            avatar=admin.avatar,
            is_active=admin.is_active,
            is_super=admin.is_super,
            role_id=admin.role_id,
            role_name=admin.role.name if admin.role else None,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
        )


class AdminCreateRequest(BaseSchema):
    """创建管理员请求"""
    
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    is_super: bool = Field(False, description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")


class AdminUpdateRequest(BaseSchema):
    """更新管理员请求"""
    
    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool | None = Field(None, description="是否激活")
    is_super: bool | None = Field(None, description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")


class AdminChangePasswordRequest(BaseSchema):
    """管理员修改密码请求"""
    
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class AdminUpdateProfileRequest(BaseSchema):
    """管理员自助修改个人信息请求"""

    nickname: str | None = Field(None, max_length=50, description="昵称")
    avatar: str | None = Field(None, max_length=500, description="头像 URL")
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")


__all__ = [
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    "AdminUpdateProfileRequest",
]
