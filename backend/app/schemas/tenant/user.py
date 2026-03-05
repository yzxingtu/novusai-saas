"""
租户用户相关 Schema

定义租户用户（C端用户）API 的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class TenantUserLoginRequest(BaseSchema):
    """租户用户登录请求"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class TenantUserResponse(BaseSchema):
    """租户用户信息响应"""

    id: int = Field(..., description="用户 ID")
    tenant_id: int = Field(..., description="租户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool = Field(..., description="是否激活")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")


class TenantUserCreateRequest(BaseSchema):
    """创建租户用户请求"""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")


class TenantUserUpdateRequest(BaseSchema):
    """更新租户用户请求"""

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool | None = Field(None, description="是否激活")


class TenantUserChangePasswordRequest(BaseSchema):
    """租户用户修改密码请求"""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


__all__ = [
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
]
