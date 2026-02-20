"""
租户管理员相关 Schema

定义租户管理员 API 的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class TenantAdminLoginRequest(BaseSchema):
    """租户管理员登录请求"""
    
    username: str = Field(..., min_length=1, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")
    captcha_challenge_id: str | None = Field(None, description="验证码挑战 ID")
    captcha_solution: str | None = Field(None, description="验证码答案")
    captcha_provider_code: str | None = Field(None, description="验证码提供方标识")


class TenantAdminResponse(BaseSchema):
    """租户管理员信息响应"""
    
    id: int = Field(..., description="管理员 ID")
    tenant_id: int = Field(..., description="租户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool = Field(..., description="是否激活")
    is_owner: bool = Field(..., description="是否租户所有者")
    role_id: int | None = Field(None, description="角色 ID")
    role_name: str | None = Field(None, description="角色名称")
    has_plan: bool = Field(True, description="租户是否已分配套餐")
    plan_name: str | None = Field(None, description="套餐名称")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    
    @classmethod
    def from_model(
        cls,
        admin,
        has_plan: bool = True,
        plan_name: str | None = None,
    ) -> "TenantAdminResponse":
        """从模型创建响应，包含角色名称和套餐状态"""
        return cls(
            id=admin.id,
            tenant_id=admin.tenant_id,
            username=admin.username,
            email=admin.email,
            phone=admin.phone,
            nickname=admin.nickname,
            avatar=admin.avatar,
            is_active=admin.is_active,
            is_owner=admin.is_owner,
            role_id=admin.role_id,
            role_name=admin.role.name if admin.role else None,
            has_plan=has_plan,
            plan_name=plan_name,
            last_login_at=admin.last_login_at,
            created_at=admin.created_at,
        )


class TenantAdminCreateRequest(BaseSchema):
    """创建租户管理员请求"""
    
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")
    is_owner: bool = Field(False, description="是否租户所有者")
    role_id: int | None = Field(None, description="角色 ID")


class TenantAdminUpdateRequest(BaseSchema):
    """更新租户管理员请求"""
    
    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像 URL")
    is_active: bool | None = Field(None, description="是否激活")
    is_owner: bool | None = Field(None, description="是否租户所有者")
    role_id: int | None = Field(None, description="角色 ID")


class TenantAdminChangePasswordRequest(BaseSchema):
    """租户管理员修改密码请求"""
    
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


__all__ = [
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
]
