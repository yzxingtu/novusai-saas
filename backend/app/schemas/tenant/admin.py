"""
企业管理员相关 Schema / Tenant Admin Schema

定义企业管理员 API 的请求和响应数据结构
Defines tenant admin API request and response data structures.
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class TenantAdminLoginRequest(BaseSchema):
    """企业管理员登录请求 / Tenant admin login request."""

    username: str = Field(
        ..., min_length=1, max_length=50, description="用户名或邮箱 / Username or email"
    )
    password: str = Field(..., min_length=1, description="密码")
    tenant_code: str | None = Field(
        None, max_length=50, description="企业编码（用于限定登录范围）"
    )
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class TenantAdminResponse(BaseSchema):
    """企业管理员信息响应 / Tenant admin info response."""

    id: int = Field(..., description="管理员 ID / Admin ID")
    tenant_id: int = Field(..., description="企业 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID（兼容旧 URL 值）")
    is_active: bool = Field(..., description="是否激活")
    ai_enabled: bool = Field(True, description="账号级 AI 对话开关")
    is_owner: bool = Field(..., description="是否企业所有者")
    role_id: int | None = Field(None, description="角色 ID")
    role_name: str | None = Field(None, description="角色名称")
    has_plan: bool = Field(True, description="企业是否已分配套餐")
    plan_name: str | None = Field(None, description="套餐名称")
    tenant_ai_enabled: bool = Field(True, description="企业套餐/配额 AI 开关")
    effective_ai_enabled: bool = Field(True, description="当前账号实际是否可用 AI")
    ai_unavailable_reason: str | None = Field(None, description="AI 不可用原因代码")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")

    @classmethod
    def from_model(
        cls,
        admin,
        has_plan: bool = True,
        plan_name: str | None = None,
        tenant_ai_enabled: bool = True,
        effective_ai_enabled: bool | None = None,
        ai_unavailable_reason: str | None = None,
    ) -> "TenantAdminResponse":
        """从模型创建响应，包含角色名称和套餐状态 / Build response from model with role name and plan status."""
        account_ai_enabled = getattr(admin, "ai_enabled", True)
        effective_ai_enabled = (
            account_ai_enabled and tenant_ai_enabled
            if effective_ai_enabled is None
            else effective_ai_enabled
        )
        return cls(
            id=admin.id,
            tenant_id=admin.tenant_id,
            username=admin.username,
            email=admin.email,
            phone=admin.phone,
            nickname=admin.nickname,
            avatar=admin.avatar,
            is_active=admin.is_active,
            ai_enabled=account_ai_enabled,
            is_owner=admin.is_owner,
            role_id=admin.role_id,
            role_name=admin.role.name if admin.role else None,
            has_plan=has_plan,
            plan_name=plan_name,
            tenant_ai_enabled=tenant_ai_enabled,
            effective_ai_enabled=effective_ai_enabled,
            ai_unavailable_reason=ai_unavailable_reason,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
        )


class TenantAdminCreateRequest(BaseSchema):
    """创建企业管理员请求 / Create tenant admin request."""

    username: str = Field(
        ..., min_length=2, max_length=50, description="用户名 / Username"
    )
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    ai_enabled: bool = Field(True, description="账号级 AI 对话开关")
    is_owner: bool = Field(False, description="是否企业所有者")
    role_id: int | None = Field(None, description="角色 ID")


class TenantAdminUpdateRequest(BaseSchema):
    """更新企业管理员请求 / Update tenant admin request."""

    email: str | None = Field(None, description="邮箱 / Email")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像附件 ID（兼容旧 URL 值）")
    is_active: bool | None = Field(None, description="是否激活")
    ai_enabled: bool | None = Field(None, description="账号级 AI 对话开关")
    is_owner: bool | None = Field(None, description="是否企业所有者")
    role_id: int | None = Field(None, description="角色 ID")


class TenantAdminChangePasswordRequest(BaseSchema):
    """企业管理员修改密码请求 / Tenant admin change password request."""

    old_password: str = Field(..., min_length=1, description="旧密码 / Old password")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class TenantAdminUpdateProfileRequest(BaseSchema):
    """企业管理员自助修改个人信息请求 / Tenant admin self-update profile request."""

    nickname: str | None = Field(None, max_length=50, description="昵称 / Nickname")
    avatar: str | None = Field(
        None, max_length=500, description="头像附件 ID（兼容旧 URL 值）"
    )
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")


__all__ = [
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    "TenantAdminUpdateProfileRequest",
]
