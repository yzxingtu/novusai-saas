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
from app.schemas.system.admin_org_node import (
    AdminOrgNodeAssignMemberRequest,
    AdminOrgNodeAuthorityPolicyRequest,
    AdminOrgNodeCreateMemberRequest,
    AdminOrgNodeCreateRequest,
    AdminOrgNodeDetailResponse,
    AdminOrgNodeMemberResponse,
    AdminOrgNodeMoveRequest,
    AdminOrgNodeResetPasswordRequest,
    AdminOrgNodeResponse,
    AdminOrgNodeSetLeaderRequest,
    AdminOrgNodeToggleStatusRequest,
    AdminOrgNodeTreeNode,
    AdminOrgNodeUpdateMemberRequest,
    AdminOrgNodeUpdateRequest,
)
from app.schemas.system.admin_permission_role import (
    AdminPermissionRoleAssignPermissionsRequest,
    AdminPermissionRoleCreateRequest,
    AdminPermissionRoleDetailResponse,
    AdminPermissionRoleResponse,
    AdminPermissionRoleUpdateRequest,
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
    PeriodicTaskBindingResponse,
    PeriodicTaskBindingSyncRequest,
    PeriodicTaskCreateRequest,
    PeriodicTaskResponse,
    PeriodicTaskToggleRequest,
    PeriodicTaskUpdateRequest,
)
from app.schemas.system.role import (
    AdminRoleAddMemberRequest,
    AdminRoleCreateRequest,
    AdminRoleCreateMemberRequest,
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
    # Admin / 平台管理员
    "AdminLoginRequest",
    "AdminResponse",
    "AdminCreateRequest",
    "AdminUpdateRequest",
    "AdminChangePasswordRequest",
    "AdminUpdateProfileRequest",
    # Role / 角色与组织
    "AdminOrgNodeResponse",
    "AdminOrgNodeDetailResponse",
    "AdminOrgNodeTreeNode",
    "AdminOrgNodeCreateRequest",
    "AdminOrgNodeUpdateRequest",
    "AdminOrgNodeAuthorityPolicyRequest",
    "AdminOrgNodeMoveRequest",
    "AdminOrgNodeSetLeaderRequest",
    "AdminOrgNodeAssignMemberRequest",
    "AdminOrgNodeCreateMemberRequest",
    "AdminOrgNodeUpdateMemberRequest",
    "AdminOrgNodeResetPasswordRequest",
    "AdminOrgNodeToggleStatusRequest",
    "AdminOrgNodeMemberResponse",
    "AdminPermissionRoleResponse",
    "AdminPermissionRoleDetailResponse",
    "AdminPermissionRoleCreateRequest",
    "AdminPermissionRoleUpdateRequest",
    "AdminPermissionRoleAssignPermissionsRequest",
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
    # Tenant / 企业
    "TenantResponse",
    "TenantStorageStats",
    "TenantCreateRequest",
    "TenantUpdateRequest",
    "TenantStatusRequest",
    "TenantImpersonateRequest",
    "TenantImpersonateResponse",
    "TenantResetOwnerPasswordRequest",
    # OperationLog / 操作日志
    "OperationLogResponse",
    "OperationLogListResponse",
    "OperatorSelectItem",
    "OperationLogDeleteRequest",
    "LogStatsItem",
    "LogStatsResponse",
    # TaskLog / 任务日志
    "TaskLogResponse",
    "TaskLogDetailResponse",
    "TaskStatsResponse",
    "TaskRetryRequest",
    "ActiveTaskResponse",
    # Cache / 缓存
    "CacheCategorySummary",
    "CacheSummaryResponse",
    "CacheClearRequest",
    "CacheClearResponse",
    # PeriodicTask / 周期任务
    "PeriodicTaskResponse",
    "PeriodicTaskCreateRequest",
    "PeriodicTaskUpdateRequest",
    "PeriodicTaskToggleRequest",
    "PeriodicTaskBindingResponse",
    "PeriodicTaskBindingSyncRequest",
]
