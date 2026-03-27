"""
平台管理员认证 API / Platform Admin Auth API

提供平台管理员的登录、登出、Token 刷新等接口
Provides platform admin login, logout, token refresh endpoints.
"""

from fastapi import APIRouter, Request

from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.rate_limit import check_login_rate_limit
from app.core.response import success
from app.rbac.decorators import auth_only, public
from app.schemas.common import RefreshTokenRequest, TokenResponse
from app.schemas.system import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminResponse,
    AdminUpdateProfileRequest,
)
from app.services.common import AuthService

router = APIRouter(prefix="/auth", tags=["平台管理员认证"])


@router.post("/login", summary="管理员登录")
@public
async def admin_login(
    db: DbSession,
    request: Request,
    login_data: AdminLoginRequest,
):
    """
    平台管理员登录 / Platform admin login

    - **username**: 用户名或邮箱 / Username or email
    - **password**: 密码 / Password
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited
    auth_service = AuthService(db)

    tokens = await auth_service.authenticate_admin(
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
    使用 Refresh Token 获取新的 Token 对 / Get new token pair using refresh token
    """
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_admin_token(refresh_data.refresh_token)

    return success(
        data=TokenResponse(**tokens),
        message=_("common.success"),
    )


@router.post("/logout", summary="管理员登出")
@auth_only
async def admin_logout(
    request: Request,
    db: DbSession,
    current_admin: ActiveAdmin,
):
    """
    管理员登出 / Admin logout
    吊销当前 access/refresh token，并从未生效的 active_tokens 中移除
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        auth_service = AuthService(db)
        await auth_service.revoke_on_logout(token, "admin", str(current_admin.id))
    return success(
        message=_("auth.logout_success"),
    )


@router.get("/me", summary="获取当前管理员信息")
@auth_only
async def get_current_admin_info(
    current_admin: ActiveAdmin,
):
    """
    获取当前登录管理员的详细信息 / Get current logged-in admin details
    """
    return success(
        data=AdminResponse.model_validate(current_admin, from_attributes=True),
        message=_("common.success"),
    )


@router.put("/password", summary="修改密码")
@auth_only
async def change_password(
    db: DbSession,
    current_admin: ActiveAdmin,
    password_data: AdminChangePasswordRequest,
):
    """
    修改当前管理员密码 / Change current admin password
    """
    auth_service = AuthService(db)

    await auth_service.change_admin_password(
        admin=current_admin,
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
    current_admin: ActiveAdmin,
    profile_data: AdminUpdateProfileRequest,
):
    """
    修改当前管理员的个人信息 / Update current admin profile

    允许修改 / Allowed fields: nickname, avatar, email, phone
    """
    update_fields = profile_data.model_dump(exclude_unset=True)
    if not update_fields:
        return success(message=_("common.success"))

    for field, value in update_fields.items():
        setattr(current_admin, field, value)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        if "unique" in str(e).lower() and "email" in str(e).lower():
            from app.exceptions import BusinessException
            raise BusinessException(message=_("auth.email_already_exists")) from e
        raise

    await db.refresh(current_admin)

    resp = AdminResponse.model_validate(current_admin, from_attributes=True)
    return success(data=resp, message=_("auth.profile_updated"))


__all__ = ["router"]
