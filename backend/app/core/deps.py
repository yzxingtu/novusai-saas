"""
依赖注入模块 / Dependency Injection Module

提供 FastAPI 依赖注入函数
Provides FastAPI dependency injection functions.

认证架构 / Authentication Architecture:
- Admin: 平台管理员 / Platform admin (/admin/login)
- TenantAdmin: 企业管理员 / Tenant admin (/tenant/login)
- TenantUser: 企业业务用户 / Tenant business user (/api/user/auth/login)
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis as AioRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.i18n import _
from app.core.query_parser import QueryParams, get_query_spec
from app.core.redis import get_redis
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_ACCESS,
    TokenExpiredError,
    verify_token_with_scope,
)
from app.exceptions.base import TokenExpiredException
from app.models import Admin, TenantAdmin, TenantUser

# ========================================
# OAuth2 配置 / OAuth2 Configuration
# ========================================

# 平台管理员 OAuth2 / Platform admin OAuth2
oauth2_admin_scheme = OAuth2PasswordBearer(
    tokenUrl="/admin/auth/login",
    auto_error=False,
)

# 企业管理员 OAuth2 / Tenant admin OAuth2
oauth2_tenant_admin_scheme = OAuth2PasswordBearer(
    tokenUrl="/tenant/auth/login",
    auto_error=False,
)

# 企业业务用户 OAuth2 / Tenant business user OAuth2
oauth2_tenant_user_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话 / Get database session

    请求成功时自动提交，异常时自动回滚
    Auto-commits on success, auto-rollbacks on exception.

    Yields:
        AsyncSession: 异步数据库会话 / Async database session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ========================================
# 平台管理员认证 / Platform Admin Authentication
# ========================================


async def get_current_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_admin_scheme)],
) -> Admin:
    """
    获取当前平台管理员 / Get current platform admin
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        user_id, scope = await verify_token_with_scope(
            token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_ACCESS, raise_on_expired=True
        )
    except TokenExpiredError as exc:
        raise TokenExpiredException() from exc

    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(Admin).where(
            Admin.id == int(user_id),
            Admin.is_deleted.is_(False),
        )
    )
    admin = result.scalar_one_or_none()

    if admin is None:
        raise credentials_exception

    return admin


async def get_current_active_admin(
    current_admin: Annotated[Admin, Depends(get_current_admin)],
) -> Admin:
    """
    获取当前激活的平台管理员 / Get current active platform admin
    """
    if not current_admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("auth.account_disabled"),
        )
    return current_admin


async def get_current_super_admin(
    current_admin: Annotated[Admin, Depends(get_current_active_admin)],
) -> Admin:
    """
    获取当前超级管理员 / Get current super admin
    """
    if not current_admin.is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("admin.super_admin_required"),
        )
    return current_admin


# ========================================
# 企业管理员认证 / Tenant Admin Authentication
# ========================================


async def get_current_tenant_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_tenant_admin_scheme)],
) -> TenantAdmin:
    """
    获取当前企业管理员 / Get current tenant admin
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        user_id, scope = await verify_token_with_scope(
            token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_ACCESS, raise_on_expired=True
        )
    except TokenExpiredError as exc:
        raise TokenExpiredException() from exc

    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(TenantAdmin).where(
            TenantAdmin.id == int(user_id),
            TenantAdmin.is_deleted.is_(False),
        )
    )
    tenant_admin = result.scalar_one_or_none()

    if tenant_admin is None:
        raise credentials_exception

    return tenant_admin


async def get_current_active_tenant_admin(
    current_tenant_admin: Annotated[TenantAdmin, Depends(get_current_tenant_admin)],
) -> TenantAdmin:
    """
    获取当前激活的企业管理员 / Get current active tenant admin
    """
    if not current_tenant_admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("auth.account_disabled"),
        )
    return current_tenant_admin


async def get_current_tenant_owner(
    current_tenant_admin: Annotated[
        TenantAdmin, Depends(get_current_active_tenant_admin)
    ],
) -> TenantAdmin:
    """
    获取当前企业所有者 / Get current tenant owner
    """
    if not current_tenant_admin.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("tenant_admin.owner_required"),
        )
    return current_tenant_admin


# ========================================
# 企业业务用户认证 / Tenant Business User Authentication
# ========================================


async def get_current_tenant_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_tenant_user_scheme)],
) -> TenantUser:
    """
    获取当前企业业务用户 / Get current tenant business user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        user_id, scope = await verify_token_with_scope(
            token, TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_ACCESS, raise_on_expired=True
        )
    except TokenExpiredError as exc:
        raise TokenExpiredException() from exc

    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(TenantUser).where(
            TenantUser.id == int(user_id),
            TenantUser.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_tenant_user(
    current_user: Annotated[TenantUser, Depends(get_current_tenant_user)],
) -> TenantUser:
    """
    获取当前激活的企业业务用户 / Get current active tenant business user
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("auth.account_disabled"),
        )
    return current_user


# ========================================
# 类型别名 / Type Aliases
# ========================================

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Redis / Redis 异步客户端
RedisClient = Annotated[AioRedis, Depends(get_redis)]

# 平台管理员 / Platform admin
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
ActiveAdmin = Annotated[Admin, Depends(get_current_active_admin)]
SuperAdmin = Annotated[Admin, Depends(get_current_super_admin)]

# 企业管理员 / Tenant admin
CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
ActiveTenantAdmin = Annotated[TenantAdmin, Depends(get_current_active_tenant_admin)]
TenantOwner = Annotated[TenantAdmin, Depends(get_current_tenant_owner)]

# 企业业务用户 / Tenant business user
CurrentTenantUser = Annotated[TenantUser, Depends(get_current_tenant_user)]
ActiveTenantUser = Annotated[TenantUser, Depends(get_current_active_tenant_user)]


__all__ = [
    "get_db",
    # 平台管理员 / Platform admin
    "get_current_admin",
    "get_current_active_admin",
    "get_current_super_admin",
    "oauth2_admin_scheme",
    "CurrentAdmin",
    "ActiveAdmin",
    "SuperAdmin",
    # 企业管理员 / Tenant admin
    "get_current_tenant_admin",
    "get_current_active_tenant_admin",
    "get_current_tenant_owner",
    "oauth2_tenant_admin_scheme",
    "CurrentTenantAdmin",
    "ActiveTenantAdmin",
    "TenantOwner",
    # 企业业务用户 / Tenant business user
    "get_current_tenant_user",
    "get_current_active_tenant_user",
    "oauth2_tenant_user_scheme",
    "CurrentTenantUser",
    "ActiveTenantUser",
    # 通用 / Common
    "DbSession",
    "RedisClient",
    # 查询参数 / Query parameters
    "get_query_spec",
    "QueryParams",
]
