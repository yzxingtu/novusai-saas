"""
平台管理后台 Schema 模块 / Platform Admin Schema Module

导出平台管理相关的 Schema
Exports platform admin related schemas.
"""

from app.schemas.system.admin import (
    AdminChangePasswordRequest,
    AdminCreateRequest,
    AdminLoginRequest,
    AdminResponse,
    AdminUpdateProfileRequest,
    AdminUpdateRequest,
)
from app.schemas.system.cache import (
    CacheCategorySummary,
    CacheClearRequest,
    CacheClearResponse,
    CacheSummaryResponse,
)
from app.schemas.system.operation_log import (
    LogStatsItem,
    LogStatsResponse,
    OperationLogDeleteRequest,
    OperationLogListResponse,
    OperationLogResponse,
    OperatorSelectItem,
)
from app.schemas.system.periodic_task import (
    PeriodicTaskCreateRequest,
    PeriodicTaskResponse,
    PeriodicTaskToggleRequest,
    PeriodicTaskUpdateRequest,
)
from app.schemas.system.role import (
    AdminRoleAddMemberRequest,
    AdminRoleCreateMemberRequest,
    AdminRoleCreateRequest,
    AdminRoleDetailResponse,
    AdminRoleMemberResponse,
    AdminRoleMoveRequest,
    AdminRolePermissionsRequest,
    AdminRoleResetPasswordRequest,
    AdminRoleResponse,
    AdminRoleSetLeaderRequest,
    AdminRoleToggleStatusRequest,
    AdminRoleTreeNode,
    AdminRoleUpdateMemberRequest,
    AdminRoleUpdateRequest,
)
from app.schemas.system.task_log import (
    ActiveTaskResponse,
    TaskLogDetailResponse,
    TaskLogResponse,
    TaskRetryRequest,
    TaskStatsResponse,
)
from app.schemas.system.tenant import (
    TenantCreateRequest,
    TenantImpersonateRequest,
    TenantImpersonateResponse,
    TenantResetOwnerPasswordRequest,
    TenantResponse,
    TenantStatusRequest,
    TenantStorageStats,
    TenantUpdateRequest,
)

__all__ = [
    # Admin
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    "AdminUpdateProfileRequest",
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
    "AdminRoleCreateMemberRequest",
    "AdminRoleUpdateMemberRequest",
    "AdminRoleResetPasswordRequest",
    "AdminRoleToggleStatusRequest",
    "AdminRoleMemberResponse",
    # Tenant
    "TenantResponse",
    "TenantStorageStats",
    "TenantCreateRequest",
    "TenantUpdateRequest",
    "TenantStatusRequest",
    "TenantImpersonateRequest",
    "TenantImpersonateResponse",
    "TenantResetOwnerPasswordRequest",
    # OperationLog
    "OperationLogResponse",
    "OperationLogListResponse",
    "OperatorSelectItem",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
    # TaskLog
    "TaskLogResponse",
    "TaskLogDetailResponse",
    "TaskStatsResponse",
    "TaskRetryRequest",
    "ActiveTaskResponse",
    # Cache
    "CacheCategorySummary",
    "CacheSummaryResponse",
    "CacheClearRequest",
    "CacheClearResponse",
    # PeriodicTask
    "PeriodicTaskResponse",
    "PeriodicTaskCreateRequest",
    "PeriodicTaskUpdateRequest",
    "PeriodicTaskToggleRequest",
]
