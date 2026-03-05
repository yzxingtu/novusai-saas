"""
租户业务用户认证 API

提供租户业务用户（C端用户）的登录、登出、Token 刷新等接口
"""

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import ActiveTenantUser, DbSession
from app.core.i18n import _
from app.core.response import success
from app.middleware.tenant import get_tenant_context
from app.rbac.decorators import auth_only, public
from app.schemas.common import RefreshTokenRequest, TokenResponse
from app.schemas.tenant import (
    TenantUserChangePasswordRequest as ChangePasswordRequest,
)
from app.schemas.tenant import (
    TenantUserLoginRequest as LoginRequest,
)
from app.schemas.tenant import (
    TenantUserResponse as UserResponse,
)
from app.services.common import AuthService

router = APIRouter(prefix="/auth", tags=["租户用户认证"])


@router.post("/login", summary="用户登录（OAuth2 表单）")
@public
async def login_oauth2(
    db: DbSession,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 密码模式登录

    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    auth_service = AuthService(db)
    form = await request.form()

    # 从域名中间件获取 tenant_ctx 作为回退
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


@router.post("/login/json", summary="用户登录（JSON 格式）")
@public
async def login_json(
    db: DbSession,
    request: Request,
    login_data: LoginRequest,
):
    """
    JSON 格式登录

    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    auth_service = AuthService(db)

    # 从域名中间件获取 tenant_ctx 作为回退
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
    tokens = await auth_service.refresh_tenant_user_token(refresh_data.refresh_token)

    return success(
        data=TokenResponse(**tokens),
        message=_("common.success"),
    )


@router.post("/logout", summary="用户登出")
@auth_only
async def logout(
    current_user: ActiveTenantUser,
):
    """
    用户登出

    注意：JWT 是无状态的，登出只是客户端行为。
    如需服务端黑名单机制，请使用 Redis 存储已失效的 Token。
    """
    return success(
        message=_("auth.logout_success"),
    )


@router.get("/me", summary="获取当前用户信息")
@auth_only
async def get_current_user_info(
    current_user: ActiveTenantUser,
):
    """
    获取当前登录用户的详细信息
    """
    return success(
        data=UserResponse.model_validate(current_user, from_attributes=True),
        message=_("common.success"),
    )


@router.put("/password", summary="修改密码")
@auth_only
async def change_password(
    db: DbSession,
    current_user: ActiveTenantUser,
    password_data: ChangePasswordRequest,
):
    """
    修改当前用户密码
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


__all__ = ["router"]
