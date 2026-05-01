"""
企业管理员认证 API / Tenant Admin Authentication API

提供企业管理员的登录、登出、Token 刷新等接口
Provides tenant admin login, logout, token refresh endpoints
"""

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.logging import ImpersonateLoggerMixin
from app.core.rate_limit import check_login_rate_limit
from app.core.response import success
from app.middleware.tenant import get_tenant_context
from app.rbac.decorators import auth_only, public
from app.schemas.common import (
    DevBootstrapRequest,
    ImpersonateTokenRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.tenant import (
    TenantAdminChangePasswordRequest,
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminUpdateProfileRequest,
)
from app.services.common import AuthService
from app.services.tenant.tenant_admin_service import TenantAdminService


# 审计日志辅助类 / Audit log helper class
class _ImpersonateAuditLogger(ImpersonateLoggerMixin):
    """Impersonate 审计日志器 / Impersonate audit logger"""

    pass


_audit_helper = _ImpersonateAuditLogger()


router = APIRouter(prefix="/auth", tags=["企业管理员认证"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _resolve_tenant_id_from_context(request: Request) -> int | None:
    tenant_ctx = get_tenant_context(request)
    if tenant_ctx and tenant_ctx.is_resolved:
        return tenant_ctx.tenant_id
    return None


@router.post("/login", summary="企业管理员登录")
@public
async def tenant_admin_login(
    db: DbSession,
    request: Request,
    login_data: TenantAdminLoginRequest,
):
    """
    企业管理员登录 / Tenant admin login

    - **username**: 用户名或邮箱 / Username or email
    - **password**: 密码 / Password
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited
    auth_service = AuthService(db)
    tokens = await auth_service.tenant_admin_auth.authenticate(
        username=login_data.username,
        password=login_data.password,
        tenant_code=login_data.tenant_code,
        tenant_id_from_ctx=_resolve_tenant_id_from_context(request),
        client_ip=_client_ip(request),
        captcha_challenge_id=login_data.captcha_challenge_id,
        captcha_solution=login_data.captcha_solution,
        captcha_provider_code=login_data.captcha_provider_code,
    )
    await db.commit()

    return success(
        data=TokenResponse(**tokens),
        message=_("auth.login_success"),
    )


if settings.APP_ENV.strip().lower() == "development":

    @router.post("/dev/bootstrap", summary="开发环境企业管理员 Bootstrap 登录")
    @public
    async def tenant_admin_dev_bootstrap_login(
        db: DbSession,
        request: Request,
        bootstrap_data: DevBootstrapRequest,
    ):
        """
        开发环境 bootstrap 登录 / Development bootstrap login.

        仅在 development 环境注册，仍返回标准 access/refresh token 对。
        Registered only in development and still returns a standard token pair.
        """
        auth_service = AuthService(db)
        tokens = await auth_service.tenant_admin_auth.authenticate_by_dev_bootstrap(
            bootstrap_secret=bootstrap_data.bootstrap_secret,
            request_host=request.url.hostname or request.headers.get("host"),
            client_ip=_client_ip(request),
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
    使用 Refresh Token 获取新的 Token 对 / Use refresh token to get new token pair
    """
    auth_service = AuthService(db)
    tokens = await auth_service.tenant_admin_auth.refresh_token(
        refresh_data.refresh_token
    )

    return success(
        data=TokenResponse(**tokens),
        message=_("common.success"),
    )


@router.post("/logout", summary="企业管理员登出")
@auth_only
async def tenant_admin_logout(
    request: Request,
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """
    企业管理员登出 / Tenant admin logout
    吊销当前 access/refresh token
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        auth_service = AuthService(db)
        await auth_service.token_sessions.revoke_on_logout(
            token, "tenant_admin", str(current_admin.id)
        )
    return success(
        message=_("auth.logout_success"),
    )


@router.get("/me", summary="获取当前企业管理员信息")
@auth_only
async def get_current_tenant_admin_info(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
):
    """
    获取当前登录企业管理员的详细信息 / Get current logged-in tenant admin details

    响应中包含 has_plan 字段，前端据此判断是否显示“未分配套餐”提示。
    Response includes has_plan field for frontend to determine whether to show "no plan assigned" prompt.
    """
    auth_service = AuthService(db)
    profile_flags = await auth_service.tenant_admin_auth.get_profile_flags(
        current_admin
    )
    ai_profile = await TenantAdminService(
        db,
        current_admin.tenant_id,
    ).get_ai_availability_profile(current_admin)

    resp = TenantAdminResponse.model_validate(current_admin, from_attributes=True)
    resp.has_plan = bool(profile_flags["has_plan"])
    resp.plan_name = profile_flags["plan_name"]
    resp.tenant_ai_enabled = bool(ai_profile["tenant_ai_enabled"])
    resp.effective_ai_enabled = bool(ai_profile["effective_ai_enabled"])
    resp.ai_unavailable_reason = ai_profile["ai_unavailable_reason"]
    return success(data=resp, message=_("common.success"))


@router.put("/password", summary="修改密码")
@auth_only
async def change_password(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    password_data: TenantAdminChangePasswordRequest,
):
    """
    修改当前企业管理员密码 / Change current tenant admin password
    """
    auth_service = AuthService(db)
    await auth_service.tenant_admin_auth.change_password(
        tenant_admin=current_admin,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    await db.commit()

    return success(
        message=_("auth.password_changed"),
    )


@router.put("/profile", summary="修改个人信息")
@auth_only
async def update_profile(
    db: DbSession,
    current_admin: ActiveTenantAdmin,
    profile_data: TenantAdminUpdateProfileRequest,
):
    """
    修改当前企业管理员的个人信息 / Update current tenant admin profile

    允许修改 / Allowed fields: nickname, avatar, email, phone
    """
    update_fields = profile_data.model_dump(exclude_unset=True)
    if not update_fields:
        return success(message=_("common.success"))

    auth_service = AuthService(db)
    tenant_admin = await auth_service.tenant_admin_auth.update_profile(
        tenant_admin=current_admin,
        profile_data=update_fields,
    )
    await db.commit()
    resp = TenantAdminResponse.model_validate(tenant_admin, from_attributes=True)
    profile_flags = await auth_service.tenant_admin_auth.get_profile_flags(tenant_admin)
    ai_profile = await TenantAdminService(
        db,
        tenant_admin.tenant_id,
    ).get_ai_availability_profile(tenant_admin)
    resp.has_plan = bool(profile_flags["has_plan"])
    resp.plan_name = profile_flags["plan_name"]
    resp.tenant_ai_enabled = bool(ai_profile["tenant_ai_enabled"])
    resp.effective_ai_enabled = bool(ai_profile["effective_ai_enabled"])
    resp.ai_unavailable_reason = ai_profile["ai_unavailable_reason"]
    return success(data=resp, message=_("auth.profile_updated"))


@router.post("/impersonate", summary="平台管理员一键登录")
@public
async def impersonate_login(
    db: DbSession,
    request: Request,
    data: ImpersonateTokenRequest,
):
    """
    验证平台管理员的 impersonate token 并换取正式 Token / Verify platform admin impersonate token and exchange for formal tokens

    - Token 60 秒过期，一次性使用 / Token expires in 60 seconds, single use
    - 返回标准的 access_token 和 refresh_token / Returns standard access_token and refresh_token
    """
    auth_service = AuthService(db)
    tokens, audit_info = await auth_service.tenant_admin_auth.impersonate(
        impersonate_token=data.impersonate_token,
    )

    # 记录审计日志 / Record audit log
    _audit_helper.logger.info(
        "Admin impersonate completed | admin_id={} | admin_username={} | "
        "target_tenant_id=%s | target_tenant_code=%s | tenant_owner_id=%s | "
        "target_role_id=%s | client_ip=%s",
        audit_info["admin_id"],
        audit_info["admin_username"],
        audit_info["target_tenant_id"],
        audit_info["target_tenant_code"],
        audit_info["tenant_owner_id"],
        audit_info["target_role_id"],
        _client_ip(request),
    )

    return success(
        data=TokenResponse(**tokens),
        message=_("auth.impersonate_success"),
    )


__all__ = ["router"]
