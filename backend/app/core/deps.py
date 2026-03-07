"""
依赖注入模块

提供 FastAPI 依赖注入函数

认证架构:
- Admin: 平台管理员 (/admin/login)
- TenantAdmin: 租户管理员 (/tenant/login)
- TenantUser: 租户业务用户 (/api/user/auth/login)
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
    verify_token_with_scope,
)
from app.models import Admin, TenantAdmin, TenantUser

# ========================================
# OAuth2 配置
# ========================================

# 平台管理员 OAuth2
oauth2_admin_scheme = OAuth2PasswordBearer(
    tokenUrl="/admin/auth/login",
    auto_error=False,
)

# 租户管理员 OAuth2
oauth2_tenant_admin_scheme = OAuth2PasswordBearer(
    tokenUrl="/tenant/auth/login",
    auto_error=False,
)

# 租户业务用户 OAuth2
oauth2_tenant_user_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话

    请求成功时自动提交，异常时自动回滚

    Yields:
        AsyncSession: 异步数据库会话
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
# 平台管理员认证
# ========================================

async def get_current_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_admin_scheme)],
) -> Admin:
    """
    获取当前平台管理员
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    # 验证 Token 并检查 scope
    user_id, scope = verify_token_with_scope(
        token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_ACCESS
    )
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
    获取当前激活的平台管理员
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
    获取当前超级管理员
    """
    if not current_admin.is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("admin.super_admin_required"),
        )
    return current_admin


# ========================================
# 租户管理员认证
# ========================================

async def get_current_tenant_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_tenant_admin_scheme)],
) -> TenantAdmin:
    """
    获取当前租户管理员
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    # 验证 Token 并检查 scope
    user_id, scope = verify_token_with_scope(
        token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_ACCESS
    )
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
    获取当前激活的租户管理员
    """
    if not current_tenant_admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("auth.account_disabled"),
        )
    return current_tenant_admin


async def get_current_tenant_owner(
    current_tenant_admin: Annotated[TenantAdmin, Depends(get_current_active_tenant_admin)],
) -> TenantAdmin:
    """
    获取当前租户所有者
    """
    if not current_tenant_admin.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("tenant_admin.owner_required"),
        )
    return current_tenant_admin


# ========================================
# 租户业务用户认证
# ========================================

async def get_current_tenant_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_tenant_user_scheme)],
) -> TenantUser:
    """
    获取当前租户业务用户
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=_("auth.token_invalid"),
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    # 验证 Token 并检查 scope
    user_id, scope = verify_token_with_scope(
        token, TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_ACCESS
    )
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
    获取当前激活的租户业务用户
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_("auth.account_disabled"),
        )
    return current_user


# ========================================
# 类型别名
# ========================================

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Redis
RedisClient = Annotated[AioRedis, Depends(get_redis)]

# 平台管理员
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
ActiveAdmin = Annotated[Admin, Depends(get_current_active_admin)]
SuperAdmin = Annotated[Admin, Depends(get_current_super_admin)]

# 租户管理员
CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
ActiveTenantAdmin = Annotated[TenantAdmin, Depends(get_current_active_tenant_admin)]
TenantOwner = Annotated[TenantAdmin, Depends(get_current_tenant_owner)]

# 租户业务用户
CurrentTenantUser = Annotated[TenantUser, Depends(get_current_tenant_user)]
ActiveTenantUser = Annotated[TenantUser, Depends(get_current_active_tenant_user)]


__all__ = [
    "get_db",
    # 平台管理员
    "get_current_admin",
    "get_current_active_admin",
    "get_current_super_admin",
    "oauth2_admin_scheme",
    "CurrentAdmin",
    "ActiveAdmin",
    "SuperAdmin",
    # 租户管理员
    "get_current_tenant_admin",
    "get_current_active_tenant_admin",
    "get_current_tenant_owner",
    "oauth2_tenant_admin_scheme",
    "CurrentTenantAdmin",
    "ActiveTenantAdmin",
    "TenantOwner",
    # 租户业务用户
    "get_current_tenant_user",
    "get_current_active_tenant_user",
    "oauth2_tenant_user_scheme",
    "CurrentTenantUser",
    "ActiveTenantUser",
    # 通用
    "DbSession",
    "RedisClient",
    # 查询参数
    "get_query_spec",
    "QueryParams",
]
