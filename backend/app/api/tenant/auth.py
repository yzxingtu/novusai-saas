"""
租户管理员认证 API

提供租户管理员的登录、登出、Token 刷新等接口
"""

from fastapi import APIRouter, Request

from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.logging import ImpersonateLoggerMixin
from app.core.response import success
from app.rbac.decorators import public, auth_only
from app.schemas.common import TokenResponse, RefreshTokenRequest, ImpersonateTokenRequest
from app.schemas.tenant import (
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminChangePasswordRequest,
)
from app.services.common import AuthService


# 审计日志辅助类
class _ImpersonateAuditLogger(ImpersonateLoggerMixin):
    """Impersonate 审计日志器"""
    pass

_audit_helper = _ImpersonateAuditLogger()


router = APIRouter(prefix="/auth", tags=["租户管理员认证"])


@router.post("/login", summary="租户管理员登录")
@public
async def tenant_admin_login(
    db: DbSession,
    request: Request,
    login_data: TenantAdminLoginRequest,
):
    """
    租户管理员登录
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    auth_service = AuthService(db)
    
    tokens = await auth_service.authenticate_tenant_admin(
        username=login_data.username,
        password=login_data.password,
        client_ip=request.client.host if request.client else None,
        captcha_challenge_id=login_data.captcha_challenge_id,
        captcha_solution=login_data.captcha_solution,
        captcha_provider_code=login_data.captcha_provider_code,
    )
    await db.commit()
    
    return success(
        data=TokenResponse(**tokens),
        message=_("auth.login_success"),
    )


@router.post("/refresh", summary="刷新 Token")
@public
async def refresh_token(
    db: DbSession,
    refresh_data: RefreshTokenRequest,
):
    """
    使用 Refresh Token 获取新的 Token 对
    """
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_tenant_admin_token(refresh_data.refresh_token)
    
    return success(
        data=TokenResponse(**tokens),
        message=_("common.success"),
    )


@router.post("/logout", summary="租户管理员登出")
@auth_only
async def tenant_admin_logout(
    current_admin: ActiveTenantAdmin,
):
    """
    租户管理员登出
    """
    return success(
        message=_("auth.logout_success"),
    )


@router.get("/me", summary="获取当前租户管理员信息")
@auth_only
async def get_current_tenant_admin_info(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """
    获取当前登录租户管理员的详细信息

    响应中包含 has_plan 字段，前端据此判断是否显示"未分配套餐"提示。
    """
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import selectinload
    from app.models.tenant.tenant import Tenant

    result = await db.execute(
        sa_select(Tenant)
        .where(Tenant.id == current_admin.tenant_id)
        .options(selectinload(Tenant.tenant_plan))
    )
    tenant = result.scalar_one_or_none()
    has_plan = tenant is not None and tenant.plan_id is not None
    plan_name = None
    if has_plan and tenant and tenant.tenant_plan:
        plan_name = tenant.tenant_plan.name

    resp = TenantAdminResponse.model_validate(current_admin, from_attributes=True)
    resp.has_plan = has_plan
    resp.plan_name = plan_name
    return success(data=resp, message=_("common.success"))


@router.put("/password", summary="修改密码")
@auth_only
async def change_password(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    password_data: TenantAdminChangePasswordRequest,
):
    """
    修改当前租户管理员密码
    """
    auth_service = AuthService(db)
    
    await auth_service.change_tenant_admin_password(
        tenant_admin=current_admin,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    await db.commit()
    
    return success(
        message=_("auth.password_changed"),
    )


@router.post("/impersonate", summary="平台管理员一键登录")
@public
async def impersonate_login(
    db: DbSession,
    request: Request,
    data: ImpersonateTokenRequest,
):
    """
    验证平台管理员的 impersonate token 并换取正式 Token
    
    - Token 60 秒过期，一次性使用
    - 返回标准的 access_token 和 refresh_token
    """
    auth_service = AuthService(db)
    
    tokens, audit_info = await auth_service.impersonate_tenant_admin(
        impersonate_token=data.impersonate_token,
    )
    
    # 记录审计日志
    _audit_helper.logger.info(
        "Admin impersonate completed | admin_id=%s | admin_username=%s | "
        "target_tenant_id=%s | target_tenant_code=%s | tenant_owner_id=%s | "
        "target_role_id=%s | client_ip=%s",
        audit_info["admin_id"],
        audit_info["admin_username"],
        audit_info["target_tenant_id"],
        audit_info["target_tenant_code"],
        audit_info["tenant_owner_id"],
        audit_info["target_role_id"],
        request.client.host if request.client else None,
    )
    
    return success(
        data=TokenResponse(**tokens),
        message=_("auth.impersonate_success"),
    )


__all__ = ["router"]
