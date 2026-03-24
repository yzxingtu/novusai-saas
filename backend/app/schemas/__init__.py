"""
Schema 模块 / Schema Module

按模块分层组织，统一导出所有 Pydantic Schema
Organized by module layers, exports all Pydantic schemas.

目录结构 / Directory structure:
- common/: 公共 Schema（三端共用） / Common schemas (shared across all endpoints)
- system/: 平台管理后台 Schema / Platform admin schemas
- tenant/: 企业相关 Schema / Tenant schemas
"""

# Common / 通用
from app.schemas.common import (
    RefreshTokenRequest,
    TokenResponse,
)

# System / 平台
from app.schemas.system import (
    AdminChangePasswordRequest,
    AdminCreateRequest,
    AdminLoginRequest,
    AdminResponse,
    AdminUpdateRequest,
)

# Tenant / 企业
from app.schemas.tenant import (
    TenantAdminChangePasswordRequest,
    TenantAdminCreateRequest,
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminUpdateRequest,
    TenantUserChangePasswordRequest,
    TenantUserCreateRequest,
    TenantUserLoginRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)

__all__ = [
    # Common / 通用
    "TokenResponse",
    "RefreshTokenRequest",
    # System - Admin / 平台 - 管理员
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    # Tenant - Admin / 企业 - 管理员
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    # Tenant - User / 企业 - 用户
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
]
