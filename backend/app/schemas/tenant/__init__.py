"""
企业 Schema 模块 / Tenant Schema Module

导出企业相关的 Schema
Exports tenant related schemas.
"""

from app.schemas.tenant.admin import (
    TenantAdminChangePasswordRequest,
    TenantAdminCreateRequest,
    TenantAdminLoginRequest,
    TenantAdminResponse,
    TenantAdminUpdateProfileRequest,
    TenantAdminUpdateRequest,
)
from app.schemas.tenant.attachment import AttachmentAccessUrlResponse
from app.schemas.tenant.domain import (
    DevHostDomainStatus,
    DevHostMutationResponse,
    DevHostsRuntimeInfo,
    DevHostsStatusResponse,
    DevHostsSyncAllResponse,
    TenantDomainCreateRequest,
    TenantDomainResponse,
    TenantDomainSimpleResponse,
    TenantDomainUpdateRequest,
    TenantDomainVerificationInfo,
    TenantDomainVerifyRequest,
    TenantSettingsResponse,
    TenantSettingsUpdateRequest,
)
from app.schemas.tenant.plan import (
    FeaturesSchema,
    PermissionSimpleResponse,
    QuotaSchema,
    TenantPlanCreateRequest,
    TenantPlanDetailResponse,
    TenantPlanPermissionsRequest,
    TenantPlanResponse,
    TenantPlanUpdateRequest,
)
from app.schemas.tenant.role import (
    TenantAdminRoleAddMemberRequest,
    TenantAdminRoleCreateMemberRequest,
    TenantAdminRoleCreateRequest,
    TenantAdminRoleDetailResponse,
    TenantAdminRoleMemberResponse,
    TenantAdminRoleMoveRequest,
    TenantAdminRolePermissionsRequest,
    TenantAdminRoleResetPasswordRequest,
    TenantAdminRoleResponse,
    TenantAdminRoleSetLeaderRequest,
    TenantAdminRoleToggleStatusRequest,
    TenantAdminRoleTreeNode,
    TenantAdminRoleUpdateMemberRequest,
    TenantAdminRoleUpdateRequest,
)
from app.schemas.tenant.ssl import (
    SslAutoRenewRequest,
    SslCertificateResponse,
    SslCertificateUploadRequest,
    SslReplaceRequest,
)
from app.schemas.tenant.user_role import (
    TenantUserRoleCreateRequest,
    TenantUserRoleDetailResponse,
    TenantUserRolePermissionsRequest,
    TenantUserRoleResponse,
    TenantUserRoleUpdateRequest,
)
from app.schemas.tenant.user import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TenantUserChangePasswordRequest,
    TenantUserCreateRequest,
    TenantUserLoginRequest,
    TenantUserProfileUpdateRequest,
    TenantUserRegisterRequest,
    TenantUserResponse,
    TenantUserUpdateRequest,
)

__all__ = [
    # TenantAdmin
    "TenantAdminLoginRequest",
    "TenantAdminResponse",
    "TenantAdminCreateRequest",
    "TenantAdminUpdateRequest",
    "TenantAdminChangePasswordRequest",
    "TenantAdminUpdateProfileRequest",
    # TenantUser
    "TenantUserLoginRequest",
    "TenantUserResponse",
    "TenantUserCreateRequest",
    "TenantUserUpdateRequest",
    "TenantUserChangePasswordRequest",
    "TenantUserRegisterRequest",
    "TenantUserProfileUpdateRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
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
    # TenantUserRole
    "TenantUserRoleResponse",
    "TenantUserRoleDetailResponse",
    "TenantUserRoleCreateRequest",
    "TenantUserRoleUpdateRequest",
    "TenantUserRolePermissionsRequest",
    # Domain
    "TenantDomainSimpleResponse",
    "TenantDomainVerificationInfo",
    "TenantDomainResponse",
    "DevHostsRuntimeInfo",
    "DevHostDomainStatus",
    "DevHostsStatusResponse",
    "DevHostMutationResponse",
    "DevHostsSyncAllResponse",
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
    "AttachmentAccessUrlResponse",
    # SSL
    "SslCertificateResponse",
    "SslCertificateUploadRequest",
    "SslAutoRenewRequest",
    "SslReplaceRequest",
]
