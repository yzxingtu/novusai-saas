"""
租户用户相关 Schema

定义租户用户（C端用户）API 的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field, model_validator

from app.core.base_schema import BaseSchema


class TenantUserLoginRequest(BaseSchema):
    """租户用户登录请求"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    tenant_code: str | None = Field(None, max_length=50, description="租户编码（用于限定登录范围）")
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
    gender: int = Field(0, description="性别: 0未知 1男 2女")
    is_active: bool = Field(..., description="是否激活")
    approval_status: str = Field("approved", description="审批状态")
    role_id: int | None = Field(None, description="角色 ID")
    role_name: str | None = Field(None, description="角色名称")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")


class TenantUserCreateRequest(BaseSchema):
    """创建租户用户请求"""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    role_id: int | None = Field(None, description="角色 ID")


class TenantUserUpdateRequest(BaseSchema):
    """更新租户用户请求"""

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool | None = Field(None, description="是否激活")
    role_id: int | None = Field(None, description="角色 ID")
    gender: int | None = Field(None, ge=0, le=2, description="性别: 0未知 1男 2女")


class TenantUserChangePasswordRequest(BaseSchema):
    """租户用户修改密码请求"""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class TenantUserRegisterRequest(BaseSchema):
    """租户用户注册请求"""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., max_length=255, description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    confirm_password: str = Field(..., min_length=6, max_length=50, description="确认密码")
    phone: str | None = Field(None, max_length=20, description="手机号")
    nickname: str | None = Field(None, max_length=100, description="昵称")
    tenant_code: str | None = Field(None, max_length=50, description="租户编码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")

    @model_validator(mode="after")
    def passwords_match(self) -> "TenantUserRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class TenantUserProfileUpdateRequest(BaseSchema):
    """租户用户资料更新请求"""

    nickname: str | None = Field(None, max_length=100, description="昵称")
    avatar: str | None = Field(None, max_length=500, description="头像 URL")
    gender: int | None = Field(None, ge=0, le=2, description="性别: 0未知 1男 2女")
    phone: str | None = Field(None, max_length=20, description="手机号")
    email: str | None = Field(None, max_length=255, description="邮箱")


class ForgotPasswordRequest(BaseSchema):
    """忘记密码请求"""

    email: str = Field(..., max_length=255, description="邮箱")
    tenant_code: str | None = Field(None, max_length=50, description="租户编码")
    channel: str = Field("email", description="发送渠道: email/sms")


class ResetPasswordRequest(BaseSchema):
    """重置密码请求"""

    email: str = Field(..., max_length=255, description="邮箱")
    code: str = Field(..., min_length=4, max_length=10, description="验证码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=50, description="确认密码")
    tenant_code: str | None = Field(None, max_length=50, description="租户编码")

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


__all__ = [
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    "TenantUserRegisterRequest",
    "TenantUserProfileUpdateRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
]
