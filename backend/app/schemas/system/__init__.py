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
    AdminUpdateProfileRequest,
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
    AdminRoleCreateMemberRequest,
    AdminRoleUpdateMemberRequest,
    AdminRoleResetPasswordRequest,
    AdminRoleToggleStatusRequest,
    AdminRoleMemberResponse,
)
from app.schemas.system.tenant import (
    TenantResponse,
    TenantStorageStats,
    TenantCreateRequest,
    TenantUpdateRequest,
    TenantStatusRequest,
    TenantImpersonateRequest,
    TenantImpersonateResponse,
    TenantResetOwnerPasswordRequest,
)
from app.schemas.system.operation_log import (
    OperationLogResponse,
    OperationLogListResponse,
    OperatorSelectItem,
    OperationLogDeleteRequest,
    LogStatsItem,
    LogStatsResponse,
)
from app.schemas.system.task_log import (
    TaskLogResponse,
    TaskLogDetailResponse,
    TaskStatsResponse,
    TaskRetryRequest,
    ActiveTaskResponse,
)
from app.schemas.system.periodic_task import (
    PeriodicTaskResponse,
    PeriodicTaskCreateRequest,
    PeriodicTaskUpdateRequest,
    PeriodicTaskToggleRequest,
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
    # PeriodicTask
    "PeriodicTaskResponse",
    "PeriodicTaskCreateRequest",
    "PeriodicTaskUpdateRequest",
    "PeriodicTaskToggleRequest",
]
