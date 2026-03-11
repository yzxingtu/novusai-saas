"""
Schema 模块 / Schema Module

按模块分层组织，统一导出所有 Pydantic Schema
Organized by module layers, exports all Pydantic schemas.

目录结构 / Directory structure:
- common/: 公共 Schema（三端共用） / Common schemas (shared across all endpoints)
- system/: 平台管理后台 Schema / Platform admin schemas
- tenant/: 租户相关 Schema / Tenant schemas
"""

# Common
from app.schemas.common import (
    RefreshTokenRequest,
    TokenResponse,
)

# System
from app.schemas.system import (
    AdminChangePasswordRequest,
    AdminCreateRequest,
    AdminLoginRequest,
    AdminResponse,
    AdminUpdateRequest,
)

# Tenant
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
    # Common
    "TokenResponse",
    "RefreshTokenRequest",
    # System - Admin
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    # Tenant - Admin
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    # Tenant - User
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
]
