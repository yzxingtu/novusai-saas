"""
企业用户相关 Schema / Tenant User Schema

定义企业用户（C端用户）API 的请求和响应数据结构
Defines tenant user (end-user) API request and response data structures.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.base_schema import BaseSchema


def _validate_writable_avatar_value(value: object) -> str | None:
    """中文: 写入边界只接受附件 ID。

    EN: Write boundaries accept attachment IDs only.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("avatar must be a positive attachment ID")
    if isinstance(value, int):
        if value > 0:
            return str(value)
        raise ValueError("avatar must be a positive attachment ID")
    if not isinstance(value, str):
        raise ValueError("avatar must be a positive attachment ID")

    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.isdecimal() and not normalized.startswith("0"):
        return normalized
    raise ValueError("avatar must be a positive attachment ID")


def _normalize_readable_avatar_value(value: object) -> str | None:
    """中文: 响应边界隐藏非附件 ID 的存量头像值。

    EN: Response boundaries hide stored avatar values that are not attachment IDs.
    """
    try:
        return _validate_writable_avatar_value(value)
    except ValueError:
        return None


class TenantUserLoginRequest(BaseSchema):
    """企业用户登录请求 / Tenant user login request."""

    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    tenant_code: str | None = Field(
        None, max_length=50, description="企业编码（用于限定登录范围）"
    )
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class TenantUserDevBootstrapRequest(BaseSchema):
    """开发环境企业用户 bootstrap 登录请求 / Dev bootstrap request for tenant users."""

    bootstrap_secret: str = Field(
        ...,
        min_length=1,
        description="开发环境 bootstrap 密钥 / Development bootstrap secret",
    )
    username: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="用户名、邮箱或手机号 / Username, email, or phone",
    )
    tenant_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="企业编码 / Tenant code",
    )


class SendLoginCodeRequest(BaseSchema):
    """发送登录验证码请求 / Send login code request."""

    channel: Literal["email", "sms"] = Field(
        "email", description="验证码渠道: email/sms"
    )
    email: str | None = Field(None, max_length=255, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")
    tenant_code: str | None = Field(None, max_length=50, description="企业编码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class LoginByCodeRequest(BaseSchema):
    """验证码登录请求 / Login by code request."""

    channel: Literal["email", "sms"] = Field(
        "email", description="验证码渠道: email/sms"
    )
    code: str = Field(..., min_length=4, max_length=10, description="验证码")
    email: str | None = Field(None, max_length=255, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")
    tenant_code: str | None = Field(None, max_length=50, description="企业编码")


class TenantUserResponse(BaseSchema):
    """企业用户信息响应 / Tenant user response."""

    id: int = Field(..., description="用户 ID")
    tenant_id: int = Field(..., description="企业 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID")
    gender: int = Field(0, description="性别: 0未知 1男 2女")
    is_active: bool = Field(..., description="是否激活")
    approval_status: str = Field("approved", description="审批状态")
    role_id: int | None = Field(None, description="权限角色 ID")
    role_name: str | None = Field(None, description="权限角色名称")
    org_node_id: int | None = Field(None, description="组织归属节点 ID")
    org_node_name: str | None = Field(None, description="组织归属节点名称")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    @field_validator("avatar", mode="before")
    @classmethod
    def normalize_avatar(cls, value: object) -> str | None:
        return _normalize_readable_avatar_value(value)


class TenantUserCreateRequest(BaseSchema):
    """创建企业用户请求 / Create tenant user request."""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    role_id: int | None = Field(None, description="权限角色 ID")
    org_node_id: int | None = Field(None, description="组织归属节点 ID")


class TenantUserUpdateRequest(BaseSchema):
    """更新企业用户请求 / Update tenant user request."""

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID")
    is_active: bool | None = Field(None, description="是否激活")
    role_id: int | None = Field(None, description="权限角色 ID")
    org_node_id: int | None = Field(None, description="组织归属节点 ID")
    gender: int | None = Field(None, ge=0, le=2, description="性别: 0未知 1男 2女")

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: object) -> str | None:
        return _validate_writable_avatar_value(value)


class TenantUserChangePasswordRequest(BaseSchema):
    """企业用户修改密码请求 / Tenant user change password request."""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class TenantUserRegisterRequest(BaseSchema):
    """企业用户注册请求 / Tenant user register request."""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., max_length=255, description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    confirm_password: str = Field(
        ..., min_length=6, max_length=50, description="确认密码"
    )
    phone: str | None = Field(None, max_length=20, description="手机号")
    nickname: str | None = Field(None, max_length=100, description="昵称")
    tenant_code: str | None = Field(None, max_length=50, description="企业编码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")

    @model_validator(mode="after")
    def passwords_match(self) -> "TenantUserRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class TenantUserProfileUpdateRequest(BaseSchema):
    """企业用户资料更新请求 / Tenant user profile update request."""

    nickname: str | None = Field(None, max_length=100, description="昵称")
    avatar: str | None = Field(None, max_length=500, description="头像附件 ID")
    gender: int | None = Field(None, ge=0, le=2, description="性别: 0未知 1男 2女")
    phone: str | None = Field(None, max_length=20, description="手机号")
    email: str | None = Field(None, max_length=255, description="邮箱")

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: object) -> str | None:
        return _validate_writable_avatar_value(value)


class ForgotPasswordRequest(BaseSchema):
    """忘记密码请求 / Forgot password request."""

    email: str = Field(..., max_length=255, description="邮箱")
    tenant_code: str | None = Field(None, max_length=50, description="企业编码")
    channel: str = Field("email", description="发送渠道: email/sms")


class ResetPasswordRequest(BaseSchema):
    """重置密码请求 / Reset password request."""

    email: str = Field(..., max_length=255, description="邮箱")
    code: str = Field(..., min_length=4, max_length=10, description="验证码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")
    confirm_password: str = Field(
        ..., min_length=6, max_length=50, description="确认密码"
    )
    tenant_code: str | None = Field(None, max_length=50, description="企业编码")

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


__all__ = [
    "TenantUserLoginRequest",
    "TenantUserDevBootstrapRequest",
    "SendLoginCodeRequest",
    "LoginByCodeRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    "TenantUserRegisterRequest",
    "TenantUserProfileUpdateRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
]
