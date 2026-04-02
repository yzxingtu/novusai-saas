"""
企业业务用户认证 API / Tenant Business User Authentication API

提供企业业务用户（C端用户）的登录、登出、注册、Token 刷新、
Provides login, logout, registration, token refresh,
个人资料管理、忘记密码等接口
profile management, forgot password endpoints for tenant business users (end users)

迁移自 api/v1/auth.py → api/user/auth.py
Migrated from api/v1/auth.py → api/user/auth.py
"""

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.configs.service import ConfigService
from app.core.deps import ActiveTenantUser, DbSession
from app.core.i18n import _
from app.core.rate_limit import check_login_rate_limit
from app.core.response import success
from app.exceptions import BusinessException
from app.middleware.tenant import get_tenant_context
from app.rbac.decorators import auth_only, public
from app.schemas.common import RefreshTokenRequest, TokenResponse
from app.schemas.tenant import (
    LoginByCodeRequest,
    SendLoginCodeRequest,
)
from app.schemas.tenant import (
    TenantUserChangePasswordRequest as ChangePasswordRequest,
)
from app.schemas.tenant import (
    TenantUserLoginRequest as LoginRequest,
)
from app.schemas.tenant import (
    TenantUserResponse as UserResponse,
)
from app.schemas.tenant.user import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TenantUserProfileUpdateRequest,
    TenantUserRegisterRequest,
)
from app.services.common import AuthService

router = APIRouter(prefix="/auth", tags=["User Authentication"])


@router.post("/login", summary="用户登录（OAuth2 表单） / User login (OAuth2 form)")
@public
async def login_oauth2(
    db: DbSession,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 密码模式登录 / OAuth2 password mode login

    - **username**: 用户名或邮箱 / Username or email
    - **password**: 密码 / Password
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited
    auth_service = AuthService(db)
    form = await request.form()

    # 从域名中间件获取 tenant_ctx 作为回退 / Get tenant_ctx from domain middleware as fallback
    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    tokens = await auth_service.authenticate_tenant_user(
        username=form_data.username,
        password=form_data.password,
        tenant_code=form.get("tenant_code"),
        tenant_id_from_ctx=tenant_id_from_ctx,
        client_ip=request.client.host if request.client else None,
        captcha_challenge_id=form.get("captcha_challenge_id"),
        captcha_solution=form.get("captcha_solution"),
        captcha_provider_code=form.get("captcha_provider_code"),
    )
    await db.commit()

    return success(
        data=TokenResponse(**tokens),
        message=_("auth.login_success"),
    )


@router.post("/login/json", summary="用户登录（JSON 格式） / User login (JSON format)")
@public
async def login_json(
    db: DbSession,
    request: Request,
    login_data: LoginRequest,
):
    """
    JSON 格式登录 / JSON format login

    - **username**: 用户名或邮箱 / Username or email
    - **password**: 密码 / Password
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited
    auth_service = AuthService(db)

    # 从域名中间件获取 tenant_ctx 作为回退 / Get tenant_ctx from domain middleware as fallback
    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    tokens = await auth_service.authenticate_tenant_user(
        username=login_data.username,
        password=login_data.password,
        tenant_code=login_data.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
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


@router.post("/login-code/send", summary="发送登录验证码 / Send login verification code")
@public
async def send_login_code(
    db: DbSession,
    request: Request,
    payload: SendLoginCodeRequest,
):
    """
    发送企业用户登录验证码 / Send tenant-user login verification code.
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited

    auth_service = AuthService(db)
    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    result = await auth_service.send_tenant_user_login_code(
        channel=payload.channel,
        email=payload.email,
        phone=payload.phone,
        tenant_code=payload.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
        client_ip=request.client.host if request.client else None,
        captcha_challenge_id=payload.captcha_challenge_id,
        captcha_solution=payload.captcha_solution,
        captcha_provider_code=payload.captcha_provider_code,
    )
    return success(
        data=result,
        message=_("auth.login_code_sent"),
    )


@router.post("/login-code/login", summary="验证码登录 / Login with verification code")
@public
async def login_by_code(
    db: DbSession,
    request: Request,
    payload: LoginByCodeRequest,
):
    """
    企业用户验证码登录 / Tenant-user login with verification code.
    """
    rate_limited = check_login_rate_limit(request)
    if rate_limited:
        return rate_limited

    auth_service = AuthService(db)
    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    tokens = await auth_service.authenticate_tenant_user_by_code(
        channel=payload.channel,
        code=payload.code,
        email=payload.email,
        phone=payload.phone,
        tenant_code=payload.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
        client_ip=request.client.host if request.client else None,
    )
    await db.commit()

    return success(
        data=TokenResponse(**tokens),
        message=_("auth.login_success"),
    )


@router.post("/refresh", summary="刷新 Token / Refresh Token")
@public
async def refresh_token(
    db: DbSession,
    refresh_data: RefreshTokenRequest,
):
    """
    使用 Refresh Token 获取新的 Token 对 / Use refresh token to obtain new token pair.
    """
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_tenant_user_token(refresh_data.refresh_token)

    return success(
        data=TokenResponse(**tokens),
        message=_("common.success"),
    )


@router.post("/logout", summary="用户登出 / User logout")
@auth_only
async def logout(
    request: Request,
    db: DbSession,
    current_user: ActiveTenantUser,
):
    """
    用户登出 / User logout
    吊销当前 access/refresh token
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        auth_service = AuthService(db)
        await auth_service.revoke_on_logout(token, "tenant_user", str(current_user.id))
    return success(
        message=_("auth.logout_success"),
    )


@router.get("/me", summary="获取当前用户信息 / Get current user info")
@auth_only
async def get_current_user_info(
    current_user: ActiveTenantUser,
):
    """
    获取当前登录用户的详细信息 / Get current user info.
    """
    return success(
        data=UserResponse.model_validate(current_user, from_attributes=True),
        message=_("common.success"),
    )


@router.put("/password", summary="修改密码 / Change password")
@auth_only
async def change_password(
    db: DbSession,
    current_user: ActiveTenantUser,
    password_data: ChangePasswordRequest,
):
    """
    修改当前用户密码 / Change current user password.
    """
    auth_service = AuthService(db)

    await auth_service.change_tenant_user_password(
        user=current_user,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    await db.commit()

    return success(
        message=_("auth.password_changed"),
    )


@router.post("/register", summary="用户注册 / User registration")
@public
async def register(
    db: DbSession,
    request: Request,
    register_data: TenantUserRegisterRequest,
):
    """
    企业用户自助注册 / Tenant user self-registration

    - **username**: 用户名 / Username
    - **email**: 邮箱 / Email
    - **password**: 密码 / Password
    - **confirm_password**: 确认密码 / Confirm password
    """
    auth_service = AuthService(db)

    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    result = await auth_service.register_tenant_user(
        username=register_data.username,
        email=register_data.email,
        password=register_data.password,
        tenant_code=register_data.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
        phone=register_data.phone,
        nickname=register_data.nickname,
        client_ip=request.client.host if request.client else None,
        captcha_challenge_id=register_data.captcha_challenge_id,
        captcha_solution=register_data.captcha_solution,
        captcha_provider_code=register_data.captcha_provider_code,
    )
    await db.commit()

    return success(
        data=result,
        message=_("auth.register_success"),
    )


@router.put("/profile", summary="更新个人资料 / Update profile")
@auth_only
async def update_profile(
    db: DbSession,
    current_user: ActiveTenantUser,
    profile_data: TenantUserProfileUpdateRequest,
):
    """
    更新当前用户个人资料 / Update current user profile.
    """
    config_service = ConfigService(db)
    allow_edit = await config_service.get_tenant_config(
        tenant_id=current_user.tenant_id,
        key="tenant_allow_profile_edit",
    )
    if allow_edit is False:
        raise BusinessException(message=_("user.profile_edit_disabled"))

    auth_service = AuthService(db)

    user = await auth_service.update_tenant_user_profile(
        user=current_user,
        nickname=profile_data.nickname,
        avatar=profile_data.avatar,
        gender=profile_data.gender,
        phone=profile_data.phone,
        email=profile_data.email,
    )
    await db.commit()

    return success(
        data=UserResponse.model_validate(user, from_attributes=True),
        message=_("common.success"),
    )


@router.post("/forgot-password", summary="忘记密码 / Forgot password")
@public
async def forgot_password(
    db: DbSession,
    request: Request,
    forgot_data: ForgotPasswordRequest,
):
    """
    请求密码重置 / Request password reset.

    发送验证码到指定邮箱
    Send verification code to specified email
    """
    auth_service = AuthService(db)

    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    result = await auth_service.request_password_reset(
        email=forgot_data.email,
        tenant_code=forgot_data.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
    )

    return success(
        data=result,
        message=_("auth.reset_code_sent"),
    )


@router.post("/reset-password", summary="重置密码 / Reset password")
@public
async def reset_password(
    db: DbSession,
    request: Request,
    reset_data: ResetPasswordRequest,
):
    """
    使用验证码重置密码 / Reset password using verification code.
    """
    auth_service = AuthService(db)

    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None

    await auth_service.reset_tenant_user_password(
        email=reset_data.email,
        code=reset_data.code,
        new_password=reset_data.new_password,
        tenant_code=reset_data.tenant_code,
        tenant_id_from_ctx=tenant_id_from_ctx,
    )
    await db.commit()

    return success(
        message=_("auth.password_reset_success"),
    )


__all__ = ["router"]
