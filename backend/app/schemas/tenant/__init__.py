"""
租户 Schema 模块

导出租户相关的 Schema
"""

from app.schemas.tenant.admin import (
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminCreateRequest,
    TenantAdminUpdateRequest,
    TenantAdminChangePasswordRequest,
)
from app.schemas.tenant.user import (
    TenantUserLoginRequest,
    TenantUserResponse,
    TenantUserCreateRequest,
    TenantUserUpdateRequest,
    TenantUserChangePasswordRequest,
)
from app.schemas.tenant.role import (
    TenantAdminRoleResponse,
    TenantAdminRoleDetailResponse,
    TenantAdminRoleTreeNode,
    TenantAdminRoleCreateRequest,
    TenantAdminRoleUpdateRequest,
    TenantAdminRolePermissionsRequest,
    TenantAdminRoleMoveRequest,
    TenantAdminRoleSetLeaderRequest,
    TenantAdminRoleAddMemberRequest,
    TenantAdminRoleCreateMemberRequest,
    TenantAdminRoleUpdateMemberRequest,
    TenantAdminRoleResetPasswordRequest,
    TenantAdminRoleToggleStatusRequest,
    TenantAdminRoleMemberResponse,
)
from app.schemas.tenant.domain import (
    TenantDomainSimpleResponse,
    TenantDomainVerificationInfo,
    TenantDomainResponse,
    TenantDomainCreateRequest,
    TenantDomainUpdateRequest,
    TenantDomainVerifyRequest,
    TenantSettingsResponse,
    TenantSettingsUpdateRequest,
)
from app.schemas.tenant.plan import (
    QuotaSchema,
    FeaturesSchema,
    TenantPlanResponse,
    TenantPlanDetailResponse,
    PermissionSimpleResponse,
    TenantPlanCreateRequest,
    TenantPlanUpdateRequest,
    TenantPlanPermissionsRequest,
)

__all__ = [
    # TenantAdmin
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    # TenantUser
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    # Role
    "TenantAdminRoleResponse",
    "TenantAdminRoleDetailResponse",
    "TenantAdminRoleTreeNode",
    "TenantAdminRoleCreateRequest",
    "TenantAdminRoleUpdateRequest",
    "TenantAdminRolePermissionsRequest",
    "TenantAdminRoleMoveRequest",
    "TenantAdminRoleSetLeaderRequest",
    "TenantAdminRoleAddMemberRequest",
    "TenantAdminRoleCreateMemberRequest",
    "TenantAdminRoleUpdateMemberRequest",
    "TenantAdminRoleResetPasswordRequest",
    "TenantAdminRoleToggleStatusRequest",
    "TenantAdminRoleMemberResponse",
    # Domain
    "TenantDomainSimpleResponse",
    "TenantDomainVerificationInfo",
    "TenantDomainResponse",
    "TenantDomainCreateRequest",
    "TenantDomainUpdateRequest",
    "TenantDomainVerifyRequest",
    "TenantSettingsResponse",
    "TenantSettingsUpdateRequest",
    # Plan
    "QuotaSchema",
    "FeaturesSchema",
    "TenantPlanResponse",
    "TenantPlanDetailResponse",
    "PermissionSimpleResponse",
    "TenantPlanCreateRequest",
    "TenantPlanUpdateRequest",
    "TenantPlanPermissionsRequest",
]
