"""
平台管理后台 Schema 模块

导出平台管理相关的 Schema
"""

from app.schemas.system.admin import (
    AdminLoginRequest,
    AdminResponse,
    AdminCreateRequest,
    AdminUpdateRequest,
    AdminChangePasswordRequest,
)
from app.schemas.system.role import (
    AdminRoleResponse,
    AdminRoleDetailResponse,
    AdminRoleTreeNode,
    AdminRoleCreateRequest,
    AdminRoleUpdateRequest,
    AdminRolePermissionsRequest,
    AdminRoleMoveRequest,
    AdminRoleSetLeaderRequest,
    AdminRoleAddMemberRequest,
    AdminRoleMemberResponse,
)
from app.schemas.system.tenant import (
    TenantResponse,
    TenantCreateRequest,
    TenantUpdateRequest,
    TenantStatusRequest,
    TenantImpersonateRequest,
    TenantImpersonateResponse,
)
from app.schemas.system.operation_log import (
    OperationLogResponse,
    OperationLogListResponse,
    OperationLogDeleteRequest,
    LogStatsItem,
    LogStatsResponse,
)

__all__ = [
    # Admin
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    # Role
    "AdminRoleResponse",
    "AdminRoleDetailResponse",
    "AdminRoleTreeNode",
    "AdminRoleCreateRequest",
    "AdminRoleUpdateRequest",
    "AdminRolePermissionsRequest",
    "AdminRoleMoveRequest",
    "AdminRoleSetLeaderRequest",
    "AdminRoleAddMemberRequest",
    "AdminRoleMemberResponse",
    # Tenant
    "TenantResponse",
    "TenantCreateRequest",
    "TenantUpdateRequest",
    "TenantStatusRequest",
    "TenantImpersonateRequest",
    "TenantImpersonateResponse",
    # OperationLog
    "OperationLogResponse",
    "OperationLogListResponse",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
]
