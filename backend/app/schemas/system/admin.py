"""
平台管理员相关 Schema / Platform Admin Schema

定义平台管理员 API 的请求和响应数据结构
Defines platform admin API request and response data structures.
"""

from datetime import datetime

from pydantic import Field, field_validator

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


class AdminLoginRequest(BaseSchema):
    """管理员登录请求 / Admin login request."""

    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class AdminResponse(BaseSchema):
    """管理员信息响应 / Admin info response."""

    id: int = Field(..., description="管理员 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID")
    is_active: bool = Field(..., description="是否激活")
    ai_enabled: bool = Field(True, description="是否允许使用 AI 对话")
    effective_ai_enabled: bool = Field(True, description="当前账号实际是否可用 AI")
    ai_unavailable_reason: str | None = Field(None, description="AI 不可用原因代码")
    is_super: bool = Field(..., description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")
    role_name: str | None = Field(None, description="角色名称")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")

    @classmethod
    def from_model(cls, admin) -> "AdminResponse":
        """从模型创建响应，包含角色名称 / Build response from model with role name."""
        return cls(
            id=admin.id,
            username=admin.username,
            email=admin.email,
            phone=admin.phone,
            nickname=admin.nickname,
            avatar=admin.avatar,
            is_active=admin.is_active,
            ai_enabled=getattr(admin, "ai_enabled", True),
            effective_ai_enabled=getattr(admin, "effective_ai_enabled", None)
            if getattr(admin, "effective_ai_enabled", None) is not None
            else getattr(admin, "ai_enabled", True),
            ai_unavailable_reason=getattr(admin, "ai_unavailable_reason", None),
            is_super=admin.is_super,
            role_id=admin.role_id,
            role_name=admin.role.name if admin.role else None,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
        )

    @field_validator("avatar", mode="before")
    @classmethod
    def normalize_avatar(cls, value: object) -> str | None:
        return _normalize_readable_avatar_value(value)


class AdminCreateRequest(BaseSchema):
    """创建管理员请求 / Create admin request."""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    ai_enabled: bool = Field(True, description="是否允许使用 AI 对话")
    is_super: bool = Field(False, description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")


class AdminUpdateRequest(BaseSchema):
    """更新管理员请求 / Update admin request."""

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID")
    is_active: bool | None = Field(None, description="是否激活")
    ai_enabled: bool | None = Field(None, description="是否允许使用 AI 对话")
    is_super: bool | None = Field(None, description="是否超级管理员")
    role_id: int | None = Field(None, description="角色 ID")

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: object) -> str | None:
        return _validate_writable_avatar_value(value)


class AdminChangePasswordRequest(BaseSchema):
    """管理员修改密码请求 / Admin change password request."""

    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class AdminUpdateProfileRequest(BaseSchema):
    """管理员自助修改个人信息请求 / Admin self-update profile request."""

    nickname: str | None = Field(None, max_length=50, description="昵称")
    avatar: str | None = Field(None, max_length=500, description="头像附件 ID")
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: object) -> str | None:
        return _validate_writable_avatar_value(value)


__all__ = [
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    "AdminUpdateProfileRequest",
]
